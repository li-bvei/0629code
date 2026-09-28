import calendar
from datetime import date, timedelta

from django.db import IntegrityError
from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.access_rules import COMPANY_RULE, CUSTOMER_RULE
from apps.authentication.drf import BusinessAccessMixin, flush_link_events
from apps.cases.models import Case

from .models import ReceptionIdempotencyRecord
from .serializers import ReceptionSerializer

# 正常フローの途中離脱・終了状態。「進行中」の件数や次アクション集計からは除外する。
CLOSED_CASE_STATUSES = {
    Case.STATUS_COMPLETED,
    Case.STATUS_WITHDRAWN,
    Case.STATUS_REJECTED,
}

# ダッシュボードの進捗サマリー（詳細ページのステッパーと同じ6分類）。
DASHBOARD_STAGE_GROUPS = [
    ('preparation', '資料準備', [
        Case.STATUS_CONSULTATION,
        Case.STATUS_ACCEPTED,
        Case.STATUS_COLLECTING_DOCUMENTS,
        Case.STATUS_PREPARING_DOCUMENTS,
        Case.STATUS_READY_TO_APPLY,
    ]),
    ('applied', '申請済み', [Case.STATUS_APPLIED]),
    ('under_review', '審査中', [
        Case.STATUS_UNDER_REVIEW,
        Case.STATUS_ADDITIONAL_DOCUMENTS,
        Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED,
    ]),
    ('result', '許可 / 不許可', [Case.STATUS_APPROVED, Case.STATUS_REJECTED]),
    ('completed', '完了', [Case.STATUS_COMPLETED]),
]

# 「待機中」とみなす進捗（外部からの返答待ちで、こちらから動けない状態）。
# work_status フィールド導入前の暫定定義。
WAITING_CASE_STATUSES = {
    Case.STATUS_ADDITIONAL_DOCUMENTS,
    Case.STATUS_UNDER_REVIEW,
}

# 案件がこの状態になっていれば「もう動きが無い案件」とみなし、期限提醒には出さない
# （完了・取下げ・不許可）。審査中や書類対応中など、まだ進行中の案件は
# 期限が過ぎていても引き続き表示する。
TERMINAL_CASE_STATUSES = {
    Case.STATUS_COMPLETED,
    Case.STATUS_WITHDRAWN,
    Case.STATUS_REJECTED,
}


