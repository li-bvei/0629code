from django.db.models import Count, Prefetch, Q
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from django.conf import settings

from apps.authentication.drf import BusinessScopedViewSetMixin

from apps.cases.models import Case

from .demo_data import seed_standard_residence_statuses
from .models import Customer, FamilyMember, ResidenceStatusMaster
from .utils import find_customer_candidates
from .serializers import (
    CustomerDetailSerializer,
    CustomerSerializer,
    FamilyMemberSerializer,
    ResidenceStatusMasterSerializer,
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


class ResidenceStatusMasterPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 200


class ResidenceStatusMasterViewSet(BusinessScopedViewSetMixin, ActiveOrderingMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = ResidenceStatusMaster.objects.all()
    serializer_class = ResidenceStatusMasterSerializer
    pagination_class = ResidenceStatusMasterPagination

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        if not settings.ENABLE_DEV_TOOLS:
            return Response({'detail': 'この機能は本番環境では無効です（管理コマンドを使用）。'}, status=status.HTTP_404_NOT_FOUND)
        result = seed_standard_residence_statuses()
        return Response(result, status=status.HTTP_201_CREATED)


class CustomerViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    """顧客。一覧・検索は全件だが範囲外は最小識別情報のみ、詳細は担当範囲／全件閲覧権限／
    案件の無い顧客（基本情報のみ）に限る。証件番号は担当範囲外で伏せる。"""

    access_resource = 'customer'
    access_action_map = {'match': 'list'}
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    # リモート検索セレクタ用の検索対象カラム（氏名・カナ・連絡先・在留カード番号・
    # パスポート番号。いずれも平文。マイナンバーは暗号化保存のため対象外）。
    SEARCH_FIELDS = ['name', 'name_kana', 'phone', 'email', 'address', 'residence_card_no', 'passport_no']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CustomerDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()
        residence_status = self.request.query_params.get('residence_status')
        if residence_status:
            queryset = queryset.filter(residence_status=residence_status)

        # リモート検索：顧客カラム（氏名・カナ・連絡先・証明書番号）に加え、
        # 案件番号でも引けるようにする。件数はページングで制限される。
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            column_q = Q()
            for field in self.SEARCH_FIELDS:
                column_q |= Q(**{f'{field}__icontains': search})
            # 案件番号での検索は、利用者が見られる案件に限る。
            case_customer_ids = list(
                self.business_policy.queryset('case', 'list').filter(case_number__icontains=search)
                .values_list('customer_id', flat=True)
            )
            if case_customer_ids:
                column_q |= Q(pk__in=case_customer_ids)
            queryset = queryset.filter(column_q).order_by('name', 'id')

        exclude_dependents = self.request.query_params.get('exclude_dependents')
        if exclude_dependents in ('true', '1'):
            # 「誰かの家族として登録されている」顧客を一覧から除外し、主申請人（独立した
            # 顧客）だけを出す。ただし配偶者・兄弟姉妹は双方向にリンクされる仕様
            # （sync_reverse_family_link）のため、単に family_customer になっているかだけで
            # 判定すると、本人が案件・会社代表を持つ「本来の主申請人」まで配偶者側の
            # リンクで誤って除外されてしまう。そのため、案件も会社代表・従業員歴も無い
            # 人物だけを「除外してよい家族」とみなす（複数の reverse relation を1つの
            # filter/exclude に混ぜると意図しないJOINになりやすいため、ID集合の差分で
            # 明示的に計算する）。
            dependent_ids = set(FamilyMember.objects.filter(  # access-reviewed: 一覧の除外条件用の ID 計算（出力は範囲済み queryset）
                family_customer__isnull=False
            ).values_list('family_customer_id', flat=True))
            independent_ids = set(Customer.objects.filter(  # access-reviewed: 同上
                Q(cases__isnull=False)
                | Q(representative_companies__isnull=False)
                | Q(company_staff_roles__isnull=False)
            ).values_list('id', flat=True))
            queryset = queryset.exclude(id__in=(dependent_ids - independent_ids))

        if self.action == 'list':
            queryset = queryset.prefetch_related(
                Prefetch('family_links', queryset=FamilyMember.objects.select_related('customer')),  # access-reviewed: 範囲済み一覧への prefetch
            ).annotate(
                cases_count_annotated=Count('cases', distinct=True),
                dependents_count_annotated=Count(
                    'family_members', filter=Q(family_members__family_customer__isnull=False), distinct=True,
                ),
            )
        return queryset

    def retrieve(self, request, *args, **kwargs):
        from apps.audit.services import record
        from apps.authentication.access_rules import CUSTOMER_RULE

        instance = self.get_object()
        policy = self.business_policy
        assigned, _ = CUSTOMER_RULE._flags(policy, instance)
        if not assigned and policy.has(CUSTOMER_RULE.SENSITIVE):
            record(module='customers', action='sensitive_identity_view', request=request, obj=instance,
                   via_permission=CUSTOMER_RULE.SENSITIVE)
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=['post'], url_path='match')
    def match(self, request):
        """新規受付：入力された最小情報から既存顧客の候補をルールベースで返す。

        システムが勝手に統合はせず、候補の提示のみ行う（確認は必ず人が行う）。
        """
        data = request.data or {}
        birth_date = data.get('birth_date') or None
        if birth_date:
            parsed = parse_date(str(birth_date))
            if parsed is None:
                return Response({'birth_date': '生年月日の形式が正しくありません。'}, status=status.HTTP_400_BAD_REQUEST)
            birth_date = parsed
        candidates = find_customer_candidates(
            name=data.get('name') or '',
            name_kana=data.get('name_kana') or '',
            birth_date=birth_date,
            phone=data.get('phone') or '',
            email=data.get('email') or '',
            residence_card_number=data.get('residence_card_number') or data.get('residence_card_no') or '',
            passport_number=data.get('passport_number') or data.get('passport_no') or '',
        )
        return Response({'candidates': self._shape_candidates(candidates)})

    def _shape_candidates(self, candidates):
        """担当範囲外の候補からは連絡先を除き、最小識別情報に揃える（Q5）。"""
        from apps.authentication.access_rules import CUSTOMER_RULE, DETAIL_LEVELS

        from .access_representation import minimal_customer

        policy = self.business_policy
        customers = {
            c.pk: c for c in policy.queryset('customer', 'list').filter(pk__in=[row['customer_id'] for row in candidates])
        }
        shaped = []
        for row in candidates:
            customer = customers.get(row['customer_id'])
            if customer is None:
                continue
            level = CUSTOMER_RULE.level(policy, customer)
            if level in DETAIL_LEVELS:
                shaped.append({**row, 'access_level': level})
                continue
            minimal = minimal_customer(customer)
            shaped.append({
                'customer_id': customer.pk,
                'name': minimal['name'],
                'name_kana': minimal['name_kana'],
                'birth_date': minimal['birth_date'],
                'nationality': minimal['nationality'],
                'has_active_case': minimal['has_active_case'],
                'responsible_employee_names': minimal['responsible_employee_names'],
                'case_count': row.get('case_count'),
                'match_strength': row['match_strength'],
                'match_score': row['match_score'],
                'match_reason': row['match_reason'],
                'access_level': level,
            })
        return shaped


class FamilyMemberViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'family_member'
    queryset = FamilyMember.objects.select_related('customer', 'family_customer')
    serializer_class = FamilyMemberSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset
