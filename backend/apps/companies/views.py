from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.viewsets import ModelViewSet

from apps.authentication.drf import BusinessScopedViewSetMixin
from apps.customers.my_number import reveal_response

from .models import Company, CompanyStaff
from .serializers import CompanySerializer, CompanyStaffSerializer


class CompanyViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'company'
    queryset = Company.objects.select_related('representative_customer')
    serializer_class = CompanySerializer
    filter_backends = [SearchFilter]
    # リモート検索セレクタ用：会社名・フリガナ・代表者名・法人番号で引ける。
    search_fields = [
        'name',
        'name_kana',
        'representative_name',
        'representative_name_kana',
        'corporate_number',
    ]


class CompanyStaffViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'company_staff'
    access_action_map = {'reveal_my_number': 'view'}
    queryset = CompanyStaff.objects.select_related('company', 'customer')
    serializer_class = CompanyStaffSerializer

    @action(detail=True, methods=['post'], url_path='reveal-my-number')
    def reveal_my_number(self, request, pk=None):
        """会社職員のマイナンバーの表示（P6）。顧客・家族と同じ権限と監査。関連付いた顧客があればその顧客の値。"""
        return reveal_response(self, request, pk, 'company_staff')

    def get_queryset(self):
        queryset = super().get_queryset()
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset
