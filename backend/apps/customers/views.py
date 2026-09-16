from django.db.models import Count, Prefetch, Q
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

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


class ResidenceStatusMasterViewSet(ActiveOrderingMixin, ModelViewSet):
    queryset = ResidenceStatusMaster.objects.all()
    serializer_class = ResidenceStatusMasterSerializer
    pagination_class = ResidenceStatusMasterPagination

    @action(detail=False, methods=['post'], url_path='seed-standard')
    def seed_standard(self, request):
        result = seed_standard_residence_statuses()
        return Response(result, status=status.HTTP_201_CREATED)


class CustomerViewSet(ModelViewSet):
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
            case_customer_ids = list(
                Case.objects.filter(case_number__icontains=search)
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
            dependent_ids = set(FamilyMember.objects.filter(
                family_customer__isnull=False
            ).values_list('family_customer_id', flat=True))
            independent_ids = set(Customer.objects.filter(
                Q(cases__isnull=False)
                | Q(representative_companies__isnull=False)
                | Q(company_staff_roles__isnull=False)
            ).values_list('id', flat=True))
            queryset = queryset.exclude(id__in=(dependent_ids - independent_ids))

        if self.action == 'list':
            queryset = queryset.prefetch_related(
                Prefetch('family_links', queryset=FamilyMember.objects.select_related('customer')),
            ).annotate(
                cases_count_annotated=Count('cases', distinct=True),
                dependents_count_annotated=Count(
                    'family_members', filter=Q(family_members__family_customer__isnull=False), distinct=True,
                ),
            )
        return queryset

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
        return Response({'candidates': candidates})


class FamilyMemberViewSet(ModelViewSet):
    queryset = FamilyMember.objects.select_related('customer', 'family_customer')
    serializer_class = FamilyMemberSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset
