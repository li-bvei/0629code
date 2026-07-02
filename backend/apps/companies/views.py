from rest_framework.viewsets import ModelViewSet

from .models import Company, CompanyStaff
from .serializers import CompanySerializer, CompanyStaffSerializer


class CompanyViewSet(ModelViewSet):
    queryset = Company.objects.select_related('representative_customer')
    serializer_class = CompanySerializer


class CompanyStaffViewSet(ModelViewSet):
    queryset = CompanyStaff.objects.select_related('company')
    serializer_class = CompanyStaffSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset
