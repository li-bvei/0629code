from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.reminders.models import Reminder
from apps.timelines.models import Timeline

from .models import Case
from .serializers import CaseSerializer


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
