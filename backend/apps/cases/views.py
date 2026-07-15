from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.reminders.models import Reminder
from apps.timelines.models import Timeline

from .demo_data import (
    normalize_template_item_orders,
    normalize_template_orders,
    seed_case_checklist_demo_data,
    seed_standard_case_checklist_templates,
)
from .models import Case, CaseChecklistItem, CaseChecklistTemplate, CaseChecklistTemplateItem
from .serializers import (
    CaseChecklistItemSerializer,
    CaseChecklistDeletionHistorySerializer,
    CaseChecklistTemplateItemSerializer,
    CaseChecklistTemplateSerializer,
    CaseSerializer,
)


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


class CaseViewSet(ModelViewSet):
    queryset = Case.objects.select_related(
        'customer',
        'company',
        'responsible_employee',
    ).prefetch_related('tasks__responsible_employee')
    serializer_class = CaseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        case = self.get_object()
        reason = (request.data.get('reason') or '').strip()

        if case.status in ['中止', '完了', Case.STATUS_COMPLETED]:
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
            case.status = '中止'
            case.save(update_fields=['status', 'updated_at'])
            Timeline.objects.create(
                case=case,
                title='案件中止',
                content=f'案件を中止しました。理由：{reason}',
                is_visible_to_client=False,
            )

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

        for family_member in customer.family_members.all():
            add_residence_candidates('家族', family_member.name, family_member.residence_expiry)
            add_passport_candidates('家族', family_member.name, getattr(family_member, 'passport_expiry', None))

        if case.company:
            for staff_member in case.company.staff_members.all():
                add_residence_candidates('会社従業員', staff_member.name, staff_member.residence_expiry)
                add_passport_candidates('会社従業員', staff_member.name, staff_member.passport_expiry)

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
                exists = Reminder.objects.filter(
                    case=case,
                    title=candidate['title'],
                    remind_at=candidate['remind_at'],
                ).exists()
                if exists:
                    skipped_count += 1
                    continue
                reminder = Reminder.objects.create(
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

        template_items = list(template.items.filter(is_active=True, deleted_at__isnull=True).order_by('sort_order', 'id'))
        current_max_order = (
            CaseChecklistItem.objects
            .filter(case=case)
            .order_by('-sort_order')
            .values_list('sort_order', flat=True)
            .first()
            or 0
        )

        created_items = []
        with transaction.atomic():
            for index, template_item in enumerate(template_items, start=1):
                created_items.append(CaseChecklistItem.objects.create(
                    case=case,
                    source_template_item=template_item,
                    category=template_item.category,
                    name=template_item.name,
                    item_type=template_item.item_type,
                    quantity=template_item.quantity,
                    unit=template_item.unit,
                    is_required=template_item.is_required,
                    note=template_item.description,
                    sort_order=current_max_order + index,
                ))

        serializer = CaseChecklistItemSerializer(created_items, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CaseChecklistTemplateViewSet(ModelViewSet):
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
        result = seed_standard_case_checklist_templates()
        return Response(result, status=status.HTTP_201_CREATED)


class CaseChecklistTemplateItemViewSet(ModelViewSet):
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


class CaseChecklistItemViewSet(ModelViewSet):
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


@api_view(['POST'])
def seed_case_checklist_demo_view(request):
    result = seed_case_checklist_demo_data()
    return Response(result, status=status.HTTP_201_CREATED)


@api_view(['GET'])
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
