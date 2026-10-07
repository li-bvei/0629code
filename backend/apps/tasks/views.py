import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.audit.services import record, safe_changes
from apps.authentication.access_policy import ALLOW
from apps.authentication.drf import BusinessScopedViewSetMixin

from .daily_plan import PlanError, carry_over, generate_report, next_sort_order, parse_date, same_version
from .models import DailyWorkReport, Task
from .serializers import DailyWorkReportSerializer, TaskSerializer

AUDITED_FIELDS = ('title', 'description', 'status', 'priority', 'work_date', 'case_id', 'result_note', 'sort_order',
                  'due_date', 'responsible_employee_id')
MAX_BATCH = 100


class VersionConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = '他の操作で内容が変わっています。画面を更新してからもう一度操作してください。'
    default_code = 'conflict'


OWN_PLAN_ONLY = '他の人の計画は変更できません。'


class PermissionDeniedPlan(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = OWN_PLAN_ONLY
    default_code = 'permission_denied'


class PermissionDeniedReport(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = '担当者に関連付いていないアカウントは業務報告を作成できません。管理者に確認してください。'
    default_code = 'permission_denied'



class PlanPagination(PageNumberPagination):
    # 1 日の計画をまとめて取得できるよう page_size を指定可能にする（既定は従来どおり 20 件）
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


def _plan_error_response(exc):
    body = {'detail': exc.detail, 'code': exc.code}
    if exc.field:
        body[exc.field] = [exc.detail]
    return Response(body, status=exc.status)


def _snapshot(task):
    return {name: getattr(task, name) for name in AUDITED_FIELDS}


def _repr(task):
    prefix = f'計画 {task.work_date}' if task.work_date else f'タスク {getattr(task.case, "case_number", "")}'
    return f'{prefix} {task.title}'[:255]


class TaskViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    """案件タスクと毎日の計画（P3）。計画の項目は本人だけが変更でき、全件閲覧権限者は閲覧だけ（TaskRule）。"""

    access_resource = 'task'
    # 一覧の範囲（list）で項目を探し、項目ごとの可否は action 内で判定する
    access_action_map = {'reorder': 'list', 'carry_over_batch': 'list', 'calendar': 'list'}
    queryset = Task.objects.select_related('case__customer', 'responsible_employee', 'carried_from')
    serializer_class = TaskSerializer
    pagination_class = PlanPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        case_id = params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        plan = params.get('plan') in ('1', 'true')
        if plan:
            queryset = queryset.filter(work_date__isnull=False)
        elif self.action == 'list':
            # 既定の一覧は従来の案件タスクだけ（毎日の計画の項目は plan=1 のときだけ返す：P3 互換）
            queryset = queryset.filter(work_date__isnull=True)
        work_date = params.get('work_date')
        if work_date:
            queryset = queryset.filter(work_date=work_date)
        if params.get('work_date_from'):
            queryset = queryset.filter(work_date__gte=params['work_date_from'])
        if params.get('work_date_to'):
            queryset = queryset.filter(work_date__lte=params['work_date_to'])
        employee = params.get('employee')
        if employee == 'me':
            employee = self.business_policy.employee_id or 0
        if employee:
            queryset = queryset.filter(responsible_employee_id=employee)
        if work_date or plan:
            queryset = queryset.order_by('work_date', 'sort_order', 'id')
        return queryset

    # --- 作成・更新・削除（版の確認と監査） ------------------------------------------------
    def perform_create(self, serializer):
        work_date = serializer.validated_data.get('work_date')
        if work_date is not None and 'sort_order' not in self.request.data:
            employee_id = self.business_policy.employee_id
            serializer.validated_data['sort_order'] = next_sort_order(employee_id, work_date) if employee_id else 0
        super().perform_create(serializer)

    def after_create(self, instance):
        record(module='tasks', action='plan_item_created' if instance.work_date else 'task_created',
               request=self.request, obj=instance, object_repr=_repr(instance),
               extra={'case_id': instance.case_id, 'work_date': instance.work_date.isoformat() if instance.work_date else None})

    def perform_update(self, serializer):
        # 行をロックしてから、画面で見ていた版（version＝updated_at）と比べる。違えば 409（黙って上書きしない）
        with transaction.atomic():
            locked = Task.objects.select_for_update().get(pk=serializer.instance.pk)  # access-reviewed: get_object で権限確認済みの行をロック
            if not same_version(locked, self.request.data.get('version')):
                raise VersionConflict()
            before = _snapshot(locked)
            serializer.instance = locked
            super().perform_update(serializer)
            after = _snapshot(serializer.instance)
            changes = safe_changes(before, after)
            if changes:
                record(module='tasks', action='plan_item_updated' if locked.work_date else 'task_updated',
                       request=self.request, obj=serializer.instance, object_repr=_repr(serializer.instance),
                       changes=changes, extra={'case_id': serializer.instance.case_id})

    def perform_destroy(self, instance):
        if not same_version(instance, self.request.query_params.get('version')):
            raise VersionConflict()
        record(module='tasks', action='plan_item_deleted' if instance.work_date else 'task_deleted',
               request=self.request, obj=instance, object_repr=_repr(instance),
               extra={'case_id': instance.case_id, 'title': instance.title})
        instance.delete()

    # --- 結転 -----------------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar(self, request):
        """日付の営業日情報（P6）：祝日名・土日・次の営業日。結転の既定日と、祝日を選んだときの注意に使う。"""
        from .business_days import day_info

        try:
            value = parse_date(request.query_params.get('date'))
        except PlanError:
            return Response({'date': ['日付を YYYY-MM-DD で指定してください。']}, status=400)
        return Response(day_info(value))

    @action(detail=True, methods=['post'], url_path='carry-over')
    def carry_over(self, request, pk=None):
        """未完了の項目を別の日へ送る（元の項目は元の日に「結転済み」で残り、新しい項目が結転元を指す）。"""
        task = self.get_object()  # 本人の計画でなければ 403／404
        try:
            target = parse_date(request.data.get('target_date'), 'target_date')
            original, created = carry_over(task.pk, target_date=target, version=request.data.get('version'),
                                           actor=request.user, request=request)
        except PlanError as exc:
            return _plan_error_response(exc)
        return Response({'original': TaskSerializer(original).data, 'created': TaskSerializer(created).data},
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='carry-over-batch')
    def carry_over_batch(self, request):
        """複数の未完了項目を結転する。項目ごとに独立して処理し、1 件の失敗で他の結転を取り消さない。"""
        policy = self.business_policy
        try:
            target = parse_date(request.data.get('target_date'), 'target_date')
        except PlanError as exc:
            return _plan_error_response(exc)
        items = request.data.get('items')
        if not isinstance(items, list) or not items or len(items) > MAX_BATCH:
            raise ValidationError({'items': [f'結転する項目を選んでください（{MAX_BATCH} 件まで）。']})
        visible = {t.pk: t for t in self.get_queryset().filter(pk__in=[i.get('id') for i in items if isinstance(i, dict)])}
        batch_id = uuid.uuid4().hex
        results = []
        for item in items:
            task_id = item.get('id') if isinstance(item, dict) else None
            task = visible.get(task_id)
            if task is None:
                results.append({'id': task_id, 'status': 'failed', 'code': 'not_found', 'detail': '項目が見つかりません。'})
                continue
            if policy.decide('task', task, 'change') != ALLOW:
                results.append({'id': task_id, 'status': 'failed', 'code': 'forbidden', 'detail': OWN_PLAN_ONLY})
                continue
            try:
                _, created = carry_over(task_id, target_date=target, version=item.get('version'), actor=request.user,
                                        request=request, batch_id=batch_id)
            except PlanError as exc:
                results.append({'id': task_id, 'status': 'failed', 'code': exc.code, 'detail': exc.detail})
                continue
            results.append({'id': task_id, 'status': 'success', 'new_id': created.pk})
        succeeded = sum(1 for r in results if r['status'] == 'success')
        record(module='tasks', action='plan_items_carried_over_batch', request=request,
               object_type='tasks.task', object_id='', object_repr=f'計画の一括結転 → {target}',
               result='success' if succeeded == len(results) else 'error',
               extra={'batch_id': batch_id, 'target_date': target.isoformat(), 'requested': len(results),
                      'succeeded': succeeded, 'failed': len(results) - succeeded,
                      'failures': [{'id': r['id'], 'code': r['code']} for r in results if r['status'] == 'failed'][:50]})
        return Response({'batch_id': batch_id, 'target_date': target.isoformat(), 'requested': len(results),
                         'succeeded': succeeded, 'failed': len(results) - succeeded, 'results': results})

    # --- 並べ替え（同じ日の本人の項目をまとめて：全体を 1 つの操作として扱う） -----------------------
    @action(detail=False, methods=['post'], url_path='reorder')
    def reorder(self, request):
        """並び順を保存する。1 件でも版が違えば全体を取りやめる（並び順が中途半端にならないように）。"""
        policy = self.business_policy
        try:
            work_date = parse_date(request.data.get('work_date'), 'work_date')
        except PlanError as exc:
            return _plan_error_response(exc)
        items = request.data.get('items')
        if not isinstance(items, list) or not items or len(items) > MAX_BATCH:
            raise ValidationError({'items': ['並べ替える項目を指定してください。']})
        ids = [item.get('id') for item in items if isinstance(item, dict)]
        if len(set(ids)) != len(items):
            raise ValidationError({'items': ['項目の指定が正しくありません。']})
        with transaction.atomic():
            tasks = {t.pk: t for t in self.get_queryset().select_related(None).select_for_update().filter(pk__in=ids)}
            for item in items:
                task = tasks.get(item['id'])
                if task is None or task.work_date != work_date:
                    raise ValidationError({'items': ['この日の計画ではない項目が含まれています。']})
                if policy.decide('task', task, 'change') != ALLOW:
                    raise PermissionDeniedPlan()
                if not same_version(task, item.get('version')):
                    raise VersionConflict()
            for index, item in enumerate(items, start=1):
                task = tasks[item['id']]
                if task.sort_order != index * 10:
                    task.sort_order = index * 10
                    task.save(update_fields=['sort_order', 'updated_at'])
            record(module='tasks', action='plan_items_reordered', request=request, object_type='tasks.task',
                   object_id='', object_repr=f'計画の並べ替え {work_date}',
                   extra={'work_date': work_date.isoformat(), 'order': ids})
        rows = self.get_queryset().filter(pk__in=ids).order_by('sort_order', 'id')
        return Response(TaskSerializer(rows, many=True).data)



class DailyWorkReportViewSet(BusinessScopedViewSetMixin, ListModelMixin, RetrieveModelMixin, UpdateModelMixin,
                             GenericViewSet):
    """業務報告（P3）。社内に保存し、コピーできる文を作るだけ（外部送信はしない）。

    作成は generate（本人のみ）。本文（final_text）の編集は本人のみで、版（version）を確認する。
    全件閲覧権限者は閲覧だけ（DailyReportRule）。
    """

    access_resource = 'daily_report'
    access_action_map = {'generate': 'list', 'confirm': 'change'}
    queryset = DailyWorkReport.objects.select_related('employee')
    serializer_class = DailyWorkReportSerializer
    pagination_class = PlanPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        employee = params.get('employee')
        if employee == 'me':
            employee = self.business_policy.employee_id or 0
        if employee:
            queryset = queryset.filter(employee_id=employee)
        if params.get('report_date'):
            queryset = queryset.filter(report_date=params['report_date'])
        if params.get('date_from'):
            queryset = queryset.filter(report_date__gte=params['date_from'])
        if params.get('date_to'):
            queryset = queryset.filter(report_date__lte=params['date_to'])
        return queryset

    def _own_employee(self):
        employee_id = self.business_policy.employee_id
        if employee_id is None:
            raise PermissionDeniedReport()
        from apps.employees.models import Employee

        return Employee.objects.get(pk=employee_id)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """その日の本人の計画から報告の下書きを作る（下書きなら作り直す。確定済みは作り直さない）。"""
        employee = self._own_employee()
        try:
            report_date = parse_date(request.data.get('report_date') or timezone.localdate(), 'report_date')
            report, created = generate_report(
                employee, report_date, actor=request.user, request=request, version=request.data.get('version'),
                overwrite_edits=request.data.get('overwrite_edits') in (True, 'true', '1', 1),
            )
        except PlanError as exc:
            return _plan_error_response(exc)
        return Response(self.get_serializer(report).data, status=status.HTTP_201_CREATED if created else 200)

    def perform_update(self, serializer):
        with transaction.atomic():
            locked = DailyWorkReport.objects.select_for_update().get(pk=serializer.instance.pk)
            if not same_version(locked, self.request.data.get('version')):
                raise VersionConflict()
            before_length = len(locked.final_text)
            serializer.instance = locked
            super().perform_update(serializer)
            report = serializer.instance
            report.updated_by = self.request.user
            report.save(update_fields=['updated_by', 'updated_at'])
            record(module='tasks', action='daily_report_edited', request=self.request, obj=report,
                   object_repr=f'業務報告 {report.report_date} {report.employee.name}'[:255],
                   extra={'before_length': before_length, 'after_length': len(report.final_text),
                          'status': report.status})

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        """確定する（以後は再生成できない。生成時のスナップショットは固定。本文の編集はできる）。"""
        report = self.get_object()
        with transaction.atomic():
            locked = DailyWorkReport.objects.select_for_update().get(pk=report.pk)
            if not same_version(locked, request.data.get('version')):
                raise VersionConflict()
            if locked.status == DailyWorkReport.STATUS_CONFIRMED:
                return Response({'detail': '既に確定しています。', 'code': 'confirmed'}, status=400)
            locked.status = DailyWorkReport.STATUS_CONFIRMED
            locked.confirmed_at = timezone.now()
            locked.confirmed_by = locked.updated_by = request.user
            locked.save(update_fields=['status', 'confirmed_at', 'confirmed_by', 'updated_by', 'updated_at'])
            record(module='tasks', action='daily_report_confirmed', request=request, obj=locked,
                   object_repr=f'業務報告 {locked.report_date} {locked.employee.name}'[:255],
                   changes={'status': {'from': DailyWorkReport.STATUS_DRAFT, 'to': DailyWorkReport.STATUS_CONFIRMED}})
        return Response(self.get_serializer(locked).data)
