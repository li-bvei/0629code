from django.db.models import Count, Prefetch, Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.filters import SearchFilter

from .demo_data import seed_standard_residence_statuses
from .models import Customer, FamilyMember, ResidenceStatusMaster
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
    filter_backends = [SearchFilter]
    search_fields = ['name', 'phone', 'email', 'address']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CustomerDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()
        residence_status = self.request.query_params.get('residence_status')
        if residence_status:
            queryset = queryset.filter(residence_status=residence_status)

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
                dependents_count_annotated=Count(
                    'family_members', filter=Q(family_members__family_customer__isnull=False), distinct=True,
                ),
            )
        return queryset


class FamilyMemberViewSet(ModelViewSet):
    queryset = FamilyMember.objects.select_related('customer', 'family_customer')
    serializer_class = FamilyMemberSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset
