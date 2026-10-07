from django.db import transaction
from rest_framework import serializers

from apps.accounting.service_lines import ServiceLineError, case_service_items, mark_used
from apps.cases.models import Case, CaseApplicationCategory, CaseTypeMaster
from apps.companies.models import Company
from apps.cases.utils import auto_apply_default_checklist_template
from apps.customers.models import Customer, FamilyMember
from apps.customers.utils import sync_reverse_family_link
from apps.timelines.models import Timeline
from apps.timelines.services import record_case_event


def has_any_value(data):
    return any(value not in ('', None, []) for value in data.values())


def normalize_gender(value):
    labels = {
        '男性': Customer.GENDER_MALE,
        '女性': Customer.GENDER_FEMALE,
        'その他': Customer.GENDER_OTHER,
    }
    return labels.get(value, value or '')


def normalize_relationship(value):
    labels = {
        '配偶者': FamilyMember.RELATIONSHIP_SPOUSE,
        '子': FamilyMember.RELATIONSHIP_CHILD,
        '父': FamilyMember.RELATIONSHIP_FATHER,
        '母': FamilyMember.RELATIONSHIP_MOTHER,
        '兄弟姉妹': FamilyMember.RELATIONSHIP_SIBLING,
        'その他': FamilyMember.RELATIONSHIP_OTHER,
    }
    return labels.get(value, value or FamilyMember.RELATIONSHIP_OTHER)


class ReceptionCustomerSerializer(serializers.Serializer):
    name = serializers.CharField()
    name_kana = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.DateField()
    gender = serializers.CharField(required=False, allow_blank=True)
    nationality = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    my_number = serializers.CharField(required=False, allow_blank=True)
    residence_status = serializers.CharField(required=False, allow_blank=True)
    residence_card_no = serializers.CharField(required=False, allow_blank=True)
    residence_expiry = serializers.DateField(required=False, allow_null=True)
    passport_no = serializers.CharField(required=False, allow_blank=True)
    passport_expiry = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True)


class ReceptionFamilyMemberSerializer(serializers.Serializer):
    customer = serializers.IntegerField(required=False, allow_null=True)
    relationship = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    name_kana = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    nationality = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    my_number = serializers.CharField(required=False, allow_blank=True)
    residence_status = serializers.CharField(required=False, allow_blank=True)
    residence_card_no = serializers.CharField(required=False, allow_blank=True)
    residence_expiry = serializers.DateField(required=False, allow_null=True)
    is_dependent = serializers.BooleanField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not has_any_value(attrs):
            return attrs
        if attrs.get('customer'):
            return attrs
        if not attrs.get('name'):
            raise serializers.ValidationError({'name': '家族の氏名を入力してください。'})
        if not attrs.get('birth_date'):
            raise serializers.ValidationError({'birth_date': '新規に顧客として登録する場合は生年月日を入力してください。'})
        return attrs


class ReceptionCompanySerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True)
    name_kana = serializers.CharField(required=False, allow_blank=True)
    representative_customer = serializers.IntegerField(required=False, allow_null=True)
    representative_customer_is_current_customer = serializers.BooleanField(required=False)
    representative_name = serializers.CharField(required=False, allow_blank=True)
    representative_name_kana = serializers.CharField(required=False, allow_blank=True)
    representative_postal_code = serializers.CharField(required=False, allow_blank=True)
    representative_address = serializers.CharField(required=False, allow_blank=True)
    corporate_number = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    fiscal_month = serializers.CharField(required=False, allow_blank=True)
    establishment_symbol = serializers.CharField(required=False, allow_blank=True)
    establishment_number = serializers.CharField(required=False, allow_blank=True)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    bank_branch = serializers.CharField(required=False, allow_blank=True)
    bank_account_type = serializers.CharField(required=False, allow_blank=True)
    bank_account_number = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        company_fields = {
            key: value
            for key, value in attrs.items()
            if key != 'representative_customer_is_current_customer'
        }
        if has_any_value(company_fields) and not attrs.get('name'):
            raise serializers.ValidationError({'name': '会社名を入力してください。'})
        return attrs


