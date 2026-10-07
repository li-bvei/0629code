"""不動産の協同台帳、明示権限、操作履歴、法定台帳と保護ファイルの回帰テスト。"""
import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.accounting.models import IncomeSource
from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.real_estate.models import InternalProfitDistribution, RealEstateTransaction
from apps.common.test_isolation import safe_rmtree

PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


class RealEstateFixture:
    def setUp(self):
        # 李も is_superuser に依存せず、3 つの明示ロールだけで全操作する。
        self.li = make_user('re_li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], employee_name='李', superuser=False)
        self.manager = make_user('re_manager', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], employee_name='管理者')
        self.staff_a = make_user('re_a', roles=[STAFF], employee_name='職員A')
        self.staff_b = make_user('re_b', roles=[STAFF], employee_name='職員B')

    def api(self, user, method, url, data=None, fmt='json'):
        self.client.force_login(user)
        kwargs = {'content_type': 'application/json'} if fmt == 'json' else {}
        return getattr(self.client, method)(url, data if data is not None else {}, **kwargs)

    def create_tx(self, user=None, **extra):
        body = {'party_name': '取引先', 'property_name': '対象物件', 'room_number': '1',
                'management_company_name': '管理会社', 'responsible_name': '仮担当', **extra}
        response = self.api(user or self.staff_a, 'post', '/api/real-estate/transactions/', body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()


class CollaborativeLedgerAccessTests(RealEstateFixture, TestCase):
    def test_free_text_assignee_and_two_users_edit_same_record(self):
        tx = self.create_tx(responsible_name='焦')
        self.assertEqual(tx['responsible_name'], '焦')
        self.assertNotIn('responsible_employee', tx)
        url = f"/api/real-estate/transactions/{tx['id']}/"
        self.assertEqual(self.api(self.staff_b, 'get', url).status_code, 200)
        changed = self.api(self.staff_b, 'patch', url, {'responsible_name': '田中（暫定）', 'stage': 'viewing'})
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(changed.json()['responsible_name'], '田中（暫定）')
        self.assertEqual(self.api(self.manager, 'patch', url, {'property_name': '更新物件'}).status_code, 200)
        history = self.api(self.staff_a, 'get', url + 'audit-log/').json()
        edited = next(row for row in history if row['actor'] == '職員B' and row['changes'])
        self.assertIn('職員Bが不動産記録の2項目を変更しました', edited['message'])
        self.assertIn({'field': '担当者', 'before': '焦', 'after': '田中（暫定）'}, edited['changes'])
        self.assertTrue(all('technical_details' not in row for row in history))

    def test_module_entry_stays_closed_and_superuser_is_not_a_bypass(self):
        outsider = make_user('re_outsider', superuser=True)
        self.assertEqual(self.api(outsider, 'get', '/api/real-estate/transactions/').status_code, 403)
        self.assertEqual(self.api(outsider, 'post', '/api/real-estate/transactions/',
                                  {'party_name': 'x', 'property_name': 'y'}).status_code, 403)

    def test_li_can_create_edit_archive_restore_export_without_superuser(self):
        self.assertFalse(self.li.is_superuser)
        tx = self.create_tx(user=self.li, responsible_name='任意文字')
        url = f"/api/real-estate/transactions/{tx['id']}/"
        self.assertEqual(self.api(self.li, 'patch', url, {'responsible_name': '別名'}).status_code, 200)
        archived = self.api(self.li, 'post', url + 'archive/', {'reason': '確認済み'})
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertTrue(archived.json()['is_archived'])
        self.assertEqual(self.api(self.li, 'patch', url, {'stage': 'contract'}).status_code, 400)
        restored = self.api(self.li, 'post', url + 'restore/')
        self.assertEqual(restored.status_code, 200, restored.content)
        self.assertFalse(restored.json()['is_archived'])
        self.client.force_login(self.li)
        self.assertEqual(self.client.get('/api/real-estate/transactions/export/').status_code, 200)
        history = self.client.get(url + 'audit-log/').json()
        self.assertTrue(any(row.get('technical_details', {}).get('action') == 'transaction_archived' for row in history))
        self.assertTrue(any(row['actor'] == '李' for row in history))

    def test_ordinary_user_cannot_archive_but_can_filter_all_records_by_text(self):
        self.create_tx(responsible_name='自由名A', stage='contract')
        other = self.create_tx(user=self.staff_b, responsible_name='自由名B', property_name='別物件')
        self.client.force_login(self.staff_a)
        body = self.client.get('/api/real-estate/transactions/', {'responsible_name': '自由名B'}).json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['results'][0]['id'], other['id'])
        self.assertEqual(self.client.post(f"/api/real-estate/transactions/{other['id']}/archive/",
                                          {'reason': 'x'}, content_type='application/json').status_code, 403)

    def test_removed_amount_fields_are_not_in_api_or_model(self):
        tx = self.create_tx()
        names = {field.name for field in RealEstateTransaction._meta.get_fields()}
        self.assertFalse(any(name.startswith('source_billed_') for name in names))
        self.assertFalse(any(name.startswith('source_sunrise_') for name in names))
        self.assertFalse(any(name.startswith(('source_billed_', 'source_sunrise_')) for name in tx))


