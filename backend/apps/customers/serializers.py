from rest_framework import serializers

from .models import Customer, FamilyMember, ResidenceStatusMaster


class ResidenceStatusMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResidenceStatusMaster
        fields = ['id', 'name', 'category', 'sort_order', 'is_active', 'created_at', 'updated_at']


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


FAMILY_MEMBER_PERSON_FIELDS = [
    'name',
    'name_kana',
    'birth_date',
    'gender',
    'nationality',
    'residence_status',
    'residence_card_no',
    'residence_expiry',
    'phone',
    'postal_code',
    'address',
    'my_number',
]


class FamilyMemberSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    relationship_display = serializers.CharField(source='get_relationship_display', read_only=True)
    gender_display = serializers.SerializerMethodField()
    passport_no = serializers.SerializerMethodField()
    passport_expiry = serializers.SerializerMethodField()
    new_customer = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = FamilyMember
        fields = [
            'id',
            'customer',
            'customer_name',
            'family_customer',
            'relationship',
            'relationship_display',
            *FAMILY_MEMBER_PERSON_FIELDS,
            'gender_display',
            'passport_no',
            'passport_expiry',
            'is_dependent',
            'note',
            'new_customer',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'customer_name',
            'relationship_display',
            'gender_display',
            *FAMILY_MEMBER_PERSON_FIELDS,
            'created_at',
            'updated_at',
        ]

    def get_gender_display(self, obj):
        gender = obj.family_customer.gender if obj.family_customer_id else obj.gender
        return dict(Customer.GENDER_CHOICES).get(gender, '')

    def get_passport_no(self, obj):
        return obj.family_customer.passport_no if obj.family_customer_id else ''

    def get_passport_expiry(self, obj):
        return obj.family_customer.passport_expiry if obj.family_customer_id else None

    def validate(self, attrs):
        family_customer = attrs.get('family_customer', getattr(self.instance, 'family_customer', None))
        new_customer_data = attrs.get('new_customer')
        if self.instance is None and not family_customer and not new_customer_data:
            raise serializers.ValidationError(
                {'family_customer': '本人となる顧客を選択するか、新しい顧客情報を入力してください。'}
            )
        if family_customer and new_customer_data:
            raise serializers.ValidationError(
                {'family_customer': '既存顧客の選択と新規顧客の入力は同時に指定できません。'}
            )
        return attrs

    def create(self, validated_data):
        new_customer_data = validated_data.pop('new_customer', None)
        if new_customer_data:
            customer_serializer = CustomerSerializer(data=new_customer_data)
            customer_serializer.is_valid(raise_exception=True)
            validated_data['family_customer'] = customer_serializer.save()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('new_customer', None)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.family_customer_id:
            person = instance.family_customer
            for field in FAMILY_MEMBER_PERSON_FIELDS:
                data[field] = getattr(person, field)
        return data
