from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case as DbCase
from django.db.models import DateField, F, IntegerField, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from django.conf import settings

from apps.audit.services import record
from apps.authentication.drf import BusinessScopedViewSetMixin, business_api_view
from apps.reminders.models import Reminder
from apps.timelines.models import Timeline
from apps.timelines.services import record_case_event

from .demo_data import (
    normalize_template_item_orders,
    normalize_template_orders,
    seed_case_checklist_demo_data,
    seed_standard_case_checklist_templates,
    seed_standard_checklist_item_presets,
)
from .models import (
    AcquisitionPlacePreset,
    Case,
    CaseApplicationCategory,
    CaseChecklistItem,
    CaseChecklistTemplate,
    CaseChecklistTemplateItem,
    CaseStatusSetting,
    CaseTypeMaster,
    ChecklistItemPreset,
    ResponsiblePartyPreset,
)
from .serializers import (
    AcquisitionPlacePresetSerializer,
    CaseApplicationCategorySerializer,
    CaseChecklistItemSerializer,
    CaseChecklistDeletionHistorySerializer,
    CaseChecklistTemplateItemSerializer,
    CaseChecklistTemplateSerializer,
    CaseSerializer,
    CaseStatusSettingSerializer,
    CaseTypeMasterSerializer,
    ChecklistItemPresetSerializer,
    ResponsiblePartyPresetSerializer,
)
from .status_service import (
    CaseStatusChangeError,
    change_case_registration_status,
    change_case_status,
    get_required_checklist_progress,
    update_case_progress_info,
)
from .utils import apply_checklist_template_to_case, generate_case_number
from .work_service import (
    CaseWorkError,
    complete_next_action,
    end_waiting,
    record_payment_link,
    set_next_action,
    start_waiting,
)


class ActiveOrderingMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active in ['true', '1']:
            queryset = queryset.filter(is_active=True)
        elif is_active in ['false', '0']:
            queryset = queryset.filter(is_active=False)
        ordering = self.request.query_params.get('ordering')
        if ordering:
            queryset = queryset.order_by(ordering)
        return queryset


class CaseTypeMasterViewSet(BusinessScopedViewSetMixin, ActiveOrderingMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = CaseTypeMaster.objects.all()
    serializer_class = CaseTypeMasterSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.cases.exists():
            return Response({'detail': '使用中の案件種別は削除できません。無効化してください。'}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


class CaseApplicationCategoryViewSet(BusinessScopedViewSetMixin, ActiveOrderingMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = CaseApplicationCategory.objects.all()
    serializer_class = CaseApplicationCategorySerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.cases.exists():
            return Response({'detail': '使用中の申請区分は削除できません。無効化してください。'}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


class CaseStatusSettingViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = CaseStatusSetting.objects.all()
    serializer_class = CaseStatusSettingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        is_visible = self.request.query_params.get('is_visible')
        if is_visible in ['true', '1']:
            queryset = queryset.filter(is_visible=True)
        elif is_visible in ['false', '0']:
            queryset = queryset.filter(is_visible=False)
        ordering = self.request.query_params.get('ordering')
        if ordering:
            queryset = queryset.order_by(ordering)
        return queryset


class AcquisitionPlacePresetViewSet(BusinessScopedViewSetMixin, ActiveOrderingMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = AcquisitionPlacePreset.objects.all()
    serializer_class = AcquisitionPlacePresetSerializer


class ResponsiblePartyPresetViewSet(BusinessScopedViewSetMixin, ActiveOrderingMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = ResponsiblePartyPreset.objects.all()
    serializer_class = ResponsiblePartyPresetSerializer


class ChecklistItemPresetPagination(PageNumberPagination):
    page_size = 200
    page_size_query_param = 'page_size'
    max_page_size = 500


class ChecklistItemPresetViewSet(BusinessScopedViewSetMixin, ActiveOrderingMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = ChecklistItemPreset.objects.all()
    serializer_class = ChecklistItemPresetSerializer
    pagination_class = ChecklistItemPresetPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        if not settings.ENABLE_DEV_TOOLS:
            return Response({'detail': 'この機能は本番環境では無効です（管理コマンドを使用）。'}, status=status.HTTP_404_NOT_FOUND)
        result = seed_standard_checklist_item_presets()
        return Response(result, status=status.HTTP_201_CREATED)


class CaseChecklistPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CaseChecklistDeletionHistoryPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


def add_months(target_date, month_delta):
    month_index = target_date.month - 1 + month_delta
    year = target_date.year + month_index // 12
    month = month_index % 12 + 1
    month_last_days = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(target_date.day, month_last_days[month - 1])
    return date(year, month, day)


def reminder_datetime(target_date):
    return timezone.make_aware(datetime.combine(target_date, time(9, 0)))


def build_auto_note(lines):
    return '\n'.join([*lines, '自動作成：true'])


class CaseViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    """案件。範囲は担当者（responsible_employee）で決まる：本人担当のみ／case_view_all で
    全件閲覧／case_change_all で担当外・未割当の変更。専用 action はすべて「変更」扱い。"""

    access_resource = 'case'
    queryset = Case.objects.select_related(
        'customer',
        'company',
        'responsible_employee',
    ).prefetch_related('tasks__responsible_employee')
    serializer_class = CaseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        view = self.request.query_params.get('view')
        if view == 'incomplete':
            queryset = queryset.filter(
                registration_status=Case.REGISTRATION_STATUS_ACTIVE,
            ).exclude(status=Case.STATUS_COMPLETED)
        elif view == 'completed':
            queryset = queryset.filter(status=Case.STATUS_COMPLETED)
        registration_status = self.request.query_params.get('registration_status')
        if view not in {'incomplete', 'completed', 'all'} and registration_status in {
            Case.REGISTRATION_STATUS_ACTIVE,
            Case.REGISTRATION_STATUS_INACTIVE,
            Case.REGISTRATION_STATUS_ARCHIVED,
        }:
            queryset = queryset.filter(registration_status=registration_status)
        status_filter = self.request.query_params.get('status')
        valid_statuses = {choice[0] for choice in Case.STATUS_CHOICES}
        if status_filter in valid_statuses:
            queryset = queryset.filter(status=status_filter)
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return self.apply_work_ordering(queryset, view)

    def perform_update(self, serializer):
        previous_responsible_id = serializer.instance.responsible_employee_id
        super().perform_update(serializer)
        instance = serializer.instance
        policy = self.business_policy
        if instance.responsible_employee_id != previous_responsible_id:
            record(
                module='cases', action='case_reassign', request=self.request, obj=instance,
                changes={'responsible_employee_id': {'from': previous_responsible_id, 'to': instance.responsible_employee_id}},
                via_permission=self.access_rule.via_permission(policy, 'change', instance),
            )
        elif previous_responsible_id != policy.employee_id:
            record(module='cases', action='case_change_other', request=self.request, obj=instance,
                   via_permission='cases.case_change_all')

    def apply_work_ordering(self, queryset, view):
        priority = DbCase(
            When(status=Case.STATUS_ADDITIONAL_DOCUMENTS, then=Value(10)),
            When(status=Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED, then=Value(20)),
            When(status=Case.STATUS_APPLIED, then=Value(30)),
            When(status=Case.STATUS_COLLECTING_DOCUMENTS, then=Value(40)),
            When(status=Case.STATUS_APPROVED, then=Value(50)),
            When(status=Case.STATUS_REJECTED, then=Value(60)),
            When(status=Case.STATUS_WITHDRAWN, then=Value(70)),
            When(status=Case.STATUS_COMPLETED, then=Value(80)),
            default=Value(999),
            output_field=IntegerField(),
        )
        due_date = DbCase(
            When(status=Case.STATUS_ADDITIONAL_DOCUMENTS, then=F('additional_documents_requested_at')),
            When(status=Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED, then=F('additional_documents_submitted_at')),
            When(status=Case.STATUS_APPLIED, then=F('applied_at')),
            When(status=Case.STATUS_COLLECTING_DOCUMENTS, then=F('status_changed_at')),
            When(status__in=[Case.STATUS_APPROVED, Case.STATUS_REJECTED], then=F('result_received_at')),
            When(status=Case.STATUS_WITHDRAWN, then=F('withdrawn_at')),
            When(status=Case.STATUS_COMPLETED, then=F('completed_at')),
            default=F('updated_at'),
            output_field=DateField(),
        )
        progress_start = DbCase(
            When(status=Case.STATUS_CONSULTATION, then=F('consulted_at')),
            When(status=Case.STATUS_ACCEPTED, then=F('accepted_at')),
            When(status=Case.STATUS_COLLECTING_DOCUMENTS, then=F('document_collection_started_at')),
            When(status=Case.STATUS_PREPARING_DOCUMENTS, then=F('documents_completed_at')),
            When(status=Case.STATUS_READY_TO_APPLY, then=F('application_ready_at')),
            When(status=Case.STATUS_APPLIED, then=F('applied_at')),
            When(status=Case.STATUS_UNDER_REVIEW, then=F('review_started_at')),
            When(status=Case.STATUS_ADDITIONAL_DOCUMENTS, then=F('additional_documents_requested_at')),
            When(status=Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED, then=F('additional_documents_submitted_at')),
            When(status__in=[Case.STATUS_APPROVED, Case.STATUS_REJECTED], then=F('result_received_at')),
            When(status=Case.STATUS_COMPLETED, then=F('completed_at')),
            default=F('status_changed_at'),
            output_field=DateField(),
        )
        end_date = Coalesce('completed_at', 'status_changed_at')
        queryset = queryset.annotate(
            work_priority=priority,
            attention_due_date=due_date,
            progress_start_order=progress_start,
            end_date_order=end_date,
        )
        if view == 'completed':
            return queryset.order_by('-end_date_order', '-updated_at', '-id')
        return queryset.order_by('work_priority', '-attention_due_date', '-updated_at', '-id')

    def _status_change_response(self, result):
        return Response({
            'case_id': result.case_id,
            'previous_status': result.previous_status,
            'new_status': result.new_status,
            'warnings': result.warnings,
            'timeline_created': result.timeline_created,
            'forced': result.forced,
            'event': result.event,
        })

    def _status_change_error_response(self, exc):
        payload = {
            'detail': exc.detail,
            'warnings': exc.warnings,
            'requires_force': exc.requires_force,
        }
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    def _build_regenerated_case_number(self, case):
        if not case.case_type_master or not case.application_category:
            raise DjangoValidationError('案件種別と申請区分を設定してください。')
        return generate_case_number(
            case_type_master=case.case_type_master,
            application_category=case.application_category,
            customer=case.customer,
        )

    @action(detail=True, methods=['get'], url_path='preview-regenerate-case-number')
    def preview_regenerate_case_number(self, request, pk=None):
        case = self.get_object()
        try:
            new_number = self._build_regenerated_case_number(case)
        except DjangoValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'current_case_number': case.case_number,
            'new_case_number': new_number,
        })

    @action(detail=True, methods=['post'], url_path='regenerate-case-number')
    def regenerate_case_number(self, request, pk=None):
        case = self.get_object()
        old_number = case.case_number
        try:
            new_number = self._build_regenerated_case_number(case)
        except DjangoValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        if Case.objects.exclude(pk=case.pk).filter(case_number=new_number).exists():  # access-reviewed: 案件番号の一意性確認
            return Response({'detail': '同じ案件番号が既に存在します。'}, status=status.HTTP_400_BAD_REQUEST)
        case.case_number = new_number
        case.save(update_fields=['case_number', 'updated_at'])
        Timeline.objects.create(  # access-reviewed: 権限確認済み案件への業務記録
            case=case,
            title='案件番号変更',
            content=f'旧番号：{old_number}\n新番号：{new_number}',
        )
        return Response(self.get_serializer(case).data)

    # --- Next Action / 待機 / 入金の記録（P1）。いずれも「変更」権限が必要（BusinessAccessPolicy）。
    def _work_error(self, exc):
        payload = {'detail': exc.detail}
        if exc.field:
            payload[exc.field] = [exc.detail]
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)

    def _work_response(self, case):
        case.refresh_from_db()
        return Response(self.get_serializer(case).data)

    @action(detail=True, methods=['post'], url_path='next-action')
    def next_action(self, request, pk=None):
        case = self.get_object()
        assignee = None
        assignee_id = request.data.get('assignee')
        if assignee_id not in (None, ''):
            from apps.employees.models import Employee

            assignee = Employee.objects.filter(pk=assignee_id).first()
            if assignee is None:
                return Response({'assignee': ['担当者が見つかりません。']}, status=status.HTTP_400_BAD_REQUEST)
        try:
            set_next_action(
                case,
                text=request.data.get('next_action'),
                assignee=assignee,
                due_at=request.data.get('next_action_due_at'),
                blocked_reason=request.data.get('blocked_reason') or '',
                actor=request.user,
                request=request,
            )
        except CaseWorkError as exc:
            return self._work_error(exc)
        return self._work_response(case)

    @action(detail=True, methods=['post'], url_path='next-action/complete')
    def complete_next_action(self, request, pk=None):
        case = self.get_object()
        try:
            complete_next_action(case, note=request.data.get('note') or '', actor=request.user, request=request)
        except CaseWorkError as exc:
            return self._work_error(exc)
        return self._work_response(case)

    @action(detail=True, methods=['post'], url_path='waiting/start')
    def start_waiting(self, request, pk=None):
        case = self.get_object()
        try:
            start_waiting(
                case,
                reason=request.data.get('waiting_reason'),
                note=request.data.get('waiting_note') or '',
                until=request.data.get('waiting_until'),
                actor=request.user,
                request=request,
            )
        except CaseWorkError as exc:
            return self._work_error(exc)
        return self._work_response(case)

    @action(detail=True, methods=['post'], url_path='waiting/end')
    def end_waiting(self, request, pk=None):
        case = self.get_object()
        try:
            end_waiting(case, note=request.data.get('note') or '', actor=request.user, request=request)
        except CaseWorkError as exc:
            return self._work_error(exc)
        return self._work_response(case)

    @action(detail=True, methods=['post'], url_path='payment-note')
    def payment_note(self, request, pk=None):
        """入金を案件経過に記録するだけ（会計データは作らない）。会計への登録は会計モジュールで行う。"""
        case = self.get_object()
        try:
            timeline = record_payment_link(
                case,
                amount=request.data.get('amount'),
                received_on=request.data.get('received_on'),
                note=request.data.get('note') or '',
                reference=request.data.get('reference') or '',
                actor=request.user,
                request=request,
            )
        except CaseWorkError as exc:
            return self._work_error(exc)
        return Response({'timeline_id': timeline.id}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='change-status')
    def change_status(self, request, pk=None):
        case = self.get_object()
        try:
            result = change_case_status(
                case,
                request.data.get('new_status'),
                changed_by=request.user,
                change_date=request.data.get('change_date'),
                note=request.data.get('note') or '',
                force=bool(request.data.get('force')),
                source='manual',
                next_action=request.data.get('next_action'),
                next_action_due_at=request.data.get('next_action_due_at'),
                status_payload=request.data.get('status_payload') or {},
            )
        except (CaseStatusChangeError, ValueError) as exc:
            if isinstance(exc, CaseStatusChangeError):
                return self._status_change_error_response(exc)
            return Response({'detail': '変更日が正しくありません。'}, status=status.HTTP_400_BAD_REQUEST)
        record(module='cases', action='case_status_changed', request=request, obj=case,
               extra={'previous': result.previous_status, 'new': result.new_status, 'forced': result.forced})
        return self._status_change_response(result)

    @action(detail=True, methods=['post'], url_path='change-registration-status')
    def change_registration_status(self, request, pk=None):
        case = self.get_object()
        try:
            result = change_case_registration_status(
                case,
                request.data.get('new_status'),
                changed_by=request.user,
                change_date=request.data.get('change_date'),
                note=request.data.get('note') or '',
                force=bool(request.data.get('force')),
                source='manual',
            )
        except (CaseStatusChangeError, ValueError) as exc:
            if isinstance(exc, CaseStatusChangeError):
                return self._status_change_error_response(exc)
            return Response({'detail': '変更日が正しくありません。'}, status=status.HTTP_400_BAD_REQUEST)
        return self._status_change_response(result)

    @action(detail=True, methods=['post'], url_path='progress-info')
    def progress_info(self, request, pk=None):
        case = self.get_object()
        try:
            update_case_progress_info(
                case,
                request.data,
                changed_by=request.user,
                note=request.data.get('note') or '',
            )
        except CaseStatusChangeError as exc:
            return Response({'detail': exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        case.refresh_from_db()
        return Response(self.get_serializer(case).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        case = self.get_object()
        reason = (request.data.get('reason') or '').strip()

        if case.status in [Case.STATUS_WITHDRAWN, Case.STATUS_COMPLETED]:
            return Response(
                {'detail': 'この案件は中止できません。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not reason:
            return Response(
                {'reason': '中止理由を入力してください。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            change_case_status(
                case,
                Case.STATUS_WITHDRAWN,
                changed_by=request.user,
                note=reason,
                force=True,
                source='cancel',
            )

        case.refresh_from_db()
        serializer = self.get_serializer(case)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='generate-reminders')
    def generate_reminders(self, request, pk=None):
        case = self.get_object()
        candidates = []

        def add_candidate(title, remind_date, note_lines):
            if not remind_date:
                return
            candidates.append({
                'title': title,
                'remind_at': reminder_datetime(remind_date),
                'note': build_auto_note(note_lines),
            })

        customer = case.customer
        residence_rules = [
            ('3ヶ月前', -3),
            ('2ヶ月前', -2),
            ('1ヶ月前', -1),
        ]
        passport_rules = [
            ('6ヶ月前', -6),
            ('3ヶ月前', -3),
            ('1ヶ月前', -1),
        ]

        def add_residence_candidates(target_type, name, expiry_date):
            for label, month_delta in residence_rules:
                add_candidate(
                    f'{name} 在留期限{label}',
                    add_months(expiry_date, month_delta) if expiry_date else None,
                    [
                        f'対象：{target_type}',
                        f'氏名：{name}',
                        '期限種別：在留期限',
                        f'基準日：{expiry_date}',
                    ],
                )
            if expiry_date:
                add_candidate(
                    f'{name} 在留期限2週間前',
                    expiry_date - timedelta(days=14),
                    [
                        f'対象：{target_type}',
                        f'氏名：{name}',
                        '期限種別：在留期限',
                        f'基準日：{expiry_date}',
                    ],
                )

        def add_passport_candidates(target_type, name, expiry_date):
            for label, month_delta in passport_rules:
                add_candidate(
                    f'{name} パスポート期限{label}',
                    add_months(expiry_date, month_delta) if expiry_date else None,
                    [
                        f'対象：{target_type}',
                        f'氏名：{name}',
                        '期限種別：パスポート期限',
                        f'基準日：{expiry_date}',
                    ],
                )

        for label, month_delta in residence_rules:
            add_candidate(
                f'{customer.name} 在留期限{label}',
                add_months(customer.residence_expiry, month_delta) if customer.residence_expiry else None,
                [
                    '対象：顧客',
                    f'氏名：{customer.name}',
                    '期限種別：在留期限',
                    f'基準日：{customer.residence_expiry}',
                ],
            )
        if customer.residence_expiry:
            add_candidate(
                f'{customer.name} 在留期限2週間前',
                customer.residence_expiry - timedelta(days=14),
                [
                    '対象：顧客',
                    f'氏名：{customer.name}',
                    '期限種別：在留期限',
                    f'基準日：{customer.residence_expiry}',
                ],
            )

        for label, month_delta in passport_rules:
            add_candidate(
                f'{customer.name} パスポート期限{label}',
                add_months(customer.passport_expiry, month_delta) if customer.passport_expiry else None,
                [
                    '対象：顧客',
                    f'氏名：{customer.name}',
                    '期限種別：パスポート期限',
                    f'基準日：{customer.passport_expiry}',
                ],
            )

        for family_member in customer.family_members.select_related('family_customer').all():
            person = family_member.family_customer
            if person:
                add_residence_candidates('家族', person.name, person.residence_expiry)
                add_passport_candidates('家族', person.name, person.passport_expiry)
            else:
                # family_customer 未紐付けの旧仕様レコード。パスポート期限はこの段階のデータに存在しない。
                add_residence_candidates('家族', family_member.name, family_member.residence_expiry)

        if case.company:
            for staff_member in case.company.staff_members.select_related('customer').all():
                person = staff_member.customer
                if not person:
                    continue
                add_residence_candidates('会社従業員', person.name, person.residence_expiry)
                add_passport_candidates('会社従業員', person.name, person.passport_expiry)

        if case.company and case.company.fiscal_month:
            fiscal_month = int(case.company.fiscal_month)
            today = timezone.localdate()
            fiscal_date = date(today.year, fiscal_month, 1)
            if fiscal_date < today:
                fiscal_date = date(today.year + 1, fiscal_month, 1)
            for label, month_delta in [
                ('2ヶ月前', -2),
                ('1ヶ月前', -1),
                ('当月', 0),
            ]:
                add_candidate(
                    f'{case.company.name} 決算月{label}',
                    add_months(fiscal_date, month_delta),
                    [
                        '対象：会社',
                        f'会社名：{case.company.name}',
                        '期限種別：決算月',
                        f'基準月：{case.company.fiscal_month}月',
                    ],
                )

        created_ids = []
        skipped_count = 0
        with transaction.atomic():
            for candidate in candidates:
                exists = Reminder.objects.filter(  # access-reviewed: 権限確認済み案件の重複確認
                    case=case,
                    title=candidate['title'],
                    remind_at=candidate['remind_at'],
                ).exists()
                if exists:
                    skipped_count += 1
                    continue
                reminder = Reminder.objects.create(  # access-reviewed: 権限確認済み案件への作成
                    case=case,
                    title=candidate['title'],
                    remind_at=candidate['remind_at'],
                    note=candidate['note'],
                    is_done=False,
                )
                created_ids.append(reminder.id)

        return Response({
            'created_count': len(created_ids),
            'skipped_count': skipped_count,
            'reminders': created_ids,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='apply-checklist-template')
    def apply_checklist_template(self, request, pk=None):
        case = self.get_object()
        template_id = request.data.get('template_id')

        if not template_id:
            return Response(
                {'template_id': 'テンプレートを選択してください。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template = CaseChecklistTemplate.objects.prefetch_related('items').get(
                pk=template_id,
                is_active=True,
            )
        except CaseChecklistTemplate.DoesNotExist:
            return Response(
                {'template_id': 'テンプレートが見つかりません。'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        mode = request.data.get('mode') or 'merge'
        if mode not in ('merge', 'replace'):
            return Response({'mode': 'merge または replace を指定してください。'}, status=status.HTTP_400_BAD_REQUEST)

        created_items = apply_checklist_template_to_case(case, template, mode=mode)
        serializer = CaseChecklistItemSerializer(created_items, many=True)
        return Response(
            {'created': serializer.data, 'created_count': len(created_items), 'mode': mode},
            status=status.HTTP_201_CREATED,
        )


class CaseChecklistTemplateViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = CaseChecklistTemplate.objects.prefetch_related('items')
    serializer_class = CaseChecklistTemplateSerializer
    pagination_class = CaseChecklistPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(deleted_at__isnull=True)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        is_active = self.request.query_params.get('is_active')
        if is_active in ['true', '1']:
            queryset = queryset.filter(is_active=True)
        if is_active in ['false', '0']:
            queryset = queryset.filter(is_active=False)
        ordering = self.request.query_params.get('ordering')
        if ordering in ['sort_order', '-sort_order', 'name', '-name', 'updated_at', '-updated_at']:
            queryset = queryset.order_by(ordering, 'id')
        return queryset

    def perform_destroy(self, instance):
        self._delete_template(instance)

    def _delete_template(self, instance):
        now = timezone.now()
        with transaction.atomic():
            instance.deleted_at = now
            instance.save(update_fields=['deleted_at', 'updated_at'])
            instance.items.filter(deleted_at__isnull=True).update(
                deleted_at=now,
                deleted_with_template=True,
                updated_at=now,
            )
            normalize_template_orders()

    @action(detail=True, methods=['post'], url_path='delete')
    def soft_delete(self, request, pk=None):
        template = self.get_object()
        self._delete_template(template)
        return Response({'detail': '削除しました。'})

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        template = CaseChecklistTemplate.objects.get(pk=pk)
        with transaction.atomic():
            template.deleted_at = None
            template.save(update_fields=['deleted_at', 'updated_at'])
            template.items.filter(deleted_with_template=True).update(
                deleted_at=None,
                deleted_with_template=False,
                updated_at=timezone.now(),
            )
            normalize_template_item_orders(template)
            normalize_template_orders()
        serializer = self.get_serializer(template)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        if not settings.ENABLE_DEV_TOOLS:
            return Response({'detail': 'この機能は本番環境では無効です（管理コマンドを使用）。'}, status=status.HTTP_404_NOT_FOUND)
        result = seed_standard_case_checklist_templates()
        return Response(result, status=status.HTTP_201_CREATED)


class CaseChecklistTemplateItemViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = CaseChecklistTemplateItem.objects.select_related('template')
    serializer_class = CaseChecklistTemplateItemSerializer
    pagination_class = CaseChecklistPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(deleted_at__isnull=True, template__deleted_at__isnull=True)
        template_id = self.request.query_params.get('template')
        if template_id:
            queryset = queryset.filter(template_id=template_id)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        is_active = self.request.query_params.get('is_active')
        if is_active in ['true', '1']:
            queryset = queryset.filter(is_active=True)
        if is_active in ['false', '0']:
            queryset = queryset.filter(is_active=False)
        ordering = self.request.query_params.get('ordering')
        if ordering in ['sort_order', '-sort_order', 'category', '-category', 'name', '-name', 'updated_at', '-updated_at']:
            queryset = queryset.order_by(ordering, 'id')
        return queryset

    def perform_create(self, serializer):
        template = serializer.validated_data['template']
        max_sort_order = (
            CaseChecklistTemplateItem.objects
            .filter(template=template, deleted_at__isnull=True)
            .order_by('-sort_order', '-id')
            .values_list('sort_order', flat=True)
            .first()
        ) or 0
        item = serializer.save(sort_order=max_sort_order + 1)
        normalize_template_item_orders(template)
        item.refresh_from_db()

    @action(detail=False, methods=['get'])
    def options(self, request):
        queryset = CaseChecklistTemplateItem.objects.filter(
            deleted_at__isnull=True,
            template__deleted_at__isnull=True,
        )
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        categories = list(
            queryset.exclude(category='')
            .order_by('category')
            .values_list('category', flat=True)
            .distinct()
        )
        names_queryset = queryset.exclude(name='').order_by('category', 'name').values('category', 'name').distinct()
        names = [
            {'category': row['category'] or '', 'name': row['name']}
            for row in names_queryset
        ]
        return Response({'categories': categories, 'items': names})

    @action(detail=False, methods=['get'], url_path='name-suggestions')
    def name_suggestions(self, request):
        query = (request.query_params.get('q') or '').strip()
        queryset = CaseChecklistTemplateItem.objects.filter(
            deleted_at__isnull=True,
            template__deleted_at__isnull=True,
        ).exclude(name='')
        if query:
            queryset = queryset.filter(name__icontains=query)

        names = []
        seen = set()
        for name in queryset.order_by('-updated_at').values_list('name', flat=True)[:200]:
            normalized = ' '.join(name.split())
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(normalized)

        if query:
            query_lower = query.lower()

            def sort_key(name):
                name_lower = name.lower()
                if name_lower == query_lower:
                    rank = 0
                elif name_lower.startswith(query_lower):
                    rank = 1
                else:
                    rank = 2
                return (rank, name_lower)

            names = sorted(names, key=sort_key)

        return Response([{'value': name} for name in names[:20]])

    def perform_destroy(self, instance):
        self._delete_item(instance)

    def _normalize_and_get_position(self, items, item_id):
        now = timezone.now()
        updates = []
        position = 1
        for index, item in enumerate(items, start=1):
            if item.id == item_id:
                position = index
            if item.sort_order != index:
                item.sort_order = index
                item.updated_at = now
                updates.append(item)
        if updates:
            CaseChecklistTemplateItem.objects.bulk_update(updates, ['sort_order', 'updated_at'])
        return position

    def _move_item(self, instance, direction):
        with transaction.atomic():
            items = list(
                CaseChecklistTemplateItem.objects
                .select_for_update()
                .filter(template=instance.template, deleted_at__isnull=True)
                .order_by('sort_order', 'id')
            )
            current_index = next((index for index, item in enumerate(items) if item.id == instance.id), None)
            if current_index is None:
                return {
                    'success': False,
                    'message': '対象項目が見つかりません。',
                    'position': 1,
                    'total': len(items),
                }

            target_index = current_index + direction
            if target_index < 0:
                position = self._normalize_and_get_position(items, instance.id)
                return {
                    'success': False,
                    'message': 'これ以上上へ移動できません。',
                    'position': position,
                    'total': len(items),
                }
            if target_index >= len(items):
                position = self._normalize_and_get_position(items, instance.id)
                return {
                    'success': False,
                    'message': 'これ以上下へ移動できません。',
                    'position': position,
                    'total': len(items),
                }

            item = items.pop(current_index)
            items.insert(target_index, item)
            position = self._normalize_and_get_position(items, instance.id)
            return {
                'success': True,
                'message': '上へ移動しました。' if direction < 0 else '下へ移動しました。',
                'position': position,
                'total': len(items),
            }

    @action(detail=True, methods=['post'], url_path='move-up')
    def move_up(self, request, pk=None):
        item = self.get_object()
        return Response(self._move_item(item, -1))

    @action(detail=True, methods=['post'], url_path='move-down')
    def move_down(self, request, pk=None):
        item = self.get_object()
        return Response(self._move_item(item, 1))

    def _delete_item(self, instance):
        instance.deleted_at = timezone.now()
        instance.deleted_with_template = False
        instance.save(update_fields=['deleted_at', 'deleted_with_template', 'updated_at'])
        normalize_template_item_orders(instance.template)

    @action(detail=True, methods=['post'], url_path='delete')
    def soft_delete(self, request, pk=None):
        item = self.get_object()
        self._delete_item(item)
        return Response({'detail': '削除しました。'})

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        item = CaseChecklistTemplateItem.objects.select_related('template').get(pk=pk)
        if item.template.deleted_at:
            return Response(
                {'detail': '所属テンプレートが削除されています。先にテンプレートを復元してください。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.deleted_at = None
        item.deleted_with_template = False
        item.save(update_fields=['deleted_at', 'deleted_with_template', 'updated_at'])
        normalize_template_item_orders(item.template)
        serializer = self.get_serializer(item)
        return Response(serializer.data)


class CaseChecklistItemViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'case_checklist_item'
    queryset = CaseChecklistItem.objects.select_related('case', 'source_template_item', 'completed_by')
    serializer_class = CaseChecklistItemSerializer
    pagination_class = CaseChecklistPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        case_id = self.request.query_params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        status_value = self.request.query_params.get('status')
        if status_value == 'completed':
            queryset = queryset.filter(is_completed=True)
        if status_value == 'pending':
            queryset = queryset.filter(is_completed=False)
        ordering = self.request.query_params.get('ordering')
        if ordering in ['sort_order', '-sort_order', 'category', '-category', 'name', '-name', 'updated_at', '-updated_at']:
            queryset = queryset.order_by(ordering, 'id')
        return queryset

    def _progress_payload(self, case):
        progress = get_required_checklist_progress(case)
        return {
            'required_items_total': progress['required_items_total'],
            'required_items_completed': progress['required_items_completed'],
            'required_items_remaining': progress['required_items_remaining'],
            'required_items_progress_percent': progress['required_items_progress_percent'],
            'all_required_items_completed': progress['all_required_items_completed'],
            'suggested_case_status': progress['suggested_case_status'],
            'suggestion_message': progress['suggestion_message'],
        }

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        item = CaseChecklistItem.objects.get(pk=response.data['id'])  # access-reviewed: 直前に作成した自分の項目
        response.data['progress_summary'] = self._progress_payload(item.case)
        return response

    def update(self, request, *args, **kwargs):
        was_completed = self.get_object().is_completed
        response = super().update(request, *args, **kwargs)
        item = CaseChecklistItem.objects.select_related('case').get(pk=response.data['id'])  # access-reviewed: 直前に更新した項目
        self._record_completion_event(item, was_completed, request)
        response.data['progress_summary'] = self._progress_payload(item.case)
        return response

    def partial_update(self, request, *args, **kwargs):
        was_completed = self.get_object().is_completed
        response = super().partial_update(request, *args, **kwargs)
        item = CaseChecklistItem.objects.select_related('case').get(pk=response.data['id'])  # access-reviewed: 直前に更新した項目
        self._record_completion_event(item, was_completed, request)
        response.data['progress_summary'] = self._progress_payload(item.case)
        return response

    def _record_completion_event(self, item, was_completed, request):
        if item.is_completed and not was_completed:
            record_case_event(
                item.case,
                Timeline.EVENT_CHECKLIST_COMPLETED,
                f'資料・タスク完了：{item.name}',
                actor=getattr(request, 'user', None),
                metadata={'checklist_item_id': item.id, 'category': item.category},
            )


@business_api_view(['POST'], 'diagnostics')
def seed_case_checklist_demo_view(request):
    # 開発用：本番では URL 自体を登録しない（api/urls.py）。
    result = seed_case_checklist_demo_data()
    return Response(result, status=status.HTTP_201_CREATED)


@business_api_view(['GET'], 'case_settings')
def case_checklist_deletion_history(request):
    templates = [
        {
            'id': template.id,
            'object_type': 'template',
            'name': template.name,
            'template_name': '',
            'deleted_at': template.deleted_at,
            'can_restore': True,
        }
        for template in CaseChecklistTemplate.objects.filter(deleted_at__isnull=False)
    ]
    items = [
        {
            'id': item.id,
            'object_type': 'template_item',
            'name': item.name,
            'template_name': item.template.name,
            'deleted_at': item.deleted_at,
            'can_restore': item.template.deleted_at is None,
        }
        for item in CaseChecklistTemplateItem.objects.select_related('template').filter(deleted_at__isnull=False)
    ]
    rows = sorted([*templates, *items], key=lambda row: row['deleted_at'], reverse=True)
    latest_deleted_at = rows[0]['deleted_at'] if rows else None
    paginator = CaseChecklistDeletionHistoryPagination()
    page = paginator.paginate_queryset(rows, request)
    serializer = CaseChecklistDeletionHistorySerializer(page, many=True)
    response = paginator.get_paginated_response(serializer.data)
    response.data['latest_deleted_at'] = latest_deleted_at
    return response