class ReceptionServiceItemSerializer(serializers.Serializer):
    """新規受付で選ぶサービス項目（参考。任意・複数可）。価格はマスタから後端が写す。"""

    service_item = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=1,
                                        min_value=0)


class ReceptionCaseSerializer(serializers.Serializer):
    case_type_master = serializers.PrimaryKeyRelatedField(
        queryset=CaseTypeMaster.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    application_category = serializers.PrimaryKeyRelatedField(
        queryset=CaseApplicationCategory.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    responsible_employee = serializers.IntegerField(required=False, allow_null=True)
    accepted_at = serializers.DateField(required=False, allow_null=True)
    # P4：関連元の案件（任意。閲覧できる案件だけ。受付 API が範囲を確認する）とサービス項目（参考）
    parent_case = serializers.IntegerField(required=False, allow_null=True)
    service_items = ReceptionServiceItemSerializer(many=True, required=False)

    def to_internal_value(self, data):
        data = data.copy()
        if data.get('responsible_employee') == '':
            data['responsible_employee'] = None
        return super().to_internal_value(data)

    def validate(self, attrs):
        case_type = attrs.get('case_type_master')
        has_application_category = bool(attrs.get('application_category'))
        if case_type is None:
            if has_application_category or attrs.get('service_items') or attrs.get('parent_case'):
                raise serializers.ValidationError('案件を作成する場合は案件種別を選択してください。')
            return attrs
        if case_type.requires_application_category and not has_application_category:
            raise serializers.ValidationError('案件を作成する場合は案件種別と申請区分の両方を選択してください。')
        return attrs


class ReceptionSerializer(serializers.Serializer):
    # 新規受付 STEP1 で既存顧客が確定した場合は existing_customer_id を渡す。
    # その場合 customer（新規作成データ）は不要。
    existing_customer_id = serializers.IntegerField(required=False, allow_null=True)
    # 既存会社を選んだ場合は existing_company_id を渡す。その場合 company（新規作成データ）は不要。
    existing_company_id = serializers.IntegerField(required=False, allow_null=True)
    customer = ReceptionCustomerSerializer(required=False)
    family_members = ReceptionFamilyMemberSerializer(many=True, required=False)
    company = ReceptionCompanySerializer(required=False)
    case = ReceptionCaseSerializer(required=False)

    def validate(self, attrs):
        if not attrs.get('existing_customer_id') and not attrs.get('customer'):
            raise serializers.ValidationError(
                {'customer': '既存顧客を選択するか、新規顧客情報を入力してください。'}
            )
        if attrs.get('existing_customer_id'):
            if not Customer.objects.filter(pk=attrs['existing_customer_id']).exists():
                raise serializers.ValidationError(
                    {'existing_customer_id': '指定された顧客が見つかりません。'}
                )
        if attrs.get('existing_company_id'):
            if not Company.objects.filter(pk=attrs['existing_company_id']).exists():
                raise serializers.ValidationError(
                    {'existing_company_id': '指定された会社が見つかりません。'}
                )
        return attrs

    def create(self, validated_data):
        existing_customer_id = validated_data.get('existing_customer_id')
        existing_company_id = validated_data.get('existing_company_id')
        customer_data = validated_data.get('customer')
        family_members_data = validated_data.get('family_members', [])
        company_data = validated_data.get('company') or {}
        case_data = validated_data.get('case') or {}

        with transaction.atomic():
            if existing_customer_id:
                customer = Customer.objects.get(pk=existing_customer_id)
                customer_reused = True
            else:
                customer_data = dict(customer_data)
                customer_data['gender'] = normalize_gender(customer_data.get('gender'))
                customer = Customer.objects.create(**customer_data)
                customer_reused = False

            family_members = []
            for family_member_data in family_members_data:
                if not has_any_value(family_member_data):
                    continue
                family_member_existing_customer_id = family_member_data.pop('customer', None)
                relationship = normalize_relationship(family_member_data.pop('relationship', None))
                is_dependent = family_member_data.pop('is_dependent', False)
                note = family_member_data.pop('note', '')

                if family_member_existing_customer_id:
                    try:
                        family_customer = Customer.objects.get(pk=family_member_existing_customer_id)
                    except Customer.DoesNotExist:
                        raise serializers.ValidationError(
                            {'family_members': f'指定された顧客（id={family_member_existing_customer_id}）が見つかりません。'}
                        )
                else:
                    family_member_data['gender'] = normalize_gender(family_member_data.get('gender'))
                    family_customer = Customer.objects.create(
                        name=family_member_data.get('name', ''),
                        name_kana=family_member_data.get('name_kana', ''),
                        birth_date=family_member_data.get('birth_date'),
                        gender=family_member_data.get('gender', ''),
                        nationality=family_member_data.get('nationality', ''),
                        phone=family_member_data.get('phone', ''),
                        postal_code=family_member_data.get('postal_code', ''),
                        address=family_member_data.get('address', ''),
                        my_number=family_member_data.get('my_number', ''),
                        residence_status=family_member_data.get('residence_status', ''),
                        residence_card_no=family_member_data.get('residence_card_no', ''),
                        residence_expiry=family_member_data.get('residence_expiry'),
                    )

                family_member = FamilyMember.objects.create(
                    customer=customer,
                    family_customer=family_customer,
                    relationship=relationship,
                    is_dependent=is_dependent,
                    note=note,
                )
                sync_reverse_family_link(family_member)
                family_members.append(family_member)

            company = None
            company_reused = False
            if existing_company_id:
                company = Company.objects.get(pk=existing_company_id)
                company_reused = True
            else:
                representative_customer_is_current_customer = company_data.pop(
                    'representative_customer_is_current_customer',
                    False,
                )
                representative_customer_id = company_data.pop('representative_customer', None)
                if has_any_value(company_data) or representative_customer_id:
                    if representative_customer_is_current_customer:
                        company_data['representative_customer'] = customer
                    elif representative_customer_id:
                        company_data['representative_customer_id'] = representative_customer_id
                    company = Company.objects.create(**company_data)

            case = None
            checklist_items = []
            if case_data.get('case_type_master'):
                actor = getattr(self.context.get('request'), 'user', None)
                service_items, used_service_ids = [], set()
                if case_data.get('service_items'):
                    try:
                        service_items, used_service_ids = case_service_items(case_data['service_items'])
                    except ServiceLineError as exc:
                        raise serializers.ValidationError({'case': {'service_items': str(exc)}})
                case = Case.objects.create(
                    case_type_master=case_data['case_type_master'],
                    application_category=case_data.get('application_category'),
                    customer=customer,
                    company=company,
                    responsible_employee_id=case_data.get('responsible_employee'),
                    accepted_at=case_data.get('accepted_at'),
                    parent_case_id=case_data.get('parent_case'),
                    service_items=service_items,
                )
                mark_used(used_service_ids)
                record_case_event(
                    case,
                    Timeline.EVENT_CASE_CREATED,
                    '新規受付',
                    description=(
                        '新規受付から案件を作成しました。'
                        + ('（既存顧客を使用）' if customer_reused else '（新規顧客を登録）')
                    ),
                    actor=actor,
                    metadata={
                        'customer_reused': customer_reused,
                        'customer_id': customer.id,
                        'source': 'reception',
                        'parent_case_id': case.parent_case_id,
                        'service_item_ids': [item['id'] for item in service_items],
                    },
                )
                checklist_items = auto_apply_default_checklist_template(case) or []

        return {
            'customer': customer.id,
            'customer_reused': customer_reused,
            'company': company.id if company else None,
            'company_reused': company_reused,
            'case': case.id if case else None,
            'case_number': case.case_number if case else None,
            'checklist_item_count': len(checklist_items),
            'family_members': [family_member.id for family_member in family_members],
        }
