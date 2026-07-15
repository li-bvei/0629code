from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.customers.models import Customer

from .models import Case
from .utils import (
    generate_case_number,
    get_case_application_category,
    get_case_number_prefix,
    sanitize_case_number_name,
)


TOKYO = ZoneInfo('Asia/Tokyo')


class CaseNumberTestCase(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name='李明',
            birth_date='1990-01-01',
        )
        self.other_customer = Customer.objects.create(
            name='王華',
            birth_date='1992-02-02',
        )

    def create_case(self, case_type='経営・管理新規申請', customer=None, **kwargs):
        return Case.objects.create(
            case_type=case_type,
            status=Case.STATUS_OPEN,
            customer=customer or self.customer,
            **kwargs,
        )

    def patch_now(self, year, month, day=10):
        return patch(
            'apps.cases.utils.timezone.now',
            return_value=datetime(year, month, day, 9, 0, tzinfo=TOKYO),
        )

    def test_business_manager_renewal_number(self):
        with self.patch_now(2026, 5):
            case = self.create_case('経営・管理更新')

        self.assertEqual(case.case_number, '経管-202605-更新-李明-0001')

    def test_business_manager_application_number(self):
        with self.patch_now(2026, 5):
            case = self.create_case('経営・管理新規申請')

        self.assertEqual(case.case_number, '経管-202605-申請-李明-0001')

    def test_same_full_prefix_increments(self):
        with self.patch_now(2026, 5):
            first = self.create_case('経営・管理更新')
            second = self.create_case('経営・管理更新')

        self.assertEqual(first.case_number, '経管-202605-更新-李明-0001')
        self.assertEqual(second.case_number, '経管-202605-更新-李明-0002')

    def test_different_customer_names_have_independent_sequence(self):
        with self.patch_now(2026, 5):
            first = self.create_case('経営・管理更新', customer=self.customer)
            second = self.create_case('経営・管理更新', customer=self.other_customer)

        self.assertEqual(first.case_number, '経管-202605-更新-李明-0001')
        self.assertEqual(second.case_number, '経管-202605-更新-王華-0001')

    def test_application_and_renewal_have_independent_sequence(self):
        with self.patch_now(2026, 5):
            application = self.create_case('経営・管理新規申請')
            renewal = self.create_case('経営・管理更新')

        self.assertEqual(application.case_number, '経管-202605-申請-李明-0001')
        self.assertEqual(renewal.case_number, '経管-202605-更新-李明-0001')

    def test_different_case_prefixes_have_independent_sequence(self):
        with self.patch_now(2026, 5):
            business = self.create_case('経営・管理更新')
            engineer = self.create_case('技人国ビザ更新')

        self.assertEqual(business.case_number, '経管-202605-更新-李明-0001')
        self.assertEqual(engineer.case_number, '技人国-202605-更新-李明-0001')

    def test_sequence_resets_next_month(self):
        with self.patch_now(2026, 5):
            first = self.create_case('経営・管理更新')
        with self.patch_now(2026, 6):
            next_month = self.create_case('経営・管理更新')

        self.assertEqual(first.case_number, '経管-202605-更新-李明-0001')
        self.assertEqual(next_month.case_number, '経管-202606-更新-李明-0001')

    def test_name_sanitizing(self):
        self.assertEqual(sanitize_case_number_name(' 李  明 '), '李 明')
        self.assertEqual(sanitize_case_number_name('ANNA-MARIA'), 'ANNAMARIA')
        self.assertEqual(sanitize_case_number_name('王\n華\t太郎'), '王 華 太郎')
        self.assertEqual(sanitize_case_number_name(''), '氏名未登録')

    def test_generated_number_uses_sanitized_name(self):
        customer = Customer.objects.create(
            name='ANNA-MARIA',
            birth_date='1991-01-01',
        )
        with self.patch_now(2026, 5):
            case = self.create_case('経営・管理更新', customer=customer)

        self.assertEqual(case.case_number, '経管-202605-更新-ANNAMARIA-0001')

    def test_empty_name_uses_placeholder(self):
        customer = Customer.objects.create(
            name=' ',
            birth_date='1991-01-01',
        )
        with self.patch_now(2026, 5):
            case = self.create_case('経営・管理新規申請', customer=customer)

        self.assertEqual(case.case_number, '経管-202605-申請-氏名未登録-0001')

    def test_generate_case_number_without_customer_uses_placeholder(self):
        self.assertEqual(
            generate_case_number('経営・管理新規申請', customer=None, created_at=datetime(2026, 5, 1, tzinfo=TOKYO)),
            '経管-202605-申請-氏名未登録-0001',
        )

    def test_old_and_irregular_case_numbers_are_ignored(self):
        Case.objects.create(
            case_number='CASE-2026-9999',
            case_type='経営・管理更新',
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )
        Case.objects.create(
            case_number='経管-202605-0001',
            case_type='経営・管理更新',
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )

        self.assertEqual(
            generate_case_number('経営・管理更新', self.customer, datetime(2026, 5, 1, tzinfo=TOKYO)),
            '経管-202605-更新-李明-0001',
        )

    def test_uses_max_sequence_instead_of_count(self):
        Case.objects.create(
            case_number='経管-202605-更新-李明-0001',
            case_type='経営・管理更新',
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )
        Case.objects.create(
            case_number='経管-202605-更新-李明-0003',
            case_type='経営・管理更新',
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )

        self.assertEqual(
            generate_case_number('経営・管理更新', self.customer, datetime(2026, 5, 1, tzinfo=TOKYO)),
            '経管-202605-更新-李明-0004',
        )

    def test_sequence_can_exceed_9999(self):
        Case.objects.create(
            case_number='経管-202605-更新-李明-9999',
            case_type='経営・管理更新',
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )

        self.assertEqual(
            generate_case_number('経営・管理更新', self.customer, datetime(2026, 5, 1, tzinfo=TOKYO)),
            '経管-202605-更新-李明-10000',
        )

    def test_case_number_does_not_change_on_case_type_or_customer_name_update(self):
        with self.patch_now(2026, 5):
            case = self.create_case('経営・管理更新')

        self.customer.name = '李明華'
        self.customer.save()
        case.case_type = '技人国ビザ更新'
        case.status = Case.STATUS_IN_PROGRESS
        case.save()
        case.refresh_from_db()

        self.assertEqual(case.case_number, '経管-202605-更新-李明-0001')

    def test_prefix_mapping_and_application_category(self):
        self.assertEqual(get_case_number_prefix('不明な案件'), 'その他')
        self.assertEqual(get_case_application_category('在留更新'), '更新')
        self.assertEqual(get_case_application_category('永住許可申請'), '申請')

    def test_unique_constraint_is_active(self):
        self.create_case(case_number='経管-202605-更新-李明-0001')
        with self.assertRaises(IntegrityError):
            self.create_case(case_number='経管-202605-更新-李明-0001')

    def test_retries_when_generated_number_conflicts(self):
        self.create_case(case_number='経管-202605-更新-李明-0001')
        with patch('apps.cases.utils.generate_case_number', side_effect=[
            '経管-202605-更新-李明-0001',
            '経管-202605-更新-李明-0002',
        ]):
            case = self.create_case('経営・管理更新')

        self.assertEqual(case.case_number, '経管-202605-更新-李明-0002')


class CaseNumberApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='case-number-test',
            password='password',
        )
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(
            name='張偉',
            birth_date='1990-01-01',
        )

    def test_api_create_returns_generated_case_number_and_ignores_payload_number(self):
        with patch(
            'apps.cases.utils.timezone.now',
            return_value=datetime(2026, 5, 10, 9, 0, tzinfo=TOKYO),
        ):
            response = self.client.post('/api/cases/', {
                'case_number': 'MANUAL-001',
                'case_type': '永住許可申請',
                'status': Case.STATUS_OPEN,
                'customer': self.customer.id,
            }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['case_number'], '永住-202605-申請-張偉-0001')
        self.assertEqual(Case.objects.get().case_number, '永住-202605-申請-張偉-0001')