class ReceptionCreateView(BusinessAccessMixin, APIView):
    """新規受付の確定 API。

    フロントは1回の確定操作につき固定の request_id を送る（ボタン二重クリックや
    ネットワーク再試行での重複だけを想定しており、汎用の冪等機構ではない）。
    - 既に成功済みの request_id → 保存済みのレスポンスをそのまま返す（顧客・案件は増えない）。
    - 処理中（ほぼ同時に届いた重複リクエスト）→ 409 を返す。
    - 未指定 → 従来どおり毎回作成する（後方互換）。
    """

    access_resource = 'case'

    def get_access_action(self):
        return 'create'

    def _resolve_case_responsible(self, request):
        """案件を作る受付では担当者を必ず決める（未指定なら本人、他人指定は case_change_all のみ）。"""
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        case_data = data.get('case')
        if isinstance(case_data, dict) and case_data.get('case_type_master') and case_data.get('application_category'):
            case_data = dict(case_data)
            case_data['responsible_employee'] = self.access_rule.resolve_create_responsible_id(
                self.business_policy, case_data.get('responsible_employee'),
            )
            data['case'] = case_data
        return data

    def _check_existing_links(self, data):
        """受付で指定された既存の顧客・会社（本人・家族・代表者・会社）に受控関連規則を適用する。
        フロントの候補一覧ではなく、送られてきた実 ID を検査する。"""
        policy = self.business_policy
        customers = policy.queryset('customer', 'list')
        companies = policy.queryset('company', 'list')

        def check_customer(raw_id, via):
            if raw_id in (None, ''):
                return
            obj = customers.filter(pk=raw_id).first()
            CUSTOMER_RULE.check_link(policy, obj, via=via)

        check_customer(data.get('existing_customer_id'), 'reception.existing_customer_id')
        for index, member in enumerate(data.get('family_members') or []):
            if isinstance(member, dict):
                check_customer(member.get('customer'), f'reception.family_members[{index}].customer')
        company_data = data.get('company')
        if isinstance(company_data, dict):
            check_customer(company_data.get('representative_customer'), 'reception.company.representative_customer')
        existing_company_id = data.get('existing_company_id')
        if existing_company_id not in (None, ''):
            COMPANY_RULE.check_link(policy, companies.filter(pk=existing_company_id).first(),
                                    via='reception.existing_company_id')

    def post(self, request):
        request_id = (request.data.get('request_id') or '').strip()
        payload = self._resolve_case_responsible(request)
        try:
            self._check_existing_links(payload)
        except Exception:
            flush_link_events(request, self.business_policy)
            raise

        if request_id:
            existing = ReceptionIdempotencyRecord.objects.filter(request_id=request_id).first()
            if existing:
                if existing.response is None:
                    return Response(
                        {'detail': '同じ内容の受付処理が実行中です。しばらくしてから確認してください。'},
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response(existing.response, status=status.HTTP_201_CREATED)
            try:
                ReceptionIdempotencyRecord.objects.create(request_id=request_id, response=None)
            except IntegrityError:
                return Response(
                    {'detail': '同じ内容の受付処理が実行中です。しばらくしてから確認してください。'},
                    status=status.HTTP_409_CONFLICT,
                )

        try:
            serializer = ReceptionSerializer(data=payload, context={'request': request})
            serializer.is_valid(raise_exception=True)
            result = serializer.save()
        except Exception:
            if request_id:
                # 失敗時はプレースホルダを消し、同じ request_id での再試行を許可する。
                ReceptionIdempotencyRecord.objects.filter(request_id=request_id, response__isnull=True).delete()
            raise

        if request_id:
            ReceptionIdempotencyRecord.objects.filter(request_id=request_id).update(response=result)
        flush_link_events(request, self.business_policy)
        return Response(result, status=status.HTTP_201_CREATED)


def build_dashboard_deadlines(today, include_dismissed=False, *, policy):
    """ダッシュボードの期限提醒一覧を計算する。

    include_dismissed=True のときは、非表示（DismissedDeadline）・案件終了による
    自動除外のフィルタを一切かけず、期限日ベースの生データをすべて返す
    （一括非表示アクションが「今まさに表示されている過期項目」を漏れなく拾うために使う）。
    """
    items = []
    # 期限は利用者が詳細を見られる顧客・会社だけを対象にする（BusinessAccessPolicy）。
    cases = policy.queryset('case', 'list')
    customers = policy.queryset('customer', 'detail')
    companies = policy.queryset('company', 'detail')
    family_members = policy.queryset('family_member', 'list')
    company_staff = policy.queryset('company_staff', 'list')

    dismissed_map = {}
    if not include_dismissed:
        dismissed_map = {
            (row['source_type'], row['source_id'], row['deadline_type'], row['deadline_date']): row['created_at']
            for row in policy.queryset('dismissed_deadline', 'list').values(
                'source_type', 'source_id', 'deadline_type', 'deadline_date', 'created_at',
            )
        }

    # 非表示にした後で「その人物／会社について新しい案件が作られた」場合は、
    # 非表示の効力を失わせて再度表示する（"直到我新建关于他的新项目"）。
    customer_latest_case_at = dict(
        cases.order_by().values('customer_id').annotate(latest=Max('created_at')).values_list('customer_id', 'latest')
    )
    company_latest_case_at = dict(
        cases.exclude(company__isnull=True).order_by()
        .values('company_id').annotate(latest=Max('created_at')).values_list('company_id', 'latest')
    )
    family_member_head_customer_id = dict(family_members.values_list('id', 'customer_id'))

    def dismissal_is_stale(target_type, target_id, dismissed_at):
        if target_type == 'customer':
            latest = customer_latest_case_at.get(target_id)
        elif target_type == 'company':
            latest = company_latest_case_at.get(target_id)
        elif target_type == 'family_member':
            head_id = family_member_head_customer_id.get(target_id)
            latest = customer_latest_case_at.get(head_id) if head_id else None
        else:
            latest = None
        return latest is not None and latest > dismissed_at

    def latest_case(queryset):
        # 案件番号の表示も利用者の案件範囲に限る。
        return (
            queryset.filter(pk__in=cases.values('pk'))
            .select_related('customer', 'company').order_by('-updated_at', '-id').first()
        )

    def case_data(case):
        if case is None:
            return {
                'case_id': None,
                'case_number': '-',
                'case_type': '-',
            }
        return {
            'case_id': case.id,
            'case_number': case.case_number,
            'case_type': case.case_type,
        }

    def add_deadline(deadline_type, target_type, target_id, target_name, deadline_label, deadline_date, case):
        if not deadline_date:
            return
        # 案件が完了・取下げ・不許可で終わっていれば、期限をどれだけ過ぎていても
        # もう動きが無いはずなので出さない（案件が無い場合は判断材料が無いので出し続ける）。
        if not include_dismissed and case is not None and case.status in TERMINAL_CASE_STATUSES:
            return
        key = (target_type, target_id, deadline_type, deadline_date)
        if key in dismissed_map and not dismissal_is_stale(target_type, target_id, dismissed_map[key]):
            return
        days_left = (deadline_date - today).days
        if days_left > 180:
            return
        status_value = 'overdue' if days_left < 0 else 'today' if days_left == 0 else 'upcoming'
        items.append({
            'type': deadline_type,
            'target_type': target_type,
            'target_id': target_id,
            'target_name': target_name,
            'deadline_label': deadline_label,
            'deadline_date': deadline_date.isoformat(),
            'days_left': days_left,
            'status': status_value,
            **case_data(case),
        })

    # 実在する Customer は「本人の案件」「家族滞在の対象」「会社スタッフ」の複数経路から
    # 同じ人物にたどり着くことがある（例：本人の案件も持ち、別会社のスタッフでもある）。
    # customer_id を鍵に1人1エントリへ集約し、案件番号は本人の案件を優先、なければ
    # 家族／会社側で見つかった案件で補完する。
    customer_entries = {}
    for customer in customers:
        customer_entries[customer.id] = {
            'name': customer.name,
            'residence_expiry': customer.residence_expiry,
            'passport_expiry': customer.passport_expiry,
            'case': latest_case(customer.cases),
        }

    for family_member in family_members.select_related('customer', 'family_customer'):
        person = family_member.family_customer
        if person:
            entry = customer_entries.get(person.id)
            if entry and entry['case'] is None:
                entry['case'] = latest_case(family_member.customer.cases)
            continue
        # family_customer 未紐付けの旧仕様レコード。パスポート期限はこの段階のデータに存在しない。
        case = latest_case(family_member.customer.cases)
        add_deadline(
            'residence_expiry',
            'family_member',
            family_member.id,
            family_member.name,
            '在留期限',
            family_member.residence_expiry,
            case,
        )

    for staff_member in company_staff.select_related('company', 'customer'):
        person = staff_member.customer
        if not person:
            continue
        entry = customer_entries.get(person.id)
        if entry and entry['case'] is None:
            entry['case'] = latest_case(staff_member.company.cases)

    for customer_id, entry in customer_entries.items():
        add_deadline(
            'residence_expiry',
            'customer',
            customer_id,
            entry['name'],
            '在留期限',
            entry['residence_expiry'],
            entry['case'],
        )
        add_deadline(
            'passport_expiry',
            'customer',
            customer_id,
            entry['name'],
            'パスポート期限',
            entry['passport_expiry'],
            entry['case'],
        )

    for company in companies:
        fiscal_deadline = DashboardDeadlinesView.get_next_fiscal_declaration_deadline(company.fiscal_month, today)
        add_deadline(
            'fiscal_declaration',
            'company',
            company.id,
            company.name,
            '決算申告期限',
            fiscal_deadline,
            latest_case(company.cases),
        )

    items.sort(key=lambda item: (item['days_left'], item['deadline_date'], item['target_name']))
    return items


class DashboardSummaryView(BusinessAccessMixin, APIView):
    """ダッシュボードの案件統計をサーバー側の集計で返す。

    フロントで案件一覧の1ページ目だけを数えていた実装を置き換えるためのもの。
    件数はすべて DB 集計で計算し、ページングの影響を受けない。
    """

    access_resource = 'case'

    def get(self, request):
        today = timezone.localdate()

        # 統計は利用者の案件範囲（本人担当／case_view_all で全件）で計算する。
        base = self.business_policy.queryset('case', 'list').filter(
            registration_status=Case.REGISTRATION_STATUS_ACTIVE,
        )
        open_cases = base.exclude(status__in=CLOSED_CASE_STATUSES)

        stage_counts = {
            row['status']: row['count']
            for row in base.values('status').annotate(count=Count('id'))
        }
        stages = []
        for key, label, statuses in DASHBOARD_STAGE_GROUPS:
            stages.append({
                'key': key,
                'label': label,
                'count': sum(stage_counts.get(s, 0) for s in statuses),
            })

        action_aggregate = open_cases.aggregate(
            overdue=Count('id', filter=Q(next_action_due_at__lt=today)),
            today=Count('id', filter=Q(next_action_due_at=today)),
            next_7_days=Count('id', filter=Q(
                next_action_due_at__gt=today,
                next_action_due_at__lte=today + timedelta(days=7),
            )),
        )

        recent_cases = [
            {
                'id': case.id,
                'case_number': case.case_number,
                'case_type': case.case_type,
                'customer_name': getattr(case.customer, 'name', '') or '',
                'company_name': getattr(case.company, 'name', '') if case.company_id else '',
                'status': case.status,
                'status_display': case.get_status_display(),
                'responsible_employee_name': (
                    getattr(case.responsible_employee, 'name', '') if case.responsible_employee_id else ''
                ),
                'next_action': case.next_action,
                'next_action_due_at': case.next_action_due_at.isoformat() if case.next_action_due_at else None,
                'updated_at': case.updated_at.isoformat(),
            }
            for case in base.select_related('customer', 'company', 'responsible_employee')
            .order_by('-updated_at', '-id')[:10]
        ]

        return Response({
            'cases': {
                'total': base.count(),
                'active': open_cases.count(),
                'waiting': open_cases.filter(status__in=WAITING_CASE_STATUSES).count(),
                'completed': base.filter(status=Case.STATUS_COMPLETED).count(),
                'unassigned': open_cases.filter(responsible_employee__isnull=True).count(),
                'without_next_action': open_cases.filter(
                    Q(next_action='') | Q(next_action__isnull=True),
                ).count(),
            },
            'actions': {
                'overdue': action_aggregate['overdue'] or 0,
                'today': action_aggregate['today'] or 0,
                'next_7_days': action_aggregate['next_7_days'] or 0,
            },
            'stages': stages,
            'recent_cases': recent_cases,
        })


class DashboardDeadlinesView(BusinessAccessMixin, APIView):
    access_resource = 'case'

    def get(self, request):
        today = timezone.localdate()
        items = build_dashboard_deadlines(today, policy=self.business_policy)
        return Response(items)

    @staticmethod
    def get_next_fiscal_declaration_deadline(fiscal_month, today):
        if not fiscal_month:
            return None
        try:
            month = int(fiscal_month)
        except ValueError:
            return None
        if month < 1 or month > 12:
            return None

        deadline = DashboardDeadlinesView.get_fiscal_declaration_deadline(today.year, month)
        if deadline < today:
            deadline = DashboardDeadlinesView.get_fiscal_declaration_deadline(today.year + 1, month)
        return deadline

    @staticmethod
    def get_fiscal_declaration_deadline(year, fiscal_month):
        deadline_month_index = fiscal_month + 2
        deadline_year = year + (deadline_month_index - 1) // 12
        deadline_month = (deadline_month_index - 1) % 12 + 1
        deadline_day = calendar.monthrange(deadline_year, deadline_month)[1]
        return date(deadline_year, deadline_month, deadline_day)
