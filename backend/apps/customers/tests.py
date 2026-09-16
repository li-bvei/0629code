from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cases.models import Case
from apps.companies.models import Company, CompanyStaff
from apps.timelines.models import Timeline

from .models import Customer, FamilyMember


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

    def test_customer_detail_returns_360_summary_and_recent_activity(self):
        active_case = self.create_case(
            'CUS-SUMMARY-ACTIVE',
            Case.REGISTRATION_STATUS_ACTIVE,
            Case.STATUS_UNDER_REVIEW,
            self.case_company,
        )
        self.create_case(
            'CUS-SUMMARY-HISTORY',
            Case.REGISTRATION_STATUS_ACTIVE,
            Case.STATUS_COMPLETED,
            self.case_company,
        )
        timeline = Timeline.objects.create(
            case=active_case,
            occurred_at='2026-09-16',
            title='入管へ提出',
            content='受付番号を確認',
        )

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['summary']['active_cases_count'], 1)
        self.assertEqual(response.data['summary']['historical_cases_count'], 1)
        self.assertEqual(response.data['summary']['company_count'], 3)
        self.assertEqual(
            response.data['summary']['primary_case']['case_number'],
            active_case.case_number,
        )
        self.assertEqual(response.data['recent_activities'][0]['id'], timeline.id)
        self.assertEqual(response.data['recent_activities'][0]['case_number'], active_case.case_number)

    def test_related_company_summary_includes_relationships_without_bank_data(self):
        self.direct_company.bank_account_number = '1234567'
        self.direct_company.save()
        CompanyStaff.objects.create(
            company=self.direct_company,
            customer=self.customer,
            name=self.customer.name,
            position='代表取締役',
        )

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        self.assertEqual(response.status_code, 200)
        company = next(
            item for item in response.data['related_companies']
            if item['id'] == self.direct_company.id
        )
        self.assertEqual(company['relation_types'], ['representative', 'staff'])
        self.assertEqual(company['positions'], ['代表取締役'])
        self.assertNotIn('bank_account_number', company)
        self.assertNotIn('corporate_number', company)

    def test_customer_detail_does_not_return_plain_my_number(self):
        self.customer.my_number = '123456789012'
        self.customer.save()

        response = self.client.get(f'/api/customers/{self.customer.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('my_number', response.data)
        self.assertTrue(response.data['has_my_number'])

    def test_family_member_response_does_not_return_plain_my_number(self):
        self.other_customer.my_number = '987654321098'
        self.other_customer.email = 'family@example.com'
        self.other_customer.passport_no = 'TR1234567'
        self.other_customer.save()
        FamilyMember.objects.create(
            customer=self.customer,
            family_customer=self.other_customer,
            relationship=FamilyMember.RELATIONSHIP_SPOUSE,
        )

        response = self.client.get('/api/family-members/', {'customer': self.customer.id})

        self.assertEqual(response.status_code, 200)
        member = response.data['results'][0]
        self.assertNotIn('my_number', member)
        self.assertTrue(member['has_my_number'])
        self.assertEqual(member['email'], 'family@example.com')
        self.assertEqual(member['passport_no'], 'TR1234567')


class CustomerRemoteSearchTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='customer-remote-search',
            password='password',
        )
        self.client.force_authenticate(self.user)

    def test_search_finds_customer_beyond_first_page(self):
        for i in range(25):
            Customer.objects.create(name=f'一般顧客{i:02d}', birth_date='1990-01-01')
        target = Customer.objects.create(
            name='山田太郎', name_kana='ヤマダタロウ', birth_date='1985-05-05',
            phone='09011112222', residence_card_no='AB12345678CD',
        )

        by_name = self.client.get('/api/customers/', {'search': '山田'})
        self.assertEqual(by_name.status_code, 200)
        self.assertEqual([r['id'] for r in by_name.data['results']], [target.id])

        by_kana = self.client.get('/api/customers/', {'search': 'ヤマダ'})
        self.assertIn(target.id, [r['id'] for r in by_kana.data['results']])

        by_card = self.client.get('/api/customers/', {'search': 'AB12345678CD'})
        self.assertEqual([r['id'] for r in by_card.data['results']], [target.id])

    def test_search_matches_case_number(self):
        customer = Customer.objects.create(name='佐藤花子', birth_date='1990-01-01')
        Case.objects.create(
            case_number='技人国-更新-202609-佐藤花子-0001',
            case_type='更新',
            status=Case.STATUS_ACCEPTED,
            customer=customer,
        )
        for i in range(22):
            Customer.objects.create(name=f'ダミー{i:02d}', birth_date='1990-01-01')

        response = self.client.get('/api/customers/', {'search': '202609-佐藤花子'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(customer.id, [r['id'] for r in response.data['results']])
