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
    has_my_number = serializers.SerializerMethodField()

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
            'has_my_number',
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
            'has_my_number',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            # マイナンバーは保存時だけ受け取り、通常の一覧・詳細レスポンスには載せない。
            # 登録済みかどうかは has_my_number で確認する。
            'my_number': {'write_only': True, 'required': False},
        }

    def to_representation(self, instance):
        from apps.authentication.access_rules import CUSTOMER_RULE, LEVEL_BASIC, LEVEL_MINIMAL

        from .access_representation import minimal_customer, shape_customer

        policy = self.context.get('policy')
        if policy is None:
            data = super().to_representation(instance)
            data.pop('my_number', None)
            return data
        level = CUSTOMER_RULE.level(policy, instance)
        if level == LEVEL_MINIMAL:
            return minimal_customer(instance)
        if level == LEVEL_BASIC:
            # 詳細シリアライザでも関連案件・活動は計算しない（案件の無い顧客の基本情報のみ）。
            data = CustomerSerializer(instance, context={**self.context, 'policy': None}).data
            return shape_customer(dict(data), level)
        return shape_customer(super().to_representation(instance), level)

    def get_cases_count(self, obj):
        annotated = getattr(obj, 'cases_count_annotated', None)
        if annotated is not None:
            return annotated
        return obj.cases.count()

    def get_has_my_number(self, obj):
        return bool(obj.my_number)

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


class CustomerCaseSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    case_number = serializers.CharField()
    case_type = serializers.CharField()
    case_type_master = serializers.IntegerField(source='case_type_master_id', allow_null=True)
    case_type_master_name = serializers.CharField(source='case_type_master.name', allow_null=True)
    application_category = serializers.IntegerField(source='application_category_id', allow_null=True)
    application_category_name = serializers.CharField(source='application_category.name', allow_null=True)
    registration_status = serializers.CharField()
    registration_status_display = serializers.CharField(source='get_registration_status_display')
    status = serializers.CharField()
    status_display = serializers.CharField(source='get_status_display')
    company = serializers.IntegerField(source='company_id', allow_null=True)
    company_name = serializers.CharField(source='company.name', allow_null=True)
    responsible_employee = serializers.IntegerField(source='responsible_employee_id', allow_null=True)
    responsible_employee_name = serializers.CharField(source='responsible_employee.name', allow_null=True)
    accepted_at = serializers.DateField(allow_null=True)
    next_action = serializers.CharField()
    next_action_due_at = serializers.DateField(allow_null=True)
    updated_at = serializers.DateTimeField()


class CustomerDetailSerializer(CustomerSerializer):
    related_cases = serializers.SerializerMethodField()
    related_companies = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    recent_activities = serializers.SerializerMethodField()

    class Meta(CustomerSerializer.Meta):
        fields = [
            *CustomerSerializer.Meta.fields,
            'related_cases',
            'related_companies',
            'summary',
            'recent_activities',
        ]
        read_only_fields = [
            *CustomerSerializer.Meta.read_only_fields,
            'related_cases',
            'related_companies',
            'summary',
            'recent_activities',
        ]

    @staticmethod
    def _is_active_case(case):
        from apps.cases.models import Case

        return (
            case.registration_status == Case.REGISTRATION_STATUS_ACTIVE
            and case.status not in {
                Case.STATUS_REJECTED,
                Case.STATUS_WITHDRAWN,
                Case.STATUS_COMPLETED,
            }
        )

    def _related_case_queryset(self, obj):
        cache = getattr(self, '_related_cases_cache', {})
        if obj.pk not in cache:
            cases = obj.cases.all()
            policy = self.context.get('policy')
            if policy is not None:
                # 関連案件は利用者の案件範囲に限る。
                cases = policy.scope('case', cases, 'list')
            cache[obj.pk] = list(
                cases
                .select_related(
                    'case_type_master',
                    'application_category',
                    'company',
                    'responsible_employee',
                )
                .order_by('-updated_at', '-created_at', '-id')
            )
            self._related_cases_cache = cache
        return cache[obj.pk]

    def get_related_cases(self, obj):
        return CustomerCaseSummarySerializer(
            self._related_case_queryset(obj),
            many=True,
            context=self.context,
        ).data

    def get_related_companies(self, obj):
        from apps.companies.models import Company

        cache = getattr(self, '_related_companies_cache', {})
        if obj.pk in cache:
            return cache[obj.pk]

        relation_map = {}

        def ensure_relation(company_id):
            return relation_map.setdefault(company_id, {
                'types': set(),
                'positions': set(),
                'active_cases_count': 0,
                'total_cases_count': 0,
            })

        for company_id in obj.representative_companies.values_list('id', flat=True):
            ensure_relation(company_id)['types'].add('representative')

        for role in obj.company_staff_roles.select_related('company').all():
            relation = ensure_relation(role.company_id)
            relation['types'].add('staff')
            if role.position:
                relation['positions'].add(role.position)

        for case in obj.cases.filter(pk__in=[c.pk for c in self._related_case_queryset(obj)]).exclude(company_id__isnull=True).only(
            'company_id', 'registration_status', 'status',
        ):
            relation = ensure_relation(case.company_id)
            relation['types'].add('case')
            relation['total_cases_count'] += 1
            if self._is_active_case(case):
                relation['active_cases_count'] += 1

        companies = Company.objects.filter(id__in=relation_map).order_by('name', 'id')
        labels = {
            'representative': '代表者',
            'staff': '従業員',
            'case': '案件関連',
        }
        result = []
        for company in companies:
            relation = relation_map[company.id]
            relation_types = [
                key for key in ('representative', 'staff', 'case')
                if key in relation['types']
            ]
            result.append({
                'id': company.id,
                'name': company.name,
                'name_kana': company.name_kana,
                'phone': company.phone,
                'email': company.email,
                'relation_types': relation_types,
                'relation_labels': [labels[key] for key in relation_types],
                'positions': sorted(relation['positions']),
                'active_cases_count': relation['active_cases_count'],
                'total_cases_count': relation['total_cases_count'],
            })
        cache[obj.pk] = result
        self._related_companies_cache = cache
        return result

    def get_summary(self, obj):
        cases = list(self._related_case_queryset(obj))
        active_cases = [case for case in cases if self._is_active_case(case)]
        primary_case = active_cases[0] if active_cases else (cases[0] if cases else None)
        return {
            'active_cases_count': len(active_cases),
            'historical_cases_count': len(cases) - len(active_cases),
            'family_count': obj.family_members.count(),
            'company_count': len(self.get_related_companies(obj)),
            'primary_case': (
                CustomerCaseSummarySerializer(primary_case, context=self.context).data
                if primary_case else None
            ),
        }

    def get_recent_activities(self, obj):
        from apps.timelines.models import Timeline

        visible_case_ids = [case.pk for case in self._related_case_queryset(obj)]
        rows = (
            Timeline.objects
            .filter(case__customer=obj, case_id__in=visible_case_ids)
            .select_related('case', 'actor')
            .order_by('-occurred_at', '-created_at', '-id')[:10]
        )
        return [
            {
                'id': row.id,
                'case_id': row.case_id,
                'case_number': row.case.case_number,
                'occurred_at': row.occurred_at,
                'title': row.title,
                'content': row.content,
                'event_type': row.event_type,
                'actor_name': (
                    row.actor.get_full_name() or row.actor.get_username()
                    if row.actor_id else ''
                ),
                'created_at': row.created_at,
            }
            for row in rows
        ]


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


# 家族の編集画面から、関連付いている人物（Customer）の情報を直接修正できる項目
FAMILY_PERSON_EDIT_FIELDS = (
    'name', 'name_kana', 'birth_date', 'gender', 'nationality', 'phone', 'email', 'postal_code', 'address',
    'my_number', 'residence_status', 'residence_card_no', 'residence_expiry', 'passport_no', 'passport_expiry',
)


class FamilyMemberSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    relationship_display = serializers.CharField(source='get_relationship_display', read_only=True)
    gender_display = serializers.SerializerMethodField()
    passport_no = serializers.SerializerMethodField()
    passport_expiry = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    has_my_number = serializers.SerializerMethodField()
    new_customer = serializers.DictField(write_only=True, required=False)
    # 関連付いている人物（family_customer）の修正内容。変更した項目だけを送る（更新時のみ）。
    # 可否は access_rules の PartyChildRule が判定する（他担当の進行中案件の顧客は直接修正できない）。
    person = serializers.DictField(write_only=True, required=False)

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
            'email',
            'has_my_number',
            'is_dependent',
            'note',
            'new_customer',
            'person',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'customer_name',
            'relationship_display',
            'gender_display',
            'email',
            'has_my_number',
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

    def get_email(self, obj):
        return obj.family_customer.email if obj.family_customer_id else ''

    def get_has_my_number(self, obj):
        if obj.family_customer_id:
            return bool(obj.family_customer.my_number)
        return bool(obj.my_number)

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
        person = attrs.get('person')
        if person is not None:
            linked = getattr(self.instance, 'family_customer', None)
            if self.instance is None or linked is None or new_customer_data or family_customer != linked:
                raise serializers.ValidationError(
                    {'person': '人物情報の修正は、関連付け済みの家族を編集するときだけ行えます。'}
                )
            unknown = sorted(set(person) - set(FAMILY_PERSON_EDIT_FIELDS))
            if unknown:
                raise serializers.ValidationError({'person': f'修正できない項目です：{"、".join(unknown)}'})
            if not person.get('my_number'):
                person.pop('my_number', None)  # 空欄は「変更なし」（登録済みの値を消さない）
            if person:
                person_serializer = CustomerSerializer(linked, data=person, partial=True)
                if not person_serializer.is_valid():
                    raise serializers.ValidationError({'person': person_serializer.errors})
                attrs['person'] = person_serializer.validated_data
        return attrs

    def _update_person(self, instance, person):
        """関連付いている人物の情報を修正し、監査に残す（証件番号・My Number は「変更あり」だけ記録）。"""
        from apps.audit.services import record, safe_changes

        linked = instance.family_customer
        before = {field: getattr(linked, field) for field in person}
        for field, value in person.items():
            setattr(linked, field, value)
        changes = safe_changes(before, {field: getattr(linked, field) for field in person})
        if not changes:
            return
        linked.save(update_fields=[*changes.keys(), 'updated_at'])
        record(module='customers', action='family_person_updated', request=self.context.get('request'), obj=linked,
               object_repr=linked.name, changes=changes,
               extra={'family_member_id': instance.pk, 'parent_customer_id': instance.customer_id})

    def create(self, validated_data):
        new_customer_data = validated_data.pop('new_customer', None)
        validated_data.pop('person', None)
        if new_customer_data:
            customer_serializer = CustomerSerializer(data=new_customer_data)
            customer_serializer.is_valid(raise_exception=True)
            validated_data['family_customer'] = customer_serializer.save()
        instance = super().create(validated_data)
        sync_reverse_family_link(instance)
        return instance

    def update(self, instance, validated_data):
        new_customer_data = validated_data.pop('new_customer', None)
        person = validated_data.pop('person', None)
        if new_customer_data:
            customer_serializer = CustomerSerializer(data=new_customer_data)
            customer_serializer.is_valid(raise_exception=True)
            validated_data['family_customer'] = customer_serializer.save()
        instance = super().update(instance, validated_data)
        if person:
            self._update_person(instance, person)
        sync_reverse_family_link(instance)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.family_customer_id:
            person = instance.family_customer
            for field in FAMILY_MEMBER_PERSON_FIELDS:
                if field == 'my_number':
                    continue
                data[field] = getattr(person, field)
        data.pop('my_number', None)
        policy = self.context.get('policy')
        if policy is not None:
            from apps.authentication.access_rules import CUSTOMER_RULE

            from .access_representation import shape_person_child

            shape_person_child(data, CUSTOMER_RULE.level(policy, instance.customer))
        return data
