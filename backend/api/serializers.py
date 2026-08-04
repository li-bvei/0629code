from django.db import transaction
from rest_framework import serializers

from apps.cases.models import Case, CaseApplicationCategory, CaseTypeMaster
from apps.companies.models import Company
from apps.customers.models import Customer, FamilyMember
from apps.timelines.models import Timeline


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
    corporate_number = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    fiscal_month = serializers.CharField(required=False, allow_blank=True)
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

    def to_internal_value(self, data):
        data = data.copy()
        if data.get('responsible_employee') == '':
            data['responsible_employee'] = None
        return super().to_internal_value(data)

    def validate(self, attrs):
        has_case_type = bool(attrs.get('case_type_master'))
        has_application_category = bool(attrs.get('application_category'))
        if has_case_type != has_application_category:
            raise serializers.ValidationError('案件を作成する場合は案件種別と申請区分の両方を選択してください。')
        return attrs


class ReceptionSerializer(serializers.Serializer):
    customer = ReceptionCustomerSerializer()
    family_members = ReceptionFamilyMemberSerializer(many=True, required=False)
    company = ReceptionCompanySerializer(required=False)
    case = ReceptionCaseSerializer(required=False)

    def create(self, validated_data):
        customer_data = validated_data['customer']
        family_members_data = validated_data.get('family_members', [])
        company_data = validated_data.get('company') or {}
        case_data = validated_data.get('case') or {}

        with transaction.atomic():
            customer_data['gender'] = normalize_gender(customer_data.get('gender'))
            customer = Customer.objects.create(**customer_data)

            family_members = []
            for family_member_data in family_members_data:
                if not has_any_value(family_member_data):
                    continue
                existing_customer_id = family_member_data.pop('customer', None)
                relationship = normalize_relationship(family_member_data.pop('relationship', None))
                is_dependent = family_member_data.pop('is_dependent', False)
                note = family_member_data.pop('note', '')

                if existing_customer_id:
                    try:
                        family_customer = Customer.objects.get(pk=existing_customer_id)
                    except Customer.DoesNotExist:
                        raise serializers.ValidationError(
                            {'family_members': f'指定された顧客（id={existing_customer_id}）が見つかりません。'}
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

                family_members.append(
                    FamilyMember.objects.create(
                        customer=customer,
                        family_customer=family_customer,
                        relationship=relationship,
                        is_dependent=is_dependent,
                        note=note,
                    ),
                )

            company = None
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
            if case_data.get('case_type_master') and case_data.get('application_category'):
                case = Case.objects.create(
                    case_type_master=case_data['case_type_master'],
                    application_category=case_data['application_category'],
                    customer=customer,
                    company=company,
                    responsible_employee_id=case_data.get('responsible_employee'),
                    accepted_at=case_data.get('accepted_at'),
                )
                Timeline.objects.create(
                    case=case,
                    title='新規受付',
                    content='新規受付ページから案件を作成しました。',
                    is_visible_to_client=False,
                )

        return {
            'customer': customer.id,
            'company': company.id if company else None,
            'case': case.id if case else None,
            'case_number': case.case_number if case else None,
            'family_members': [family_member.id for family_member in family_members],
        }
