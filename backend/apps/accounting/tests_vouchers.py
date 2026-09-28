"""P2-C11：見積書・契約書・請求書・領収書（状態は帳票ごとに独立、共通は採番・金額・PDF・監査のみ）。"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from apps.accounting.models import AccountingVoucher, Contract, Estimate
from apps.accounting.tests_links import AccountingFixture
from apps.audit.models import AuditLog
from apps.authentication.testing import make_user

LINES = [
    {'item_name': '在留資格変更 申請取次', 'quantity': 1, 'unit_price': 55000, 'tax_category': 'tax_10', 'price_type': 'tax_included'},
    {'item_name': '収入印紙', 'quantity': 1, 'unit_price': 4000, 'tax_category': 'non_taxable'},
]


def grant(user, *codenames):
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename=codename))
    return user


class VoucherFixture(AccountingFixture):
    def post(self, user, url, body=None):
        self.client.force_login(user)
        return self.client.post(url, body or {}, content_type='application/json')

    def patch(self, user, url, body):
        self.client.force_login(user)
        return self.client.patch(url, body, content_type='application/json')

    def create_estimate(self, user=None, **extra):
        body = {'issue_date': '2026-09-29', 'recipient_name': '株式会社テスト', 'title': '在留資格変更',
                'line_items': LINES, **extra}
        response = self.post(user or self.li, '/api/accounting/estimates/', body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def move(self, user, kind, pk, target, **extra):
        return self.post(user, f'/api/accounting/{kind}/{pk}/transition/', {'status': target, **extra})


class EstimateTests(VoucherFixture, TestCase):
    def test_create_numbers_and_amounts(self):
        first = self.create_estimate()
        second = self.create_estimate()
        self.assertEqual(first['estimate_number'], 'EST-20260929-0001')
        self.assertEqual(second['estimate_number'], 'EST-20260929-0002')
        self.assertEqual(first['status'], 'draft')
        self.assertEqual(first['total_amount'], '59000')
        self.assertEqual(first['tax_amount'], '5000')
        self.assertTrue(first['is_editable'])
        self.assertEqual([t['value'] for t in first['allowed_transitions']], ['submitted', 'cancelled'])
        self.assertTrue(AuditLog.objects.filter(module='voucher', action='estimate_created').exists())

    def test_submit_takes_snapshot_and_locks_content(self):
        estimate = self.create_estimate()
        url = f'/api/accounting/estimates/{estimate["id"]}/'
        response = self.move(self.li, 'estimates', estimate['id'], 'submitted', reason='提出')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['status'], 'submitted')
        self.assertFalse(body['is_editable'])
        self.assertEqual(body['issued_snapshot']['total_amount'], 59000)
        self.assertEqual(body['issued_snapshot']['number'], estimate['estimate_number'])
        log = AuditLog.objects.get(action='estimate_status_changed')
        self.assertEqual(log.changes, {'status': ['draft', 'submitted']})
        self.assertEqual(log.reason, '提出')

        changed = self.patch(self.li, url, {'line_items': [{'item_name': '値引き', 'quantity': 1, 'unit_price': 1}]})
        self.assertEqual(changed.status_code, 400)
        self.assertIn('line_items', changed.json()['locked_fields'])
        # 同じ内容の再送（画面の全項目送信）と備考だけの変更は通る
        same = self.patch(self.li, url, {'line_items': LINES, 'recipient_name': '株式会社テスト', 'note': '郵送済み'})
        self.assertEqual(same.status_code, 200, same.content)
        self.assertEqual(Estimate.objects.get(pk=estimate['id']).note, '郵送済み')
        self.client.force_login(self.li)
        self.assertEqual(self.client.delete(url).status_code, 400)

    def test_invalid_transition_and_empty_issue_rejected(self):
        estimate = self.create_estimate()
        self.assertEqual(self.move(self.li, 'estimates', estimate['id'], 'accepted').status_code, 400)
        empty = self.create_estimate(line_items=[])
        self.assertEqual(self.move(self.li, 'estimates', empty['id'], 'submitted').status_code, 400)
        # 取消は明細が無くてもできる、下書きは削除できる
        self.assertEqual(self.move(self.li, 'estimates', empty['id'], 'cancelled').status_code, 200)
        draft = self.create_estimate()
        self.client.force_login(self.li)
        self.assertEqual(self.client.delete(f'/api/accounting/estimates/{draft["id"]}/').status_code, 204)

    def test_estimate_status_is_independent_from_documents_created_from_it(self):
        estimate = self.create_estimate(case=self.case_a.id)
        contract = self.post(self.li, f'/api/accounting/estimates/{estimate["id"]}/create-contract/')
        invoice = self.post(self.li, f'/api/accounting/estimates/{estimate["id"]}/create-invoice/')
        self.assertEqual(contract.status_code, 201, contract.content)
        self.assertEqual(invoice.status_code, 201, invoice.content)
        contract, invoice = contract.json(), invoice.json()
        self.assertEqual(contract['status'], 'draft')
        self.assertEqual(contract['source_estimate_number'], estimate['estimate_number'])
        self.assertEqual(contract['total_amount'], '59000')
        self.assertEqual(contract['case'], self.case_a.id)
        self.assertEqual(invoice['invoice_status'], 'draft')
        self.assertEqual(invoice['receipt_status'], '')
        self.assertEqual(invoice['voucher_number'], 'INV-' + timezone.localdate().strftime('%Y%m%d') + '-0001')

        self.move(self.li, 'estimates', estimate['id'], 'submitted')
        self.move(self.li, 'estimates', estimate['id'], 'accepted')
        self.assertEqual(Contract.objects.get(pk=contract['id']).status, 'draft')
        self.assertEqual(AccountingVoucher.objects.get(pk=invoice['id']).invoice_status, 'draft')


class ContractTests(VoucherFixture, TestCase):
    def create_contract(self, **extra):
        body = {'issue_date': '2026-09-29', 'recipient_name': '王小明', 'recipient_honorific': '様',
                'title': '業務委託契約書', 'line_items': LINES, 'start_date': '2026-10-01', 'end_date': '2027-03-31',
                'payment_terms': '着手時に全額', 'body': '第1条（目的）\n甲は乙に申請取次業務を委託する。\n' * 40, **extra}
        response = self.post(self.li, '/api/accounting/contracts/', body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_contract_workflow_and_signed_date(self):
        contract = self.create_contract()
        self.assertEqual(contract['contract_number'], 'CON-20260929-0001')
        self.assertEqual(self.move(self.li, 'contracts', contract['id'], 'signed').status_code, 400)
        self.assertEqual(self.move(self.li, 'contracts', contract['id'], 'sent').status_code, 200)
        signed = self.move(self.li, 'contracts', contract['id'], 'signed', date='2026-10-02').json()
        self.assertEqual(signed['status'], 'signed')
        self.assertEqual(signed['signed_date'], '2026-10-02')
        self.assertEqual([t['value'] for t in signed['allowed_transitions']], ['terminated'])
        body = self.patch(self.li, f'/api/accounting/contracts/{contract["id"]}/', {'body': '書き換え'})
        self.assertEqual(body.status_code, 400)

    def test_end_before_start_rejected(self):
        response = self.post(self.li, '/api/accounting/contracts/', {
            'issue_date': '2026-09-29', 'start_date': '2026-10-01', 'end_date': '2026-09-01'})
        self.assertEqual(response.status_code, 400)

    def test_pdfs_are_generated_and_audited(self):
        contract = self.create_contract()
        estimate = self.create_estimate(note='有効期限内にご連絡ください。')
        self.client.force_login(self.li)
        for url in (f'/api/accounting/contracts/{contract["id"]}/pdf/?with_seal=1',
                    f'/api/accounting/estimates/{estimate["id"]}/pdf/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertTrue(AuditLog.objects.filter(action='contract_pdf_downloaded', extra__with_seal=True).exists())
        self.assertTrue(AuditLog.objects.filter(action='estimate_pdf_downloaded').exists())


class InvoiceReceiptTests(VoucherFixture, TestCase):
    def create_invoice(self, **extra):
        body = {'voucher_type': 'invoice', 'issue_date': '2026-09-29', 'recipient_name': '株式会社テスト',
                'line_items': LINES, 'payment_due_date': '2026-10-31', **extra}
        response = self.post(self.li, '/api/accounting/vouchers/', body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_invoice_and_receipt_have_separate_workflows(self):
        invoice = self.create_invoice()
        self.assertEqual(invoice['invoice_status'], 'draft')
        self.assertEqual(invoice['receipt_status'], '')
        self.assertEqual(self.move(self.li, 'vouchers', invoice['id'], 'voided').status_code, 400)
        self.assertEqual(self.move(self.li, 'vouchers', invoice['id'], 'issued').status_code, 200)
        paid = self.move(self.li, 'vouchers', invoice['id'], 'paid', date='2026-10-15').json()
        self.assertEqual(paid['invoice_status'], 'paid')
        self.assertEqual(paid['paid_date'], '2026-10-15')

        receipt = self.post(self.li, f'/api/accounting/vouchers/{invoice["id"]}/create-receipt/')
        self.assertEqual(receipt.status_code, 201, receipt.content)
        receipt = receipt.json()
        self.assertEqual(receipt['voucher_type'], 'receipt')
        self.assertEqual(receipt['receipt_status'], 'draft')
        self.assertEqual(receipt['invoice_status'], '')
        self.assertEqual(receipt['source_invoice_number'], invoice['voucher_number'])
        self.assertEqual(self.move(self.li, 'vouchers', receipt['id'], 'paid').status_code, 400)
        self.assertEqual(self.move(self.li, 'vouchers', receipt['id'], 'issued').status_code, 200)
        self.assertEqual(self.move(self.li, 'vouchers', receipt['id'], 'voided').status_code, 200)
        # 領収書を無効にしても請求書の状態は変わらない
        self.assertEqual(AccountingVoucher.objects.get(pk=invoice['id']).invoice_status, 'paid')
        # 領収書から領収書は作れない
        self.assertEqual(self.post(self.li, f'/api/accounting/vouchers/{receipt["id"]}/create-receipt/').status_code, 400)

    def test_legacy_rows_are_left_unset_and_still_editable(self):
        legacy = AccountingVoucher.objects.create(voucher_type='invoice', issue_date=date(2026, 7, 1),
                                                  voucher_number='INV-20260929-0007', amount=Decimal('1000'))
        self.client.force_login(self.li)
        data = self.client.get(f'/api/accounting/vouchers/{legacy.id}/').json()
        self.assertEqual(data['invoice_status'], '')
        self.assertEqual(data['status_display'], '状態未設定（旧データ）')
        self.assertTrue(data['is_editable'])
        unset = self.client.get('/api/accounting/vouchers/', {'voucher_type': 'invoice', 'status': 'unset'}).json()
        self.assertEqual([row['id'] for row in unset['results']], [legacy.id])
        # 旧来の番号の続きから採番する（重複しない）
        new = self.create_invoice()
        self.assertEqual(new['voucher_number'], 'INV-20260929-0008')
        # 旧データは一括で状態を付けない。個別に遷移できる
        self.assertEqual(self.move(self.li, 'vouchers', legacy.id, 'paid').status_code, 200)

    def test_status_filter_requires_voucher_type(self):
        self.client.force_login(self.li)
        response = self.client.get('/api/accounting/vouchers/', {'status': 'draft'})
        self.assertEqual(response.status_code, 400)


class VoucherAccessTests(VoucherFixture, TestCase):
    def test_permissions_are_separate_per_document(self):
        user = grant(make_user('voucher_only'), 'use_voucher')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/api/accounting/vouchers/').status_code, 200)
        self.assertEqual(self.client.get('/api/accounting/estimates/').status_code, 403)
        self.assertEqual(self.client.get('/api/accounting/contracts/').status_code, 403)
        self.assertEqual(self.client.get('/api/accounting/voucher-item-templates/').status_code, 200)

        estimate_user = grant(make_user('estimate_only'), 'use_estimate')
        estimate = self.create_estimate(user=self.li)
        self.client.force_login(estimate_user)
        self.assertEqual(self.client.get(f'/api/accounting/estimates/{estimate["id"]}/').status_code, 200)
        # 作成先（請求書・契約書）の権限がなければ作れない
        self.assertEqual(self.post(estimate_user, f'/api/accounting/estimates/{estimate["id"]}/create-invoice/').status_code, 403)
        self.assertEqual(self.post(estimate_user, f'/api/accounting/estimates/{estimate["id"]}/create-contract/').status_code, 403)
        self.assertEqual(self.client.get('/api/accounting/voucher-item-templates/').status_code, 200)
        self.assertEqual(self.post(estimate_user, '/api/accounting/voucher-item-templates/', {'name': 'x'}).status_code, 403)
        self.assertEqual(self.client.get('/api/accounting/vouchers/').status_code, 403)

    def test_linking_case_requires_case_change_permission(self):
        user = grant(make_user('estimate_staff', roles=['staff'], employee_name='C'), 'use_estimate')
        denied = self.post(user, '/api/accounting/estimates/', {'issue_date': '2026-09-29', 'case': self.case_a.id})
        self.assertEqual(denied.status_code, 403)
        grant(self.staff_a, 'use_estimate')
        ok = self.post(self.staff_a, '/api/accounting/estimates/', {'issue_date': '2026-09-29', 'case': self.case_a.id})
        self.assertEqual(ok.status_code, 201, ok.content)
        self.assertEqual(ok.json()['customer'], self.customer.id)

    def test_voucher_links_summary(self):
        self.create_estimate(case=self.case_a.id)
        self.client.force_login(self.li)
        data = self.client.get('/api/accounting/voucher-links/', {'case': self.case_a.id}).json()
        self.assertEqual(data['estimates']['count'], 1)
        self.assertEqual(data['estimates']['items'][0]['status_display'], '下書き')
        self.assertEqual(data['invoices']['count'], 0)
        by_customer = self.client.get('/api/accounting/voucher-links/', {'customer': self.customer.id}).json()
        self.assertEqual(by_customer['estimates']['count'], 1)

        grant(self.staff_a, 'use_estimate')
        self.client.force_login(self.staff_a)
        data = self.client.get('/api/accounting/voucher-links/', {'case': self.case_a.id}).json()
        self.assertEqual(data['estimates']['count'], 1)
        self.assertFalse(data['invoices']['visible'])
        # 担当外の案件は見られない
        self.assertEqual(self.client.get('/api/accounting/voucher-links/', {'case': self.case_b.id}).status_code, 403)
        # 帳票の権限が一つもなければ使えない
        self.client.force_login(self.staff_b)
        self.assertEqual(self.client.get('/api/accounting/voucher-links/', {'case': self.case_b.id}).status_code, 403)