class LegalLedgerTests(RealEstateFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.tx = self.create_tx(transaction_date='2026-09-10', rent_or_price='85000', brokerage_fee='85000',
                                 advertising_fee='42500', property_address='所在地')
        response = self.api(self.li, 'post', f"/api/real-estate/transactions/{self.tx['id']}/ensure-ledger/")
        self.assertEqual(response.status_code, 201, response.content)
        self.ledger = response.json()
        self.url = f"/api/real-estate/ledgers/{self.ledger['id']}/"

    def test_li_ledger_manage_correction_close_and_export(self):
        edit = self.api(self.li, 'patch', self.url, {'special_terms': '更新内容'})
        self.assertEqual(edit.status_code, 200, edit.content)
        locked = self.api(self.li, 'post', self.url + 'lock/')
        self.assertEqual(locked.status_code, 200, locked.content)
        corrected = self.api(self.li, 'post', self.url + 'correct/',
                             {'changes': {'rent_or_price': '90000'}, 'reason': '根拠資料を確認'})
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertEqual(corrected.json()['version'], 2)
        closed = self.api(self.li, 'post', '/api/real-estate/ledgers/close-year/', {'fiscal_year': 2027})
        self.assertEqual(closed.status_code, 200, closed.content)
        self.client.force_login(self.li)
        self.assertEqual(self.client.get('/api/real-estate/ledgers/export/', {'fiscal_year': 2027}).status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='ledger_corrected', user=self.li).exists())

    def test_ordinary_user_can_view_but_not_use_legal_ledger_admin_actions(self):
        self.assertEqual(self.api(self.staff_b, 'get', self.url).status_code, 200)
        self.assertEqual(self.api(self.staff_b, 'patch', self.url, {'special_terms': 'x'}).status_code, 403)
        self.assertEqual(self.api(self.staff_b, 'post', self.url + 'lock/').status_code, 403)
        self.client.force_login(self.staff_b)
        self.assertEqual(self.client.get('/api/real-estate/ledgers/export/').status_code, 403)


class FileAndAccountingTests(RealEstateFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.tx = self.create_tx()

    def tearDown(self):
        self.override.disable()
        safe_rmtree(self.media)

    def upload(self, user, name='contract.pdf', content=PDF):
        self.client.force_login(user)
        return self.client.post('/api/real-estate/files/', {
            'transaction': self.tx['id'], 'kind': 'contract', 'title': '契約書',
            'file': SimpleUploadedFile(name, content, content_type='application/pdf'),
        })

    def test_any_authorized_user_can_upload_and_download_same_record(self):
        response = self.upload(self.staff_b)
        self.assertEqual(response.status_code, 201, response.content)
        file_id = response.json()['id']
        self.client.force_login(self.staff_a)
        download = self.client.get(f'/api/real-estate/files/{file_id}/download/')
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), PDF)

    def test_accounting_link_remains_guarded_by_accounting_permission(self):
        income = IncomeSource.objects.create(source_date=date(2026, 9, 1), amount=Decimal('85000'), source_target='仲介')
        body = {'transaction': self.tx['id'], 'income_source': income.id}
        self.assertEqual(self.api(self.staff_a, 'post', '/api/real-estate/accounting-links/', body).status_code, 403)
        self.assertEqual(self.api(self.li, 'post', '/api/real-estate/accounting-links/', body).status_code, 201)


class ProfitDistributionTests(RealEstateFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.tx = self.create_tx()
        self.list_url = '/api/real-estate/profit-distributions/'

    def test_profit_distribution_requires_explicit_permission_and_li_has_it(self):
        body = {'transaction': self.tx['id'], 'recipient_name': '配分先', 'method': 'ratio', 'base_amount': '100000',
                'ratio_percent': '30'}
        self.assertEqual(self.api(self.staff_a, 'post', self.list_url, body).status_code, 403)
        created = self.api(self.li, 'post', self.list_url, body)
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()['amount'], '30000')
        self.staff_a.user_permissions.add(Permission.objects.get(codename='manage_profit_distribution'))
        self.assertEqual(self.api(self.staff_a, 'get', f"{self.list_url}?transaction={self.tx['id']}").status_code, 200)

    def test_li_settle_and_reopen(self):
        obj = self.api(self.li, 'post', self.list_url, {'transaction': self.tx['id'], 'recipient_name': '配分先',
                                                        'method': 'fixed', 'fixed_amount': '15000'}).json()
        url = f"{self.list_url}{obj['id']}/"
        self.assertEqual(self.api(self.li, 'post', url + 'settle/').json()['status'], 'settled')
        self.assertEqual(self.api(self.li, 'post', url + 'reopen/', {'reason': '金額再確認'}).json()['status'], 'draft')
        self.assertEqual(InternalProfitDistribution.objects.get(pk=obj['id']).status, 'draft')
