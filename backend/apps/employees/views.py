from rest_framework.viewsets import ModelViewSet

from apps.authentication.drf import BusinessScopedViewSetMixin
from rest_framework.filters import SearchFilter

from .models import Employee
from .serializers import EmployeeSerializer


class EmployeeViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'case_settings'
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'email', 'phone']

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active in ['true', '1']:
            queryset = queryset.filter(is_active=True)
        elif is_active in ['false', '0']:
            queryset = queryset.filter(is_active=False)
        return queryset
