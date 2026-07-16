from rest_framework import serializers

from .models import Customer, FamilyMember


class CustomerSerializer(serializers.ModelSerializer):
    cases_count = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id',
            'name',
            'name_kana',
            'birth_date',
            'gender',
            'nationality',
            'residence_status',
            'residence_card_no',
            'residence_expiry',
            'passport_no',
            'passport_expiry',
            'email',
            'phone',
            'postal_code',
            'address',
            'my_number',
            'note',
            'cases_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'cases_count', 'created_at', 'updated_at']

    def get_cases_count(self, obj):
        return obj.cases.count()


class CustomerDetailSerializer(CustomerSerializer):
    related_cases = serializers.SerializerMethodField()
    related_companies = serializers.SerializerMethodField()

    class Meta(CustomerSerializer.Meta):
        fields = [
            *CustomerSerializer.Meta.fields,
            'related_cases',
            'related_companies',
        ]
        read_only_fields = [
            *CustomerSerializer.Meta.read_only_fields,
            'related_cases',
            'related_companies',
        ]

    def get_related_cases(self, obj):
        from apps.cases.serializers import CaseSerializer

        queryset = (
            obj.cases
            .select_related('customer', 'company', 'responsible_employee')
            .prefetch_related('tasks__responsible_employee')
            .order_by('-updated_at', '-created_at', '-id')
        )
        return CaseSerializer(queryset, many=True, context=self.context).data

    def get_related_companies(self, obj):
        from apps.companies.models import Company
        from apps.companies.serializers import CompanySerializer

        representative_company_ids = obj.representative_companies.values_list('id', flat=True)
        case_company_ids = (
            obj.cases
            .filter(company__isnull=False)
            .values_list('company_id', flat=True)
        )
        company_ids = set(representative_company_ids) | set(case_company_ids)
        queryset = (
            Company.objects
            .filter(id__in=company_ids)
            .select_related('representative_customer')
            .order_by('name', 'id')
        )
        return CompanySerializer(queryset, many=True, context=self.context).data


class FamilyMemberSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    relationship_display = serializers.CharField(source='get_relationship_display', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)

    class Meta:
        model = FamilyMember
        fields = [
            'id',
            'customer',
            'customer_name',
            'relationship',
            'relationship_display',
            'name',
            'name_kana',
            'birth_date',
            'gender',
            'gender_display',
            'nationality',
            'residence_status',
            'residence_card_no',
            'residence_expiry',
            'phone',
            'postal_code',
            'address',
            'my_number',
            'is_dependent',
            'note',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'customer_name',
            'relationship_display',
            'gender_display',
            'created_at',
            'updated_at',
        ]
