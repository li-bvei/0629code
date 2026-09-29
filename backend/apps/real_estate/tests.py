"""P3 不動産：権限（本人担当／全件閲覧／全件変更）、法定台帳（ロック・更正・年度締め・legal hold・出力）、
ファイルの受保護ダウンロード、会計参照、内部利益配分（専用権限・監査）。"""
import shutil
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
from apps.employees.models import Employee
from apps.real_estate.models import InternalProfitDistribution, LegalLedger, RealEstateTransaction

PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'


class RealEstateFixture:
    def setUp(self):
        self.li = make_user('re_li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], employee_name='李', superuser=True)
        self.jiao = make_user('re_jiao', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], employee_name='焦')
        self.staff_a = make_user('re_a', roles=[STAFF], employee_name='A')
        self.staff_b = make_user('re_b', roles=[STAFF], employee_name='B')
        self.emp_a = Employee.objects.get(user=self.staff_a)
        self.emp_b = Employee.objects.get(user=self.staff_b)

    def api(self, user, method, url, data=None, fmt='json'):
        self.client.force_login(user)
        kwargs = {'content_type': 'application/json'} if fmt == 'json' else {}
        return getattr(self.client, method)(url, data if data is not None else {}, **kwargs)

    def create_tx(self, user=None, **extra):
        body = {'party_name': '王 借主', 'property_name': 'サンライズ天王寺', 'room_number': '301',
                'management_company_name': '大阪管理', **extra}
        response = self.api(user or self.staff_a, 'post', '/api/real-estate/transactions/', body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()


class TransactionAccessTests(RealEstateFixture, TestCase):
    def test_minimal_create_defaults_and_missing_items(self):
        tx = self.create_tx()
        self.assertRegex(tx['transaction_number'], r'^RE-\d{6}-0001$')
        self.assertEqual(tx['transaction_type'], 'rental')
        self.assertEqual(tx['stage'], 'inquiry')
        self.assertEqual(tx['responsible_employee'], self.emp_a.id)
        self.assertIn('取引日', tx['missing_items'])
        self.assertIn('支払状態', tx['missing_items'])
        self.assertNotIn('管理会社', tx['missing_items'])
        self.assertTrue(AuditLog.objects.filter(module='real_estate', action='transaction_created').exists())

    def test_scope_own_view_all_change_all(self):
        tx = self.create_tx()
        url = f"/api/real-estate/transactions/{tx['id']}/"
        # 他の担当者を指定して作れない
        denied = self.api(self.staff_a, 'post', '/api/real-estate/transactions/',
                          {'party_name': 'x', 'property_name': 'y', 'responsible_employee': self.emp_b.id})
        self.assertEqual(denied.status_code, 403)
        # 担当外の一般職員には見えない
        self.assertEqual(self.api(self.staff_b, 'get', url).status_code, 404)
        self.assertEqual(self.api(self.staff_b, 'get', '/api/real-estate/transactions/').json()['count'], 0)
        # 業務管理者：全件閲覧できるが、本人担当以外は変更できない
        self.assertEqual(self.api(self.jiao, 'get', url).status_code, 200)
        self.assertEqual(self.api(self.jiao, 'patch', url, {'stage': 'viewing'}).status_code, 403)
        # 李：全件変更・担当者の付け替えができる
        response = self.api(self.li, 'patch', url, {'stage': 'contract', 'responsible_employee': self.emp_b.id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.api(self.staff_b, 'get', url).status_code, 200)
        # 担当者の付け替えは一般職員にはできない
        self.assertEqual(self.api(self.staff_b, 'patch', url, {'responsible_employee': self.emp_a.id}).status_code, 403)

    def test_filters(self):
        self.create_tx(stage='contract', payment_status='paid')
        self.create_tx(property_name='別物件', management_company_name='京都管理', transaction_type='sale')
        list_url = '/api/real-estate/transactions/'
        self.client.force_login(self.staff_a)
        self.assertEqual(self.client.get(list_url, {'stage': 'contract'}).json()['count'], 1)
        self.assertEqual(self.client.get(list_url, {'payment_status': 'unset'}).json()['count'], 1)
        self.assertEqual(self.client.get(list_url, {'management_company': '京都'}).json()['count'], 1)
        self.assertEqual(self.client.get(list_url, {'transaction_type': 'sale'}).json()['count'], 1)
        self.assertEqual(self.client.get(list_url, {'responsible_employee': self.emp_b.id}).json()['count'], 0)
        self.assertEqual(self.client.get(list_url, {'missing': '1'}).json()['count'], 2)


class LegalLedgerTests(RealEstateFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.tx = self.create_tx(transaction_date='2026-09-10', rent_or_price='85000', brokerage_fee='85000',
                                 advertising_fee='42500', property_address='大阪市天王寺区勝山4-7-3')
        response = self.api(self.staff_a, 'post', f"/api/real-estate/transactions/{self.tx['id']}/ensure-ledger/")
        self.assertEqual(response.status_code, 201, response.content)
        self.ledger = response.json()
        self.url = f"/api/real-estate/ledgers/{self.ledger['id']}/"

    def test_ledger_defaults_from_transaction(self):
        self.assertEqual(self.ledger['rent_or_price'], '85000')
        self.assertEqual(self.ledger['remuneration'], '85000')
        self.assertEqual(self.ledger['property_location'], '大阪市天王寺区勝山4-7-3')
        self.assertEqual(self.ledger['retention_years'], 5)
        # 3 月決算：2026-09-10 は 2027 年度、保存期限は年度末から 5 年
        self.assertEqual(self.ledger['fiscal_year'], 2027)
        self.assertEqual(self.ledger['retention_until'], '2032-03-31')
        again = self.api(self.staff_a, 'post', f"/api/real-estate/transactions/{self.tx['id']}/ensure-ledger/")
        self.assertEqual(again.status_code, 200)

    def test_lock_and_correction_flow(self):
        edit = self.api(self.staff_a, 'patch', self.url, {'special_terms': '更新料なし', 'transaction_form': 'brokerage'})
        self.assertEqual(edit.status_code, 200, edit.content)
        # 一般職員はロックできない（拒否も監査に残る）
        self.assertEqual(self.api(self.staff_a, 'post', self.url + 'lock/').status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action='ledger_manage_denied').exists())
        locked = self.api(self.li, 'post', self.url + 'lock/')
        self.assertEqual(locked.status_code, 200, locked.content)
        self.assertTrue(locked.json()['is_locked'])
        self.assertEqual(locked.json()['locked_snapshot']['special_terms'], '更新料なし')
        # ロック後は直接変更できない（当事者の追加も不可）
        self.assertEqual(self.api(self.staff_a, 'patch', self.url, {'rent_or_price': '90000'}).status_code, 400)
        party = self.api(self.staff_a, 'post', '/api/real-estate/parties/',
                         {'transaction': self.tx['id'], 'role': 'lessor', 'name': '貸主'})
        self.assertEqual(party.status_code, 400)
        # 更正：理由が必須、版が上がり、履歴と監査が残る
        self.assertEqual(self.api(self.li, 'post', self.url + 'correct/', {'changes': {'rent_or_price': '90000'}, 'reason': ''}).status_code, 400)
        corrected = self.api(self.li, 'post', self.url + 'correct/',
                             {'changes': {'rent_or_price': '90000'}, 'reason': '契約書の賃料を再確認'})
        self.assertEqual(corrected.status_code, 200, corrected.content)
        self.assertEqual(corrected.json()['version'], 2)
        history = self.api(self.li, 'get', self.url + 'corrections/').json()
        self.assertEqual(history[0]['changes'], {'rent_or_price': ['85000', '90000']})
        self.assertTrue(AuditLog.objects.filter(action='ledger_corrected', reason='契約書の賃料を再確認').exists())
        self.assertEqual(self.api(self.li, 'post', self.url + 'correct/',
                                  {'changes': {'fiscal_year': 2020}, 'reason': 'x'}).status_code, 400)

    def test_close_year_hold_export_and_no_delete(self):
        closed = self.api(self.li, 'post', '/api/real-estate/ledgers/close-year/', {'fiscal_year': 2027})
        self.assertEqual(closed.json(), {'fiscal_year': 2027, 'ledgers': 1, 'newly_locked': 1})
        ledger = LegalLedger.objects.get(pk=self.ledger['id'])
        self.assertTrue(ledger.is_locked)
        self.assertIsNotNone(ledger.fiscal_year_closed_at)
        self.assertEqual(self.api(self.li, 'post', self.url + 'legal-hold/', {'hold': True, 'reason': ''}).status_code, 400)
        held = self.api(self.li, 'post', self.url + 'legal-hold/', {'hold': True, 'reason': '係争のため'})
        self.assertTrue(held.json()['legal_hold'])
        self.client.force_login(self.li)
        export = self.client.get('/api/real-estate/ledgers/export/', {'fiscal_year': 2027})
        self.assertEqual(export.status_code, 200)
        self.assertIn('サンライズ天王寺', export.content.decode('utf-8'))
        self.assertTrue(AuditLog.objects.filter(action='ledger_exported').exists())
        self.client.force_login(self.staff_a)
        self.assertEqual(self.client.get('/api/real-estate/ledgers/export/').status_code, 403)
        # 台帳は削除 API が無く、台帳のある取引も削除できない
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertEqual(self.client.delete(f"/api/real-estate/transactions/{self.tx['id']}/").status_code, 400)

    def test_other_staff_cannot_touch_ledger(self):
        self.assertEqual(self.api(self.staff_b, 'get', self.url).status_code, 404)
        self.assertEqual(self.api(self.jiao, 'get', self.url).status_code, 200)
        self.assertEqual(self.api(self.jiao, 'patch', self.url, {'special_terms': 'x'}).status_code, 403)


class FileAndAccountingTests(RealEstateFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.tx = self.create_tx()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def upload(self, user, name='contract.pdf', content=PDF):
        self.client.force_login(user)
        return self.client.post('/api/real-estate/files/', {
            'transaction': self.tx['id'], 'kind': 'contract', 'title': '賃貸借契約書',
            'file': SimpleUploadedFile(name, content, content_type='application/pdf'),
        })

    def test_upload_and_protected_download(self):
        response = self.upload(self.staff_a)
        self.assertEqual(response.status_code, 201, response.content)
        file_id = response.json()['id']
        self.assertEqual(response.json()['file_name'], 'contract.pdf')
        download = self.client.get(f'/api/real-estate/files/{file_id}/download/')
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), PDF)
        self.assertTrue(AuditLog.objects.filter(action='file_download_started').exists())
        self.client.force_login(self.staff_b)
        self.assertEqual(self.client.get(f'/api/real-estate/files/{file_id}/download/').status_code, 404)
        self.assertEqual(self.upload(self.staff_b).status_code, 403)
        self.assertEqual(self.upload(self.staff_a, name='evil.exe', content=b'MZ\x90\x00').status_code, 400)

    def test_accounting_link_requires_accounting_permission(self):
        income = IncomeSource.objects.create(source_date=date(2026, 9, 1), amount=Decimal('85000'), source_target='仲介')
        body = {'transaction': self.tx['id'], 'income_source': income.id}
        self.assertEqual(self.api(self.staff_a, 'post', '/api/real-estate/accounting-links/', body).status_code, 403)
        created = self.api(self.li, 'post', '/api/real-estate/accounting-links/', body)
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()['income_summary']['amount'], 85000)
        rows = self.api(self.jiao, 'get', f"/api/real-estate/accounting-links/?transaction={self.tx['id']}").json()['results']
        self.assertIsNone(rows[0]['income_summary'])


