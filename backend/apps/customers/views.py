from rest_framework.viewsets import ModelViewSet
from rest_framework.filters import SearchFilter

from .models import Customer, FamilyMember
from .serializers import CustomerSerializer, FamilyMemberSerializer


class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'phone', 'email', 'address']

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
