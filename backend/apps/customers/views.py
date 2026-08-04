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
        return queryset


class FamilyMemberViewSet(ModelViewSet):
    queryset = FamilyMember.objects.select_related('customer')
    serializer_class = FamilyMemberSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset
