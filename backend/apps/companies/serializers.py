from rest_framework import serializers

from .models import Company, CompanyStaff


class CompanySerializer(serializers.ModelSerializer):
    cases_count = serializers.SerializerMethodField()
    representative_customer_name = serializers.CharField(
        source='representative_customer.name',
        read_only=True,
    )

    class Meta:
        model = Company
        fields = [
            'id',
            'name',
            'name_kana',
            'representative_customer',
            'representative_customer_name',
            'representative_name',
            'representative_name_kana',
            'corporate_number',
            'corporate_registration_number',
            'email',
            'phone',
            'postal_code',
            'address',
            'fiscal_month',
            'bank_name',
            'bank_branch',
            'bank_account_type',
            'bank_account_number',
            'cases_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'corporate_registration_number',
            'representative_customer_name',
            'cases_count',
            'created_at',
            'updated_at',
        ]

    def get_cases_count(self, obj):
        return obj.cases.count()


class CompanyStaffSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')

    class Meta:
        model = CompanyStaff
        fields = [
            'id',
            'company',
            'company_name',
            'customer',
            'customer_name',
            'name',
            'name_kana',
            'position',
            'birth_date',
            'gender',
            'nationality',
            'residence_status',
            'residence_card_no',
            'residence_expiry',
            'passport_no',
            'passport_expiry',
            'phone',
            'email',
            'postal_code',
            'address',
            'my_number',
            'employment_start_date',
            'employment_end_date',
            'note',
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        customer = attrs.get('customer', getattr(self.instance, 'customer', None))
        employment_end_date = attrs.get(
            'employment_end_date',
            getattr(self.instance, 'employment_end_date', None),
        )
        if customer and not employment_end_date:
            conflict = CompanyStaff.objects.filter(
                customer=customer,
                employment_end_date__isnull=True,
            )
            if self.instance:
                conflict = conflict.exclude(pk=self.instance.pk)
            if conflict.exists():
                raise serializers.ValidationError(
                    {'customer': 'この顧客は既に他の会社の従業員として在職中です。'}
                )
        return attrs
        read_only_fields = ['id', 'company_name', 'created_at', 'updated_at']
