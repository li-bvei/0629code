from rest_framework.filters import SearchFilter
from rest_framework.viewsets import ModelViewSet

from apps.authentication.drf import BusinessScopedViewSetMixin

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
    queryset = CompanyStaff.objects.select_related('company', 'customer')
    serializer_class = CompanyStaffSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset
