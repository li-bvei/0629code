from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cases.models import Case
from apps.companies.models import Company

from .models import Customer


class CustomerDetailRelatedDataTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='customer-related-test',
            password='password',
        )
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(
            name='関連確認顧客',
            birth_date='1990-01-01',
        )
        self.other_customer = Customer.objects.create(
            name='別顧客',
            birth_date='1991-01-01',
        )
        self.direct_company = Company.objects.create(
            name='代表者直接会社',
            representative_customer=self.customer,
        )
        self.case_company = Company.objects.create(name='案件関連会社')
        self.duplicate_company = Company.objects.create(
            name='重複確認会社',
            representative_customer=self.customer,
        )
        self.other_company = Company.objects.create(
            name='別顧客会社',
            representative_customer=self.other_customer,
        )

    def create_case(self, case_number, registration_status, status, company=None):
        return Case.objects.create(
            case_number=case_number,
            case_type='更新',
            registration_status=registration_status,
            status=status,
            customer=self.customer,
            company=company,
        )

    def test_customer_detail_keeps_all_historical_related_cases(self):
        self.create_case(
            'CUS-ACTIVE-001',
            Case.REGISTRATION_STATUS_ACTIVE,
            Case.STATUS_ACCEPTED,
            self.case_company,
        )
        self.create_case(
            'CUS-COMPLETED-001',
            Case.REGISTRATION_STATUS_ACTIVE,
            Case.STATUS_COMPLETED,
            self.case_company,
        )
        self.create_case(
            'CUS-ARCHIVED-001',
            Case.REGISTRATION_STATUS_ARCHIVED,
            Case.STATUS_ACCEPTED,
            self.case_company,
        )
        self.create_case(
            'CUS-INACTIVE-001',
            Case.REGISTRATION_STATUS_INACTIVE,
            Case.STATUS_ACCEPTED,
            self.case_company,
        )
        self.create_case(
            'CUS-REJECTED-001',
            Case.REGISTRATION_STATUS_ACTIVE,
            Case.STATUS_REJECTED,
            self.case_company,
        )
        self.create_case(
            'CUS-WITHDRAWN-001',
            Case.REGISTRATION_STATUS_ACTIVE,
            Case.STATUS_WITHDRAWN,
            self.case_company,
        )

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        self.assertEqual(response.status_code, 200)
        case_numbers = {item['case_number'] for item in response.data['related_cases']}
        self.assertEqual(case_numbers, {
            'CUS-ACTIVE-001',
            'CUS-COMPLETED-001',
            'CUS-ARCHIVED-001',
            'CUS-INACTIVE-001',
            'CUS-REJECTED-001',
            'CUS-WITHDRAWN-001',
        })

    def test_customer_detail_merges_direct_and_case_related_companies_without_duplicates(self):
        self.create_case(
            'CUS-COMPANY-001',
            Case.REGISTRATION_STATUS_ARCHIVED,
            Case.STATUS_COMPLETED,
            self.case_company,
        )
        self.create_case(
            'CUS-COMPANY-002',
            Case.REGISTRATION_STATUS_ACTIVE,
            Case.STATUS_ACCEPTED,
            self.duplicate_company,
        )
        Case.objects.create(
            case_number='OTHER-COMPANY-001',
            case_type='更新',
            registration_status=Case.REGISTRATION_STATUS_ACTIVE,
            status=Case.STATUS_ACCEPTED,
            customer=self.other_customer,
            company=self.other_company,
        )

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        self.assertEqual(response.status_code, 200)
        company_ids = [item['id'] for item in response.data['related_companies']]
        self.assertIn(self.direct_company.id, company_ids)
        self.assertIn(self.case_company.id, company_ids)
        self.assertIn(self.duplicate_company.id, company_ids)
        self.assertNotIn(self.other_company.id, company_ids)
        self.assertEqual(len(company_ids), len(set(company_ids)))

    def test_customer_detail_returns_empty_related_companies_when_none_exist(self):
        customer = Customer.objects.create(
            name='関連なし顧客',
            birth_date='1992-01-01',
        )

        response = self.client.get(f'/api/customers/{customer.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['related_companies'], [])
