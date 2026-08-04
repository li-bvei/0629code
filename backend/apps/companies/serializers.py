from rest_framework import serializers

from apps.customers.serializers import CustomerSerializer

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


COMPANY_STAFF_PERSON_FIELDS = [
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
    'phone',
    'email',
    'postal_code',
    'address',
    'my_number',
]


class CompanyStaffSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    new_customer = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = CompanyStaff
        fields = [
            'id',
            'company',
            'company_name',
            'customer',
            'customer_name',
            'position',
            *COMPANY_STAFF_PERSON_FIELDS,
            'employment_start_date',
            'employment_end_date',
            'note',
            'new_customer',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'company_name',
            'customer_name',
            *COMPANY_STAFF_PERSON_FIELDS,
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        customer = attrs.get('customer', getattr(self.instance, 'customer', None))
        new_customer_data = attrs.get('new_customer')
        if self.instance is None and not customer and not new_customer_data:
            raise serializers.ValidationError(
                {'customer': '従業員となる顧客を選択するか、新しい顧客情報を入力してください。'}
            )
        if customer and new_customer_data:
            raise serializers.ValidationError(
                {'customer': '既存顧客の選択と新規顧客の入力は同時に指定できません。'}
            )
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

    def create(self, validated_data):
        new_customer_data = validated_data.pop('new_customer', None)
        if new_customer_data:
            customer_serializer = CustomerSerializer(data=new_customer_data)
            customer_serializer.is_valid(raise_exception=True)
            validated_data['customer'] = customer_serializer.save()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('new_customer', None)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.customer_id:
            person = instance.customer
            for field in COMPANY_STAFF_PERSON_FIELDS:
                data[field] = getattr(person, field)
        return data
