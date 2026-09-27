from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cases.models import Case, CaseApplicationCategory, CaseChecklistTemplate, CaseChecklistTemplateItem, CaseTypeMaster
from apps.customers.models import Customer
from apps.timelines.models import Timeline

from .models import ReceptionIdempotencyRecord
from apps.authentication.testing import grant_full_business_access


class CustomerMatchApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username='match-test', password='pw')
        grant_full_business_access(self.user, employee_name='テスト担当者')
        self.client.force_authenticate(self.user)

    def test_name_and_birthdate_is_strong_match(self):
        target = Customer.objects.create(name='李 明', name_kana='リ メイ', birth_date='1990-01-01', phone='09011112222')
        Customer.objects.create(name='王 華', birth_date='1992-02-02')

        response = self.client.post('/api/customers/match/', {
            'name': '李明',
            'birth_date': '1990-01-01',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        candidates = response.json()['candidates']
        self.assertEqual(candidates[0]['customer_id'], target.id)
        self.assertEqual(candidates[0]['match_strength'], 'strong')

    def test_residence_card_number_is_strong_match(self):
        target = Customer.objects.create(name='別名でも可', birth_date='1980-03-03', residence_card_no='AB12345678CD')

        response = self.client.post('/api/customers/match/', {
            'name': 'ぜんぜん違う名前',
            'residence_card_number': 'AB12345678CD',
        }, format='json')

        candidates = response.json()['candidates']
        self.assertEqual(candidates[0]['customer_id'], target.id)
        self.assertEqual(candidates[0]['match_strength'], 'strong')

    def test_no_candidates_for_unrelated_input(self):
        Customer.objects.create(name='田中太郎', birth_date='1990-01-01')
        response = self.client.post('/api/customers/match/', {'name': '存在しない氏名'}, format='json')
        self.assertEqual(response.json()['candidates'], [])

    def test_partial_name_with_birthdate_is_medium_not_strong(self):
        # 氏名が部分一致（完全一致ではない）の場合、生年月日が一致していても
        # 同姓同名の別人の可能性があるため strong にはしない。
        target = Customer.objects.create(name='田中太郎', birth_date='1990-01-01')

        response = self.client.post('/api/customers/match/', {
            'name': '田中',
            'birth_date': '1990-01-01',
        }, format='json')

        candidates = response.json()['candidates']
        self.assertEqual(candidates[0]['customer_id'], target.id)
        self.assertEqual(candidates[0]['match_strength'], 'medium')

    def test_full_name_with_hyphenated_phone_is_medium_match(self):
        target = Customer.objects.create(name='佐藤花子', birth_date='1988-08-08', phone='09011112222')

        response = self.client.post('/api/customers/match/', {
            'name': '佐藤花子',
            'phone': '+81-90-1111-2222',
        }, format='json')

        candidates = response.json()['candidates']
        self.assertEqual(candidates[0]['customer_id'], target.id)
        self.assertEqual(candidates[0]['match_strength'], 'medium')
        self.assertIn('電話番号', candidates[0]['match_reason'])

    def test_partial_name_with_phone_only_is_weak(self):
        target = Customer.objects.create(name='鈴木一郎', birth_date='1975-01-01', phone='08033334444')

        response = self.client.post('/api/customers/match/', {
            'name': '鈴木',
            'phone': '080-3333-4444',
        }, format='json')

        candidates = response.json()['candidates']
        self.assertEqual(candidates[0]['customer_id'], target.id)
        self.assertEqual(candidates[0]['match_strength'], 'weak')


class ReceptionApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username='reception-test', password='pw')
        grant_full_business_access(self.user, employee_name='テスト担当者')
        self.client.force_authenticate(self.user)
        self.case_type, _ = CaseTypeMaster.objects.update_or_create(
            code='eng', defaults={'name': '技人国テスト', 'number_abbreviation': '技人国', 'sort_order': 1},
        )
        self.category, _ = CaseApplicationCategory.objects.update_or_create(
            code='renewal', defaults={'name': '更新テスト', 'number_abbreviation': '更新', 'sort_order': 1},
        )
        template = CaseChecklistTemplate.objects.create(
            name='技人国更新', case_type_master=self.case_type, application_category=self.category,
        )
        for i in range(3):
            CaseChecklistTemplateItem.objects.create(template=template, name=f'資料{i}', sort_order=i)

    def test_reception_with_existing_customer_reuses_and_creates_case(self):
        existing = Customer.objects.create(name='既存 顧客', birth_date='1990-01-01')

        response = self.client.post('/api/receptions/', {
            'existing_customer_id': existing.id,
            'case': {
                'case_type_master': self.case_type.id,
                'application_category': self.category.id,
            },
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertTrue(body['customer_reused'])
        self.assertEqual(body['customer'], existing.id)
        self.assertEqual(Customer.objects.count(), 1)
        case = Case.objects.get(id=body['case'])
        self.assertEqual(case.customer_id, existing.id)
        self.assertEqual(body['checklist_item_count'], 3)
        self.assertEqual(case.checklist_items.count(), 3)
        self.assertTrue(
            Timeline.objects.filter(case=case, event_type=Timeline.EVENT_CASE_CREATED).exists()
        )

    def test_reception_with_new_customer_creates_customer_and_case(self):
        response = self.client.post('/api/receptions/', {
            'customer': {'name': '新規 太郎', 'birth_date': '1995-06-06'},
            'case': {
                'case_type_master': self.case_type.id,
                'application_category': self.category.id,
            },
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertFalse(body['customer_reused'])
        self.assertEqual(Customer.objects.count(), 1)
        self.assertIsNotNone(body['case_number'])

    def test_reception_requires_customer_or_existing_id(self):
        response = self.client.post('/api/receptions/', {
            'case': {'case_type_master': self.case_type.id, 'application_category': self.category.id},
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_reception_with_existing_company_binds_case_without_duplicating_company(self):
        from apps.companies.models import Company

        existing_company = Company.objects.create(name='既存会社')

        response = self.client.post('/api/receptions/', {
            'customer': {'name': '会社紐付テスト', 'birth_date': '1992-02-02'},
            'existing_company_id': existing_company.id,
            'case': {
                'case_type_master': self.case_type.id,
                'application_category': self.category.id,
            },
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertTrue(body['company_reused'])
        self.assertEqual(body['company'], existing_company.id)
        self.assertEqual(Company.objects.count(), 1)
        case = Case.objects.get(id=body['case'])
        self.assertEqual(case.company_id, existing_company.id)

    def test_reception_rejects_unknown_existing_company_id(self):
        response = self.client.post('/api/receptions/', {
            'customer': {'name': '存在しない会社テスト', 'birth_date': '1992-02-02'},
            'existing_company_id': 999999,
            'case': {
                'case_type_master': self.case_type.id,
                'application_category': self.category.id,
            },
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('existing_company_id', response.json())


class ReceptionIdempotencyApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username='reception-idempotency-test', password='pw')
        grant_full_business_access(self.user, employee_name='テスト担当者')
        self.client.force_authenticate(self.user)
        self.case_type, _ = CaseTypeMaster.objects.update_or_create(
            code='idem-eng', defaults={'name': '冪等テスト種別', 'number_abbreviation': '冪等', 'sort_order': 1},
        )
        self.category, _ = CaseApplicationCategory.objects.update_or_create(
            code='idem-renewal', defaults={'name': '冪等テスト区分', 'number_abbreviation': '冪等', 'sort_order': 1},
        )

    def _payload(self, request_id, name='冪等 太郎'):
        return {
            'request_id': request_id,
            'customer': {'name': name, 'birth_date': '1993-03-03'},
            'case': {
                'case_type_master': self.case_type.id,
                'application_category': self.category.id,
            },
        }

    def test_duplicate_request_id_does_not_create_duplicate_records(self):
        first = self.client.post('/api/receptions/', self._payload('req-001'), format='json')
        second = self.client.post('/api/receptions/', self._payload('req-001'), format='json')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Case.objects.count(), 1)

    def test_different_request_id_creates_independent_records(self):
        self.client.post('/api/receptions/', self._payload('req-a', name='顧客A'), format='json')
        self.client.post('/api/receptions/', self._payload('req-b', name='顧客B'), format='json')

        self.assertEqual(Customer.objects.count(), 2)
        self.assertEqual(Case.objects.count(), 2)

    def test_in_progress_request_id_returns_conflict(self):
        ReceptionIdempotencyRecord.objects.create(request_id='req-pending', response=None)

        response = self.client.post('/api/receptions/', self._payload('req-pending'), format='json')

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Customer.objects.count(), 0)

    def test_failed_attempt_allows_retry_with_same_request_id(self):
        bad_payload = {'request_id': 'req-retry', 'case': {}}
        failed = self.client.post('/api/receptions/', bad_payload, format='json')
        self.assertEqual(failed.status_code, 400)
        self.assertFalse(ReceptionIdempotencyRecord.objects.filter(request_id='req-retry').exists())

        retried = self.client.post('/api/receptions/', self._payload('req-retry'), format='json')
        self.assertEqual(retried.status_code, 201)
        self.assertEqual(Customer.objects.count(), 1)

    def test_request_id_is_optional_and_backward_compatible(self):
        response = self.client.post('/api/receptions/', {
            'customer': {'name': '冪等キーなし', 'birth_date': '1990-01-01'},
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ReceptionIdempotencyRecord.objects.count(), 0)
