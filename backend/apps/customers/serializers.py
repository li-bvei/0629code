from rest_framework import serializers

from .models import Customer, FamilyMember, ResidenceStatusMaster
from .utils import sync_reverse_family_link


class ResidenceStatusMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResidenceStatusMaster
        fields = ['id', 'name', 'category', 'sort_order', 'is_active', 'created_at', 'updated_at']


class CustomerSerializer(serializers.ModelSerializer):
    cases_count = serializers.SerializerMethodField()
    is_dependent = serializers.SerializerMethodField()
    primary_applicant = serializers.SerializerMethodField()
    dependents_count = serializers.SerializerMethodField()

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
            'is_dependent',
            'primary_applicant',
            'dependents_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'cases_count', 'is_dependent', 'primary_applicant', 'dependents_count',
            'created_at', 'updated_at',
        ]

    def get_cases_count(self, obj):
        return obj.cases.count()

    def _primary_family_link(self, obj):
        # 顧客一覧では「誰かの家族（配偶者・子など）として登録されているか」を判定したいだけなので、
        # 複数の family_links がある場合でも先頭の1件だけ見れば十分。
        # ViewSet 側で prefetch_related('family_links__customer') 済みの前提で
        # obj.family_links.all() を呼ぶ（ここで select_related 等を追加すると
        # prefetch のキャッシュが使われず1行ごとに追加クエリが発生するので避ける）。
        links = list(obj.family_links.all())
        return links[0] if links else None

    def get_is_dependent(self, obj):
        return self._primary_family_link(obj) is not None

    def get_primary_applicant(self, obj):
        link = self._primary_family_link(obj)
        if not link:
            return None
        return {
            'id': link.customer_id,
            'name': link.customer.name,
            'relationship': link.relationship,
            'relationship_display': link.get_relationship_display(),
        }

    def get_dependents_count(self, obj):
        # ViewSet 側で Count アノテーションが付いていればそれを使い、無ければ都度カウントする
        # （CustomerDetailSerializer 経由の retrieve など、アノテーション無しでも動くように）。
        annotated = getattr(obj, 'dependents_count_annotated', None)
        if annotated is not None:
            return annotated
        return obj.family_members.filter(family_customer__isnull=False).count()


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
        instance = super().create(validated_data)
        sync_reverse_family_link(instance)
        return instance

    def update(self, instance, validated_data):
        new_customer_data = validated_data.pop('new_customer', None)
        if new_customer_data:
            customer_serializer = CustomerSerializer(data=new_customer_data)
            customer_serializer.is_valid(raise_exception=True)
            validated_data['family_customer'] = customer_serializer.save()
        instance = super().update(instance, validated_data)
        sync_reverse_family_link(instance)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.family_customer_id:
            person = instance.family_customer
            for field in FAMILY_MEMBER_PERSON_FIELDS:
                data[field] = getattr(person, field)
        return data
