from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.customers.models import Customer
from apps.timelines.models import Timeline

from .models import Case, CaseApplicationCategory, CaseChecklistItem, CaseChecklistTemplate, CaseChecklistTemplateItem, CaseTypeMaster
from .utils import generate_case_number, sanitize_case_number_name


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
        self.business_type, _ = CaseTypeMaster.objects.update_or_create(
            code='business_manager',
            defaults={'name': '経営・管理', 'number_abbreviation': '経管', 'sort_order': 10},
        )
        self.engineer_type, _ = CaseTypeMaster.objects.update_or_create(
            code='engineer_humanities',
            defaults={'name': '技術・人文知識・国際業務', 'number_abbreviation': '技人国', 'sort_order': 20},
        )
        self.permanent_type, _ = CaseTypeMaster.objects.update_or_create(
            code='permanent_residence',
            defaults={'name': '永住許可', 'number_abbreviation': '永住', 'sort_order': 30},
        )
        self.new_category, _ = CaseApplicationCategory.objects.update_or_create(
            code='new',
            defaults={'name': '申請', 'number_abbreviation': '申請', 'sort_order': 10},
        )
        self.renewal_category, _ = CaseApplicationCategory.objects.update_or_create(
            code='renewal',
            defaults={'name': '更新', 'number_abbreviation': '更新', 'sort_order': 20},
        )

    def create_case(self, case_type='経営・管理新規申請', customer=None, **kwargs):
        case_type_master = kwargs.pop('case_type_master', self.engineer_type if '技人国' in case_type else self.business_type)
        application_category = kwargs.pop('application_category', self.renewal_category if '更新' in case_type else self.new_category)
        return Case.objects.create(
            case_type=case_type,
            case_type_master=case_type_master,
            application_category=application_category,
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

        self.assertEqual(case.case_number, '経管-更新-202605-李明-0001')

    def test_business_manager_application_number(self):
        with self.patch_now(2026, 5):
            case = self.create_case('経営・管理新規申請')

        self.assertEqual(case.case_number, '経管-申請-202605-李明-0001')

    def test_same_full_prefix_increments(self):
        with self.patch_now(2026, 5):
            first = self.create_case('経営・管理更新')
            second = self.create_case('経営・管理更新')

        self.assertEqual(first.case_number, '経管-更新-202605-李明-0001')
        self.assertEqual(second.case_number, '経管-更新-202605-李明-0002')

    def test_different_customer_names_have_independent_sequence(self):
        with self.patch_now(2026, 5):
            first = self.create_case('経営・管理更新', customer=self.customer)
            second = self.create_case('経営・管理更新', customer=self.other_customer)

        self.assertEqual(first.case_number, '経管-更新-202605-李明-0001')
        self.assertEqual(second.case_number, '経管-更新-202605-王華-0001')

    def test_application_and_renewal_have_independent_sequence(self):
        with self.patch_now(2026, 5):
            application = self.create_case('経営・管理新規申請')
            renewal = self.create_case('経営・管理更新')

        self.assertEqual(application.case_number, '経管-申請-202605-李明-0001')
        self.assertEqual(renewal.case_number, '経管-更新-202605-李明-0001')

    def test_different_case_prefixes_have_independent_sequence(self):
        with self.patch_now(2026, 5):
            business = self.create_case('経営・管理更新')
            engineer = self.create_case('技人国ビザ更新')

        self.assertEqual(business.case_number, '経管-更新-202605-李明-0001')
        self.assertEqual(engineer.case_number, '技人国-更新-202605-李明-0001')

    def test_sequence_resets_next_month(self):
        with self.patch_now(2026, 5):
            first = self.create_case('経営・管理更新')
        with self.patch_now(2026, 6):
            next_month = self.create_case('経営・管理更新')

        self.assertEqual(first.case_number, '経管-更新-202605-李明-0001')
        self.assertEqual(next_month.case_number, '経管-更新-202606-李明-0001')

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

        self.assertEqual(case.case_number, '経管-更新-202605-ANNAMARIA-0001')

    def test_empty_name_uses_placeholder(self):
        customer = Customer.objects.create(
            name=' ',
            birth_date='1991-01-01',
        )
        with self.patch_now(2026, 5):
            case = self.create_case('経営・管理新規申請', customer=customer)

        self.assertEqual(case.case_number, '経管-申請-202605-氏名未登録-0001')

    def test_generate_case_number_without_customer_uses_placeholder(self):
        self.assertEqual(
            generate_case_number(
                self.business_type,
                self.new_category,
                customer=None,
                created_at=datetime(2026, 5, 1, tzinfo=TOKYO),
            ),
            '経管-申請-202605-氏名未登録-0001',
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
            generate_case_number(self.business_type, self.renewal_category, self.customer, datetime(2026, 5, 1, tzinfo=TOKYO)),
            '経管-更新-202605-李明-0001',
        )

    def test_uses_max_sequence_instead_of_count(self):
        Case.objects.create(
            case_number='経管-更新-202605-李明-0001',
            case_type='経営・管理更新',
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )
        Case.objects.create(
            case_number='経管-更新-202605-李明-0003',
            case_type='経営・管理更新',
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )

        self.assertEqual(
            generate_case_number(self.business_type, self.renewal_category, self.customer, datetime(2026, 5, 1, tzinfo=TOKYO)),
            '経管-更新-202605-李明-0004',
        )

    def test_sequence_can_exceed_9999(self):
        Case.objects.create(
            case_number='経管-更新-202605-李明-9999',
            case_type='経営・管理更新',
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )

        self.assertEqual(
            generate_case_number(self.business_type, self.renewal_category, self.customer, datetime(2026, 5, 1, tzinfo=TOKYO)),
            '経管-更新-202605-李明-10000',
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

        self.assertEqual(case.case_number, '経管-更新-202605-李明-0001')

    def test_number_generation_uses_master_abbreviations(self):
        self.assertEqual(
            generate_case_number(self.engineer_type, self.renewal_category, self.customer, datetime(2026, 5, 1, tzinfo=TOKYO)),
            '技人国-更新-202605-李明-0001',
        )

    def test_unique_constraint_is_active(self):
        self.create_case(case_number='経管-更新-202605-李明-0001')
        with self.assertRaises(IntegrityError):
            self.create_case(case_number='経管-更新-202605-李明-0001')

    def test_retries_when_generated_number_conflicts(self):
        self.create_case(case_number='経管-更新-202605-李明-0001')
        with patch('apps.cases.utils.generate_case_number', side_effect=[
            '経管-更新-202605-李明-0001',
            '経管-更新-202605-李明-0002',
        ]):
            case = self.create_case('経営・管理更新')

        self.assertEqual(case.case_number, '経管-更新-202605-李明-0002')


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
        self.business_type, _ = CaseTypeMaster.objects.update_or_create(
            code='business_manager',
            defaults={'name': '経営・管理', 'number_abbreviation': '経管'},
        )
        self.permanent_type, _ = CaseTypeMaster.objects.update_or_create(
            code='permanent_residence',
            defaults={'name': '永住許可', 'number_abbreviation': '永住'},
        )
        self.new_category, _ = CaseApplicationCategory.objects.update_or_create(
            code='new',
            defaults={'name': '申請', 'number_abbreviation': '申請'},
        )
        self.renewal_category, _ = CaseApplicationCategory.objects.update_or_create(
            code='renewal',
            defaults={'name': '更新', 'number_abbreviation': '更新'},
        )

    def test_api_create_returns_generated_case_number_and_ignores_payload_number(self):
        with patch(
            'apps.cases.utils.timezone.now',
            return_value=datetime(2026, 5, 10, 9, 0, tzinfo=TOKYO),
        ):
            response = self.client.post('/api/cases/', {
                'case_number': 'MANUAL-001',
                'case_type_master': self.permanent_type.id,
                'application_category': self.new_category.id,
                'status': Case.STATUS_OPEN,
                'customer': self.customer.id,
            }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['case_number'], '永住-申請-202605-張偉-0001')
        self.assertEqual(Case.objects.get().case_number, '永住-申請-202605-張偉-0001')

    def test_api_create_with_minimum_fields_generates_number_and_defaults(self):
        with patch(
            'apps.cases.utils.timezone.now',
            return_value=datetime(2026, 7, 10, 9, 0, tzinfo=TOKYO),
        ):
            response = self.client.post('/api/cases/', {
                'case_type_master': self.business_type.id,
                'application_category': self.renewal_category.id,
                'customer': self.customer.id,
                'accepted_at': None,
                'applied_at': None,
                'completed_at': None,
            }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['case_number'], '経管-更新-202607-張偉-0001')
        self.assertEqual(response.data['registration_status'], Case.REGISTRATION_STATUS_ACTIVE)
        self.assertEqual(response.data['status'], Case.STATUS_COLLECTING_DOCUMENTS)
        self.assertIsNone(response.data['accepted_at'])

    def test_api_create_rejects_invalid_status_with_field_error(self):
        response = self.client.post('/api/cases/', {
            'case_type_master': self.business_type.id,
            'application_category': self.renewal_category.id,
            'customer': self.customer.id,
            'status': '資料準備中',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('status', response.data)

    def test_case_number_does_not_recalculate_after_customer_name_change(self):
        with patch(
            'apps.cases.utils.timezone.now',
            return_value=datetime(2026, 7, 10, 9, 0, tzinfo=TOKYO),
        ):
            response = self.client.post('/api/cases/', {
                'case_type_master': self.business_type.id,
                'application_category': self.renewal_category.id,
                'customer': self.customer.id,
            }, format='json')

        self.assertEqual(response.status_code, 201)
        case = Case.objects.get(id=response.data['id'])
        self.customer.name = '張偉更新後'
        self.customer.save()
        case.case_type = '技人国ビザ更新'
        case.status = Case.STATUS_APPLIED
        case.save()
        case.refresh_from_db()
        self.assertEqual(case.case_number, '経管-更新-202607-張偉-0001')


class CaseRegistrationStatusApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='case-registration-status-test',
            password='password',
        )
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(
            name='登録状態テスト顧客',
            birth_date='1990-01-01',
        )
        self.company = Company.objects.create(name='登録状態テスト会社')
        self.active_case = Case.objects.create(
            case_number='REG-ACTIVE-001',
            case_type='更新',
            registration_status=Case.REGISTRATION_STATUS_ACTIVE,
            status=Case.STATUS_ACCEPTED,
            customer=self.customer,
            company=self.company,
        )
        self.inactive_case = Case.objects.create(
            case_number='REG-INACTIVE-001',
            case_type='更新',
            registration_status=Case.REGISTRATION_STATUS_INACTIVE,
            status=Case.STATUS_COMPLETED,
            customer=self.customer,
            company=self.company,
        )
        self.archived_case = Case.objects.create(
            case_number='REG-ARCHIVED-001',
            case_type='更新',
            registration_status=Case.REGISTRATION_STATUS_ARCHIVED,
            status=Case.STATUS_WITHDRAWN,
            customer=self.customer,
            company=self.company,
        )

    def get_case_numbers(self, params=None):
        response = self.client.get('/api/cases/', params or {})
        self.assertEqual(response.status_code, 200)
        return {item['case_number'] for item in response.data['results']}

    def test_registration_status_active_only_returns_active_cases(self):
        self.assertEqual(
            self.get_case_numbers({'registration_status': Case.REGISTRATION_STATUS_ACTIVE}),
            {'REG-ACTIVE-001'},
        )

    def test_registration_status_inactive_only_returns_inactive_cases(self):
        self.assertEqual(
            self.get_case_numbers({'registration_status': Case.REGISTRATION_STATUS_INACTIVE}),
            {'REG-INACTIVE-001'},
        )

    def test_registration_status_archived_only_returns_archived_cases(self):
        self.assertEqual(
            self.get_case_numbers({'registration_status': Case.REGISTRATION_STATUS_ARCHIVED}),
            {'REG-ARCHIVED-001'},
        )

    def test_missing_registration_status_returns_all_registration_statuses(self):
        self.assertEqual(
            self.get_case_numbers(),
            {'REG-ACTIVE-001', 'REG-INACTIVE-001', 'REG-ARCHIVED-001'},
        )

    def test_archived_case_detail_is_available(self):
        response = self.client.get(f'/api/cases/{self.archived_case.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['case_number'], 'REG-ARCHIVED-001')
        self.assertEqual(response.data['company'], self.company.id)

    def test_work_views_filter_expected_case_sets(self):
        active_status_cases = {}
        for status_value in [
            Case.STATUS_CONSULTATION,
            Case.STATUS_COLLECTING_DOCUMENTS,
            Case.STATUS_PREPARING_DOCUMENTS,
            Case.STATUS_READY_TO_APPLY,
            Case.STATUS_APPLIED,
            Case.STATUS_UNDER_REVIEW,
            Case.STATUS_ADDITIONAL_DOCUMENTS,
            Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED,
            Case.STATUS_APPROVED,
            Case.STATUS_REJECTED,
            Case.STATUS_WITHDRAWN,
        ]:
            active_status_cases[status_value] = Case.objects.create(
                case_number=f'REG-{status_value.upper()}-001',
                case_type='更新',
                registration_status=Case.REGISTRATION_STATUS_ACTIVE,
                status=status_value,
                customer=self.customer,
            )
        active_completed_case = Case.objects.create(
            case_number='REG-COMPLETED-001',
            case_type='更新',
            registration_status=Case.REGISTRATION_STATUS_ACTIVE,
            status=Case.STATUS_COMPLETED,
            customer=self.customer,
            completed_at='2026-07-21',
        )
        archived_completed_case = Case.objects.create(
            case_number='REG-ARCHIVED-COMPLETED-001',
            case_type='更新',
            registration_status=Case.REGISTRATION_STATUS_ARCHIVED,
            status=Case.STATUS_COMPLETED,
            customer=self.customer,
            completed_at='2026-07-22',
        )

        incomplete_numbers = self.get_case_numbers({'view': 'incomplete'})
        self.assertIn(self.active_case.case_number, incomplete_numbers)
        for case in active_status_cases.values():
            self.assertIn(case.case_number, incomplete_numbers)
        self.assertNotIn(active_completed_case.case_number, incomplete_numbers)
        self.assertNotIn(self.inactive_case.case_number, incomplete_numbers)
        self.assertNotIn(self.archived_case.case_number, incomplete_numbers)

        completed_numbers = self.get_case_numbers({'view': 'completed'})
        self.assertEqual(
            completed_numbers,
            {
                active_completed_case.case_number,
                self.inactive_case.case_number,
                archived_completed_case.case_number,
            },
        )
        completed_with_legacy_registration_param = self.get_case_numbers({
            'view': 'completed',
            'registration_status': Case.REGISTRATION_STATUS_ACTIVE,
        })
        self.assertEqual(completed_with_legacy_registration_param, completed_numbers)

        all_numbers = self.get_case_numbers({'view': 'all'})
        self.assertIn(self.active_case.case_number, all_numbers)
        self.assertIn(self.inactive_case.case_number, all_numbers)
        self.assertIn(self.archived_case.case_number, all_numbers)
        self.assertIn(active_completed_case.case_number, all_numbers)
        self.assertIn(archived_completed_case.case_number, all_numbers)
        for case in active_status_cases.values():
            self.assertIn(case.case_number, all_numbers)

        accepted_numbers = self.get_case_numbers({
            'view': 'incomplete',
            'status': Case.STATUS_ACCEPTED,
        })
        self.assertEqual(accepted_numbers, {self.active_case.case_number})

        all_with_legacy_registration_param = self.get_case_numbers({
            'view': 'all',
            'registration_status': Case.REGISTRATION_STATUS_ACTIVE,
        })
        self.assertEqual(all_with_legacy_registration_param, all_numbers)


class CaseChecklistFieldTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='checklist-field-test',
            password='password',
        )
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(
            name='王小明',
            birth_date='1990-01-01',
        )
        self.case_type_master, _ = CaseTypeMaster.objects.update_or_create(
            code='business_manager',
            defaults={'name': '経営・管理', 'number_abbreviation': '経管'},
        )
        self.application_category, _ = CaseApplicationCategory.objects.update_or_create(
            code='renewal',
            defaults={'name': '更新', 'number_abbreviation': '更新'},
        )
        self.case = Case.objects.create(
            case_type='経営・管理更新',
            case_type_master=self.case_type_master,
            application_category=self.application_category,
            status=Case.STATUS_OPEN,
            customer=self.customer,
        )
        self.template = CaseChecklistTemplate.objects.create(name='更新用テンプレート')

    def test_template_item_new_fields_can_be_saved_and_read(self):
        item = CaseChecklistTemplateItem.objects.create(
            template=self.template,
            category='税務資料',
            name='納税証明書取得',
            responsible_party=CaseChecklistTemplateItem.RESPONSIBLE_PARTY_CUSTOMER,
            acquisition_place='大阪南税務署',
            required_details='納税証明書その3の3\n直近1年分',
            internal_note='内部確認のみ',
            customer_note='委任状が必要です',
            is_visible_to_customer=False,
            importance_level=CaseChecklistTemplateItem.IMPORTANCE_WARNING,
        )

        response = self.client.get(f'/api/case-checklist-template-items/{item.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['acquisition_place'], '大阪南税務署')
        self.assertEqual(response.data['required_details'], '納税証明書その3の3\n直近1年分')
        self.assertEqual(response.data['internal_note'], '内部確認のみ')
        self.assertEqual(response.data['customer_note'], '委任状が必要です')
        self.assertFalse(response.data['is_visible_to_customer'])
        self.assertEqual(response.data['importance_level'], 'warning')

    def test_invalid_importance_level_is_rejected(self):
        response = self.client.post('/api/case-checklist-template-items/', {
            'template': self.template.id,
            'category': '税務資料',
            'name': '不正項目',
            'item_type': CaseChecklistTemplateItem.ITEM_TYPE_DOCUMENT,
            'importance_level': 'critical',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('importance_level', response.data)

    def test_apply_template_copies_new_fields_and_keeps_order(self):
        first = CaseChecklistTemplateItem.objects.create(
            template=self.template,
            category='税務資料',
            name='納税証明書取得',
            sort_order=20,
            acquisition_place='大阪南税務署',
            required_details='納税証明書その3の3',
            internal_note='内部備考',
            customer_note='委任状が必要です',
            is_visible_to_customer=True,
            importance_level=CaseChecklistTemplateItem.IMPORTANCE_IMPORTANT,
        )
        CaseChecklistTemplateItem.objects.create(
            template=self.template,
            category='内部',
            name='内部確認',
            sort_order=10,
            is_active=False,
            acquisition_place='非表示',
        )
        deleted = CaseChecklistTemplateItem.objects.create(
            template=self.template,
            category='削除',
            name='削除済み',
            sort_order=30,
            deleted_at=datetime(2026, 7, 1, tzinfo=TOKYO),
        )

        response = self.client.post(f'/api/cases/{self.case.id}/apply-checklist-template/', {
            'template_id': self.template.id,
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data), 1)
        created = CaseChecklistItem.objects.get(source_template_item=first)
        self.assertEqual(created.acquisition_place, '大阪南税務署')
        self.assertEqual(created.required_details, '納税証明書その3の3')
        self.assertEqual(created.internal_note, '内部備考')
        self.assertEqual(created.customer_note, '委任状が必要です')
        self.assertTrue(created.is_visible_to_customer)
        self.assertEqual(created.importance_level, 'important')
        self.assertEqual(list(CaseChecklistItem.objects.values_list('name', flat=True)), ['納税証明書取得'])
        self.assertFalse(CaseChecklistItem.objects.filter(source_template_item=deleted).exists())

    def test_case_item_hidden_from_customer_can_be_saved(self):
        item = CaseChecklistItem.objects.create(
            case=self.case,
            category='内部',
            name='内部確認',
            is_visible_to_customer=False,
            importance_level=CaseChecklistTemplateItem.IMPORTANCE_NORMAL,
        )

        response = self.client.patch(f'/api/case-checklist-items/{item.id}/', {
            'customer_note': '顧客には出さない',
            'is_visible_to_customer': False,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['is_visible_to_customer'])
        self.assertEqual(response.data['customer_note'], '顧客には出さない')


class CaseStatusWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            username='case-status-test',
            password='password',
        )
        self.client.force_authenticate(self.user)
        self.customer = Customer.objects.create(
            name='王小明',
            birth_date='1990-01-01',
        )
        self.case_type_master, _ = CaseTypeMaster.objects.update_or_create(
            code='business_manager',
            defaults={'name': '経営・管理', 'number_abbreviation': '経管'},
        )
        self.application_category, _ = CaseApplicationCategory.objects.update_or_create(
            code='renewal',
            defaults={'name': '更新', 'number_abbreviation': '更新'},
        )
        self.case = Case.objects.create(
            case_type='経営・管理更新',
            case_type_master=self.case_type_master,
            application_category=self.application_category,
            customer=self.customer,
        )

    def test_new_case_defaults(self):
        self.assertEqual(self.case.registration_status, Case.REGISTRATION_STATUS_ACTIVE)
        self.assertEqual(self.case.status, Case.STATUS_ACCEPTED)

    def test_change_status_creates_timeline(self):
        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_COLLECTING_DOCUMENTS,
            'change_date': '2026-07-16',
            'note': '資料収集開始',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.STATUS_COLLECTING_DOCUMENTS)
        timeline = Timeline.objects.get(case=self.case, title='案件進捗変更')
        self.assertIn('受任済み → 資料準備中', timeline.content)
        self.assertIn('資料待ち開始日：2026-07-16', timeline.content)
        self.assertIn('資料収集開始', timeline.content)
        self.assertTrue(response.data['timeline_created'])
        self.assertEqual(response.data['event']['event_type'], 'case_status_changed')

    def test_status_change_saves_next_action_and_due_date(self):
        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_COLLECTING_DOCUMENTS,
            'change_date': '2026-07-16',
            'next_action': '顧客へ納税証明書を依頼',
            'next_action_due_at': '2026-07-20',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.next_action, '顧客へ納税証明書を依頼')
        self.assertEqual(str(self.case.next_action_due_at), '2026-07-20')
        self.assertIn('次の対応：顧客へ納税証明書を依頼', Timeline.objects.get(case=self.case).content)

    def test_case_detail_returns_progress_management_fields(self):
        self.case.status = Case.STATUS_COLLECTING_DOCUMENTS
        self.case.document_collection_started_at = '2026-07-01'
        self.case.next_action_due_at = '2026-07-10'
        self.case.save(update_fields=['status', 'document_collection_started_at', 'next_action_due_at'])

        with patch('apps.cases.serializers.timezone.localdate', return_value=datetime(2026, 7, 16, tzinfo=TOKYO).date()):
            response = self.client.get(f'/api/cases/{self.case.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data['progress_started_at']), '2026-07-01')
        self.assertEqual(response.data['progress_elapsed_days'], 15)
        self.assertEqual(response.data['progress_remaining_days'], -6)
        self.assertTrue(response.data['is_overdue'])

    def test_progress_info_update_does_not_change_status_and_creates_timeline(self):
        self.case.status = Case.STATUS_APPROVED
        self.case.applied_at = '2026-07-01'
        self.case.result_received_at = '2026-09-20'
        self.case.permission_number = '阪許可123'
        self.case.save(update_fields=['status', 'applied_at', 'result_received_at', 'permission_number'])

        response = self.client.post(f'/api/cases/{self.case.id}/progress-info/', {
            'result_received_at': '2026-09-18',
            'permission_number': '阪許可456',
            'note': '許可通知の記載を修正',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.STATUS_APPROVED)
        self.assertEqual(str(self.case.result_received_at), '2026-09-18')
        self.assertEqual(self.case.permission_number, '阪許可456')
        timeline = Timeline.objects.get(case=self.case, title='案件進捗情報変更')
        self.assertIn('許可番号：阪許可123 → 阪許可456', timeline.content)

    def test_progress_info_update_rejects_invalid_date_order(self):
        self.case.applied_at = '2026-07-10'
        self.case.save(update_fields=['applied_at'])

        response = self.client.post(f'/api/cases/{self.case.id}/progress-info/', {
            'result_received_at': '2026-07-01',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.case.refresh_from_db()
        self.assertIsNone(self.case.result_received_at)

    def test_applied_status_saves_application_fields_without_test_values(self):
        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_APPLIED,
            'change_date': '2026-07-16',
            'force': True,
            'note': '必須事項未完了だが先行申請',
            'status_payload': {
                'applied_at': '2026-07-17',
                'application_authority': '大阪出入国在留管理局',
                'application_receipt_number': '阪在留第12345号',
                'expected_result_at': '2026-09-16',
            },
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.STATUS_APPLIED)
        self.assertEqual(str(self.case.applied_at), '2026-07-17')
        self.assertEqual(self.case.application_receipt_number, '阪在留第12345号')

    def test_additional_documents_and_under_review_submission_dates(self):
        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_ADDITIONAL_DOCUMENTS,
            'change_date': '2026-07-16',
            'status_payload': {
                'additional_documents_due_at': '2026-07-25',
                'additional_documents_detail': '納税証明書を追加提出',
            },
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(str(self.case.additional_documents_requested_at), '2026-07-16')

        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED,
            'change_date': '2026-07-26',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(str(self.case.additional_documents_submitted_at), '2026-07-26')

    def test_approved_rejected_and_completed_dates_are_preserved(self):
        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_APPROVED,
            'change_date': '2026-07-16',
            'status_payload': {
                'result_received_at': '2026-07-18',
                'permission_number': '阪許可123',
                'result_note': '許可通知受領',
            },
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(str(self.case.result_received_at), '2026-07-18')
        self.assertEqual(self.case.permission_number, '阪許可123')
        self.assertEqual(self.case.result_note, '許可通知受領')

        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_COMPLETED,
            'change_date': '2026-07-20',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(str(self.case.completed_at), '2026-07-20')

        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_ACCEPTED,
            'change_date': '2026-07-21',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(str(self.case.completed_at), '2026-07-20')

    def test_ready_to_apply_requires_force_with_incomplete_required_items(self):
        CaseChecklistItem.objects.create(
            case=self.case,
            name='納税証明書',
            is_required=True,
            is_completed=False,
        )

        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_READY_TO_APPLY,
            'change_date': '2026-07-16',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data['requires_force'])
        self.assertEqual(response.data['warnings'][0]['code'], 'required_items_incomplete')
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.STATUS_ACCEPTED)

    def test_force_requires_note_and_then_allows_status_change(self):
        CaseChecklistItem.objects.create(
            case=self.case,
            name='納税証明書',
            is_required=True,
            is_completed=False,
        )
        empty_note_response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_READY_TO_APPLY,
            'force': True,
            'note': '',
        }, format='json')
        self.assertEqual(empty_note_response.status_code, 400)

        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_READY_TO_APPLY,
            'force': True,
            'note': '例外対応',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.STATUS_READY_TO_APPLY)
        self.assertTrue(response.data['forced'])

    def test_completed_status_checks_unfinished_items(self):
        CaseChecklistItem.objects.create(
            case=self.case,
            name='署名確認',
            is_required=False,
            is_completed=False,
        )

        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_COMPLETED,
        }, format='json')

        self.assertEqual(response.status_code, 400)
        warning_codes = {warning['code'] for warning in response.data['warnings']}
        self.assertIn('checklist_items_incomplete', warning_codes)
        self.assertIn('result_status_not_terminal', warning_codes)

    def test_required_checklist_completion_returns_suggestion_without_auto_status_change(self):
        self.case.status = Case.STATUS_COLLECTING_DOCUMENTS
        self.case.save(update_fields=['status'])
        item = CaseChecklistItem.objects.create(
            case=self.case,
            name='納税証明書',
            is_required=True,
            is_completed=False,
        )

        response = self.client.patch(f'/api/case-checklist-items/{item.id}/', {
            'is_completed': True,
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['progress_summary']['suggested_case_status'], Case.STATUS_PREPARING_DOCUMENTS)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.STATUS_COLLECTING_DOCUMENTS)

        response = self.client.patch(f'/api/case-checklist-items/{item.id}/', {
            'is_completed': False,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.STATUS_COLLECTING_DOCUMENTS)

    def test_archive_registration_status_warns_when_business_status_not_finished(self):
        response = self.client.post(f'/api/cases/{self.case.id}/change-registration-status/', {
            'new_status': Case.REGISTRATION_STATUS_ARCHIVED,
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data['requires_force'])
        self.assertEqual(response.data['warnings'][0]['code'], 'business_status_not_finished')

    def test_force_archive_keeps_related_data(self):
        item = CaseChecklistItem.objects.create(case=self.case, name='資料', is_required=True)
        response = self.client.post(f'/api/cases/{self.case.id}/change-registration-status/', {
            'new_status': Case.REGISTRATION_STATUS_ARCHIVED,
            'force': True,
            'note': '完了前だが保管扱い',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.registration_status, Case.REGISTRATION_STATUS_ARCHIVED)
        self.assertTrue(CaseChecklistItem.objects.filter(id=item.id, case=self.case).exists())
        self.assertTrue(Timeline.objects.filter(case=self.case, title='登録状態変更').exists())

    def test_unauthenticated_user_cannot_change_status(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(f'/api/cases/{self.case.id}/change-status/', {
            'new_status': Case.STATUS_COLLECTING_DOCUMENTS,
        }, format='json')

        self.assertIn(response.status_code, [401, 403])

    def test_case_list_registration_status_filter(self):
        archived = Case.objects.create(
            case_type='永住許可申請',
            case_type_master=self.case_type_master,
            application_category=self.application_category,
            customer=self.customer,
            registration_status=Case.REGISTRATION_STATUS_ARCHIVED,
        )

        default_response = self.client.get('/api/cases/')
        self.assertEqual(default_response.status_code, 200)
        default_ids = {row['id'] for row in default_response.data['results']}
        self.assertIn(self.case.id, default_ids)
        self.assertIn(archived.id, default_ids)

        active_response = self.client.get('/api/cases/', {'registration_status': Case.REGISTRATION_STATUS_ACTIVE})
        self.assertEqual(active_response.status_code, 200)
        active_ids = {row['id'] for row in active_response.data['results']}
        self.assertIn(self.case.id, active_ids)
        self.assertNotIn(archived.id, active_ids)

        archived_response = self.client.get('/api/cases/', {'registration_status': Case.REGISTRATION_STATUS_ARCHIVED})
        self.assertEqual(archived_response.status_code, 200)
        archived_ids = {row['id'] for row in archived_response.data['results']}
        self.assertIn(archived.id, archived_ids)