class ProfitDistributionTests(RealEstateFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.tx = self.create_tx()
        self.list_url = '/api/real-estate/profit-distributions/'

    def test_only_explicit_permission_holders(self):
        body = {'transaction': self.tx['id'], 'recipient_name': 'A', 'method': 'ratio', 'base_amount': '100000',
                'ratio_percent': '30'}
        for user in (self.staff_a, self.jiao):
            self.assertEqual(self.api(user, 'get', self.list_url).status_code, 403)
            self.assertEqual(self.api(user, 'post', self.list_url, body).status_code, 403)
        created = self.api(self.li, 'post', self.list_url, body)
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()['amount'], '30000')
        # 明示的に権限を付与された職員は、自分が扱える取引の配分だけ扱える
        self.staff_a.user_permissions.add(Permission.objects.get(codename='manage_profit_distribution'))
        rows = self.api(self.staff_a, 'get', f"{self.list_url}?transaction={self.tx['id']}").json()
        self.assertEqual(rows['count'], 1)
        self.assertTrue(AuditLog.objects.filter(action='profit_distribution_viewed', user=self.staff_a).exists())
        # 監査一覧：利益配分の記録は権限者にだけ含める
        log_url = f"/api/real-estate/transactions/{self.tx['id']}/audit-log/"
        actions = {r['action'] for r in self.api(self.jiao, 'get', log_url).json()}
        self.assertNotIn('profit_distribution_created', actions)
        actions = {r['action'] for r in self.api(self.li, 'get', log_url).json()}
        self.assertIn('profit_distribution_created', actions)

    def test_fixed_settle_reopen(self):
        obj = self.api(self.li, 'post', self.list_url, {'transaction': self.tx['id'], 'recipient_name': '紹介者',
                                                        'method': 'fixed', 'fixed_amount': '15000'}).json()
        self.assertEqual(obj['amount'], '15000')
        url = f"{self.list_url}{obj['id']}/"
        self.assertEqual(self.api(self.li, 'post', self.list_url, {'transaction': self.tx['id'], 'recipient_name': 'x',
                                                                    'method': 'ratio', 'ratio_percent': '150'}).status_code, 400)
        self.assertEqual(self.api(self.li, 'post', url + 'settle/').json()['status'], 'settled')
        self.assertEqual(self.api(self.li, 'patch', url, {'fixed_amount': '1'}).status_code, 400)
        self.assertEqual(self.api(self.li, 'patch', url, {'note': '振込済み'}).status_code, 200)
        self.client.force_login(self.li)
        self.assertEqual(self.client.delete(url).status_code, 400)
        self.assertEqual(self.api(self.li, 'post', url + 'reopen/', {'reason': ''}).status_code, 400)
        self.assertEqual(self.api(self.li, 'post', url + 'reopen/', {'reason': '金額訂正'}).json()['status'], 'draft')
        self.assertEqual(InternalProfitDistribution.objects.get(pk=obj['id']).status, 'draft')
        # 利益配分は法定台帳の出力に含まれない
        self.assertFalse(RealEstateTransaction._meta.get_field('profit_distributions').concrete)
