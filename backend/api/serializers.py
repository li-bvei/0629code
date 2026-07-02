from django.db import transaction
from rest_framework import serializers

from apps.cases.models import Case
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
        if has_any_value(attrs) and not attrs.get('name'):
            raise serializers.ValidationError({'name': '家族の氏名を入力してください。'})
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
    case_type = serializers.CharField()
    status = serializers.CharField()
    responsible_employee = serializers.IntegerField(required=False, allow_null=True)
    accepted_at = serializers.DateField(required=False, allow_null=True)

    def to_internal_value(self, data):
        data = data.copy()
        if data.get('responsible_employee') == '':
            data['responsible_employee'] = None
        return super().to_internal_value(data)


class ReceptionSerializer(serializers.Serializer):
    customer = ReceptionCustomerSerializer()
    family_members = ReceptionFamilyMemberSerializer(many=True, required=False)
    company = ReceptionCompanySerializer(required=False)
    case = ReceptionCaseSerializer()

    def create(self, validated_data):
        customer_data = validated_data['customer']
        family_members_data = validated_data.get('family_members', [])
        company_data = validated_data.get('company') or {}
        case_data = validated_data['case']

        with transaction.atomic():
            customer_data['gender'] = normalize_gender(customer_data.get('gender'))
            customer = Customer.objects.create(**customer_data)

            family_members = []
            for family_member_data in family_members_data:
                if not has_any_value(family_member_data):
                    continue
                family_member_data['gender'] = normalize_gender(family_member_data.get('gender'))
                family_member_data['relationship'] = normalize_relationship(
                    family_member_data.get('relationship'),
                )
                family_members.append(
                    FamilyMember.objects.create(customer=customer, **family_member_data),
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

            case = Case.objects.create(
                case_type=case_data['case_type'],
                status=case_data['status'],
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
            'case': case.id,
            'case_number': case.case_number,
            'family_members': [family_member.id for family_member in family_members],
        }
