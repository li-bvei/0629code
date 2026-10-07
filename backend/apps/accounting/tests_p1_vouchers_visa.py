"""2026-10 P1：請求書・領収書の自由な状態切替と状態履歴、返签 visa 表の単一主流程と確実な PDF 生成。"""
import tempfile
from pathlib import Path
from unittest import mock

import fitz
from django.test import TestCase, override_settings

from apps.accounting import visa_return_pdf
from apps.accounting.models import (
    AccountingVoucher,
    VisaGuarantorTemplate,
    VisaReturnApplication,
    VisaReturnPdfGeneration,
    VoucherStatusHistory,
)
from apps.audit.models import AuditLog
from apps.authentication.testing import make_user

from .tests_vouchers import LINES, VoucherFixture
from apps.common.test_isolation import safe_rmtree

VOUCHERS = '/api/accounting/vouchers/'


class VoucherFreeStatusTests(VoucherFixture, TestCase):
    def create_invoice(self, **extra):
        body = {'voucher_type': 'invoice', 'issue_date': '2026-10-03', 'recipient_name': '株式会社テスト',
                'title': '在留資格変更', 'line_items': LINES, **extra}
        response = self.post(self.li, VOUCHERS, body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def move(self, user, pk, target, **extra):
        return self.post(user, f'{VOUCHERS}{pk}/transition/', {'status': target, **extra})

    def history(self, pk, user=None):
        self.client.force_login(user or self.li)
        return self.client.get(f'{VOUCHERS}{pk}/status-history/')

    def set_draft_status(self, pk):
        AccountingVoucher.objects.filter(pk=pk).update(invoice_status='draft')

    def test_any_valid_state_can_switch_to_any_other_including_back_to_draft(self):
        invoice = self.create_invoice()
        self.assertEqual(invoice['invoice_status'], 'draft')
        expected = {'draft', 'issued', 'sent', 'paid', 'cancelled'}
        self.assertEqual({t['value'] for t in invoice['allowed_transitions']}, expected - {'draft'})
        path = ['issued', 'cancelled', 'draft', 'paid', 'sent', 'issued', 'draft']
        for target in path:
            response = self.move(self.li, invoice['id'], target)
            self.assertEqual(response.status_code, 200, (target, response.content))
            body = response.json()
            self.assertEqual(body['invoice_status'], target)
            self.assertEqual({t['value'] for t in body['allowed_transitions']}, expected - {target})
        self.assertEqual(VoucherStatusHistory.objects.filter(voucher_id=invoice['id']).count(), len(path))

    def test_legacy_unset_status_can_move_to_any_state_but_not_back_to_unset(self):
        invoice = self.create_invoice()
        AccountingVoucher.objects.filter(pk=invoice['id']).update(invoice_status='')  # P2-C11 以前の旧データ
        self.client.force_login(self.li)
        legacy = self.client.get(f"{VOUCHERS}{invoice['id']}/").json()
        self.assertEqual(legacy['status_display'], '状態未設定（旧データ）')
        self.assertTrue(legacy['is_editable'])
        self.assertEqual({t['value'] for t in legacy['allowed_transitions']}, {'draft', 'issued', 'sent', 'paid', 'cancelled'})
        self.assertEqual(self.move(self.li, invoice['id'], 'sent').status_code, 200)
        self.assertEqual(self.move(self.li, invoice['id'], '').status_code, 400)
        row = VoucherStatusHistory.objects.get(voucher_id=invoice['id'])
        self.assertEqual((row.from_status, row.to_status), ('', 'sent'))

    def test_reissue_after_back_to_draft_keeps_previous_issued_content_traceable(self):
        invoice = self.create_invoice()
        url = f"{VOUCHERS}{invoice['id']}/"
        self.assertEqual(self.move(self.li, invoice['id'], 'issued', reason='初回発行').status_code, 200)
        locked = self.patch(self.li, url, {'line_items': [{'item_name': '値引き後', 'quantity': 1, 'unit_price': 30000}]})
        self.assertEqual(locked.status_code, 400)
        self.assertIn('下書き', locked.json()['detail'][0])  # 発行状態のまま黙って書き換えない
        self.assertEqual(self.move(self.li, invoice['id'], 'draft', reason='金額訂正').status_code, 200)
        edited = self.patch(self.li, url, {'line_items': [{'item_name': '値引き後', 'quantity': 1, 'unit_price': 30000}]})
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(edited.json()['total_amount'], '30000')
        reissued = self.move(self.li, invoice['id'], 'issued', reason='再発行').json()
        self.assertEqual(reissued['issued_snapshot']['total_amount'], 30000)

        rows = self.history(invoice['id']).json()
        self.assertEqual([(r['from_status'], r['to_status'], r['version']) for r in rows],
                         [('draft', 'issued', 2), ('issued', 'draft', 0), ('draft', 'issued', 1)])
        first_issue = rows[-1]
        self.assertEqual(first_issue['snapshot']['total_amount'], 59000)  # 最初の発行内容が残る
        self.assertEqual(first_issue['snapshot']['line_items'][0]['item_name'], LINES[0]['item_name'])
        self.assertEqual(rows[0]['snapshot']['total_amount'], 30000)
        for row in rows:
            self.assertEqual(row['changed_by_name'], '李')
            self.assertTrue(row['changed_at'])
            self.assertEqual(row['document_kind'], 'invoice')
            self.assertEqual(row['voucher_number'], invoice['voucher_number'])
        self.assertEqual(rows[1]['reason'], '金額訂正')
        self.assertEqual(rows[1]['from_status_display'], '発行済み')
        self.assertEqual(AuditLog.objects.filter(action='invoice_status_changed').count(), 3)

    def test_paid_date_is_recorded_and_receipt_status_is_independent(self):
        invoice = self.create_invoice()
        self.move(self.li, invoice['id'], 'issued')
        paid = self.move(self.li, invoice['id'], 'paid', date='2026-10-10').json()
        self.assertEqual(paid['paid_date'], '2026-10-10')
        receipt = self.post(self.li, f"{VOUCHERS}{invoice['id']}/create-receipt/").json()
        self.assertEqual((receipt['receipt_status'], receipt['invoice_status']), ('draft', ''))
        self.assertEqual({t['value'] for t in receipt['allowed_transitions']}, {'issued', 'voided'})
        self.assertEqual(self.move(self.li, receipt['id'], 'voided').status_code, 200)
        self.assertEqual(self.move(self.li, receipt['id'], 'draft').status_code, 200)  # 無効からも下書きへ戻せる
        self.assertEqual(AccountingVoucher.objects.get(pk=invoice['id']).invoice_status, 'paid')
        self.assertEqual(self.move(self.li, invoice['id'], 'cancelled').status_code, 200)
        self.assertEqual(AccountingVoucher.objects.get(pk=receipt['id']).receipt_status, 'draft')
        kinds = set(VoucherStatusHistory.objects.filter(voucher_id=receipt['id']).values_list('document_kind', flat=True))
        self.assertEqual(kinds, {'receipt'})

    def test_invalid_requests_do_not_change_state_or_history(self):
        invoice = self.create_invoice()
        self.assertEqual(self.move(self.li, invoice['id'], 'unknown').status_code, 400)
        self.assertEqual(self.move(self.li, invoice['id'], 'issued').status_code, 200)
        self.assertEqual(self.move(self.li, invoice['id'], 'issued').status_code, 400)  # 同じ状態
        # 旧データの「状態未設定」へは戻せない（選択肢に無い）
        self.assertEqual(self.move(self.li, invoice['id'], '').status_code, 400)
        empty = self.create_invoice(line_items=[])
        self.assertEqual(self.move(self.li, empty['id'], 'issued').status_code, 400)  # 明細なしは発行不可
        self.assertEqual(self.move(self.li, empty['id'], 'cancelled').status_code, 200)
        self.assertEqual(VoucherStatusHistory.objects.filter(voucher_id=invoice['id']).count(), 1)

    def test_stale_screen_gets_conflict_and_nothing_is_written(self):
        invoice = self.create_invoice()
        self.move(self.li, invoice['id'], 'issued')
        stale = self.move(self.li, invoice['id'], 'paid', expected_status='draft')
        self.assertEqual(stale.status_code, 409, stale.content)
        self.assertEqual(AccountingVoucher.objects.get(pk=invoice['id']).invoice_status, 'issued')
        self.assertEqual(VoucherStatusHistory.objects.filter(voucher_id=invoice['id']).count(), 1)
        ok = self.move(self.li, invoice['id'], 'paid', expected_status='issued')
        self.assertEqual(ok.status_code, 200, ok.content)

    def test_content_saved_from_a_draft_screen_is_rejected_if_issued_meanwhile(self):
        invoice = self.create_invoice()
        self.set_draft_status(invoice['id'])
        from apps.accounting.voucher_views import AccountingVoucherViewSet

        original = AccountingVoucherViewSet.get_object

        def issue_meanwhile(view):
            obj = original(view)
            AccountingVoucher.objects.filter(pk=obj.pk).update(invoice_status='issued')  # 別の操作が先に発行した
            return obj

        with mock.patch.object(AccountingVoucherViewSet, 'get_object', issue_meanwhile):
            response = self.patch(self.li, f"{VOUCHERS}{invoice['id']}/",
                                  {'line_items': [{'item_name': '書き換え', 'quantity': 1, 'unit_price': 1}]})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(AccountingVoucher.objects.get(pk=invoice['id']).total_amount, 59000)

    def test_line_error_points_to_the_row(self):
        lines = [LINES[0], {'item_name': '二行目', 'quantity': 'abc', 'unit_price': 100}]
        response = self.post(self.li, VOUCHERS, {'voucher_type': 'invoice', 'issue_date': '2026-10-03', 'line_items': lines})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['line_item_row'], ['2'])
        self.assertIn('2 行目', response.json()['line_items'][0])

    def test_unit_and_line_note_are_kept(self):
        lines = [{**LINES[0], 'unit': '件', 'note': '着手金'}]
        invoice = self.create_invoice(line_items=lines)
        self.assertEqual((invoice['line_items'][0]['unit'], invoice['line_items'][0]['note']), ('件', '着手金'))

    def pdf_text(self, pk):
        self.client.force_login(self.li)
        response = self.client.get(f'{VOUCHERS}{pk}/pdf/')
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content) if response.streaming else response.content
        doc = fitz.open(stream=content, filetype='pdf')
        text = ''.join(page.get_text() for page in doc)
        doc.close()
        return text

    def test_invoice_pdf_prints_unit_always_and_line_note_only_when_entered(self):
        lines = [{**LINES[0], 'quantity': 2, 'unit': '件', 'note': '着手金（QA）'},
                 {'item_name': '収入印紙', 'quantity': 3, 'unit_price': 200, 'tax_category': 'non_taxable', 'unit': '枚'}]
        invoice = self.create_invoice(line_items=lines)
        text = self.pdf_text(invoice['id'])
        self.assertIn('2件', text)
        self.assertIn('3枚', text)
        self.assertIn('着手金（QA）', text)  # 入力した備考だけが印字される（空の行は何も出ない）

    def test_delete_only_in_draft_and_history_survives_deletion(self):
        invoice = self.create_invoice()
        self.move(self.li, invoice['id'], 'issued')
        self.client.force_login(self.li)
        self.assertEqual(self.client.delete(f"{VOUCHERS}{invoice['id']}/").status_code, 400)
        self.move(self.li, invoice['id'], 'draft')
        self.assertEqual(self.client.delete(f"{VOUCHERS}{invoice['id']}/").status_code, 204)
        rows = VoucherStatusHistory.objects.filter(voucher_number=invoice['voucher_number'])
        self.assertEqual(rows.count(), 2)
        self.assertTrue(all(row.voucher_id is None for row in rows))

    def test_permissions_for_transition_and_history(self):
        invoice = self.create_invoice()
        su = make_user('p1_su', superuser=True)
        for user in (self.staff_a, self.jiao, su):
            self.assertEqual(self.move(user, invoice['id'], 'issued').status_code, 403, user.username)
            self.assertEqual(self.history(invoice['id'], user).status_code, 403, user.username)
        self.assertEqual(AccountingVoucher.objects.get(pk=invoice['id']).invoice_status, 'draft')
        self.assertFalse(VoucherStatusHistory.objects.exists())


PNG_NOT_PDF = b'not a pdf at all'


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class VisaMainFlowTests(VoucherFixture, TestCase):
    URL = '/api/accounting/visa-return-applications/'

    def setUp(self):
        super().setUp()
        self.template = VisaGuarantorTemplate.objects.create(
            name='公文テンプレート', guarantor_name='公文 慎吾', guarantor_name_en='KUMON SHINGO',
            guarantor_phone='06-1111-2222', guarantor_address='大阪府大阪市天王寺区1-1',
            guarantor_address_en='1-1 Tennoji Osaka', guarantor_birth_date='1980-01-02', guarantor_nationality='日本',
            guarantor_visa_status='日本人', guarantor_occupation='会社役員', guarantor_relationship='雇用主',
        )
        self.applicant = {
            'applicant_name': 'WANG XIAOMING', 'birth_date': '1995-05-05', 'nationality': '中国',
            'passport_number': 'E12345678', 'passport_expiry_date': '2030-01-01', 'phone': '090-0000-0000',
            'form_data': {'pinyin_name1': 'WANG', 'pinyin_name2': 'XIAOMING'},
        }

    def tearDown(self):
        from django.conf import settings

        safe_rmtree(settings.MEDIA_ROOT)

    def create(self, **extra):
        response = self.post(self.li, self.URL, {**self.applicant, **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def generate(self, pk, user=None):
        return self.post(user or self.li, f'{self.URL}{pk}/generate-pdf/')

    def get(self, url, user=None):
        self.client.force_login(user or self.li)
        return self.client.get(url)

    def pdf_text(self, content):
        doc = fitz.open(stream=content, filetype='pdf')
        text = ''.join(page.get_text() for page in doc)
        doc.close()
        return text

    def test_selected_guarantor_template_is_snapshotted_by_server_and_used_in_pdf(self):
        app = self.create(guarantor_template=self.template.id,
                          guarantor_snapshot={'guarantor_name': '画面から送った別人'})
        snapshot = app['guarantor_snapshot']
        self.assertEqual((snapshot['guarantor_name'], snapshot['template_name'], snapshot['guarantor_template_id']),
                         ('公文 慎吾', '公文テンプレート', str(self.template.id)))
        self.assertTrue(snapshot['template_version'])
        check = self.get(f"{self.URL}{app['id']}/check/").json()
        self.assertTrue(check['ready'], check)
        sources = {row['key']: (row['value'], row['source']) for row in check['fields']}
        self.assertEqual(sources['guarantor_name_jp'], ('公文 慎吾', 'template'))
        self.assertEqual(sources['guarantor_address_jp'][1], 'template')
        self.assertEqual(check['guarantor_template']['name'], '公文テンプレート')

        response = self.generate(app['id'])
        self.assertEqual(response.status_code, 201, response.content)
        generation = response.json()
        self.assertEqual((generation['status'], generation['method']), ('success', 'form'))
        self.assertEqual(len(generation['template_version']), 16)
        self.assertEqual(generation['guarantor_template'], self.template.id)
        self.assertEqual(generation['guarantor_template_version'], snapshot['template_version'][:40])
        self.assertTrue(generation['download_url'])
        download = self.get('/api' + generation['download_url'])
        self.assertEqual(download.status_code, 200)
        content = b''.join(download.streaming_content)
        self.assertTrue(content.startswith(b'%PDF'))
        text = self.pdf_text(content)
        self.assertIn('KUMON SHINGO', text)  # テンプレートの担保人が PDF に入っている
        self.assertIn('WANG', text)  # 様式の氏名欄（英文姓）
        self.assertTrue(AuditLog.objects.filter(action='visa_pdf_generated').exists())

    def test_client_cannot_write_guarantor_snapshot_by_any_route(self):
        forged = {'guarantor_template_id': str(self.template.id), 'template_name': '偽', 'template_version': 'x',
                  'guarantor_name': '偽の担保人', 'guarantor_name_en': 'FAKE'}
        app = self.create(guarantor_template=self.template.id)
        server = app['guarantor_snapshot']
        url = f"{self.URL}{app['id']}/"
        # テンプレートを送らずにスナップショットだけ書き換える
        self.assertEqual(self.patch(self.li, url, {'guarantor_snapshot': forged}).status_code, 200)
        self.assertEqual(VisaReturnApplication.objects.get(pk=app['id']).guarantor_snapshot, server)
        # 同じテンプレートを送りつつ偽のスナップショットを送る
        self.assertEqual(self.patch(self.li, url, {'guarantor_template': self.template.id, 'guarantor_snapshot': forged}).status_code, 200)
        self.assertEqual(VisaReturnApplication.objects.get(pk=app['id']).guarantor_snapshot, server)
        # 保存済みの快照が別テンプレートのもの（不整合な旧データ）なら作り直す
        VisaReturnApplication.objects.filter(pk=app['id']).update(guarantor_snapshot=forged | {'guarantor_template_id': '999'})
        self.patch(self.li, url, {'note': 'x'})
        self.assertEqual(VisaReturnApplication.objects.get(pk=app['id']).guarantor_snapshot['guarantor_name'], '公文 慎吾')
        # テンプレートを外すと、偽の印を付けたスナップショットは残らず空になる
        self.assertEqual(self.patch(self.li, url, {'guarantor_template': None, 'guarantor_snapshot': forged}).status_code, 200)
        self.assertEqual(VisaReturnApplication.objects.get(pk=app['id']).guarantor_snapshot, {})
        # テンプレート無しで新規作成しても、送ったスナップショットは使われない（出所が「テンプレート」にならない）
        manual = self.create(guarantor_template=None, guarantor_snapshot=forged, guarantor_name='手入力 担保人',
                             guarantor_phone='06-0000-0000', guarantor_address='大阪')
        self.assertEqual(manual['guarantor_snapshot'], {})
        check = self.get(f"{self.URL}{manual['id']}/check/").json()
        sources = {row['key']: (row['value'], row['source']) for row in check['fields']}
        self.assertEqual(sources['guarantor_name_jp'], ('手入力 担保人', 'manual'))
        self.assertEqual(sources['guarantor_name_en'], ('', ''))
        self.assertEqual(check['guarantor_template']['name'], '')

    def test_choice_field_that_cannot_be_selected_is_an_error_not_success(self):
        doc = fitz.open(visa_return_pdf.VISA_FORM_TEMPLATE_PATH)
        field = 'topmostSubform[0].Page1[0].#area[5].#area[6].#area[7].RB1[0]'
        self.assertTrue(visa_return_pdf.set_pdf_radio_group_value(doc, field, '0'))
        self.assertFalse(visa_return_pdf.set_pdf_radio_group_value(doc, field, '9'))  # 該当する選択肢が無い
        doc.close()
        app = self.create(guarantor_template=self.template.id, gender='male', marital_status='married')
        self.assertEqual(self.generate(app['id']).status_code, 201)
        with mock.patch.object(visa_return_pdf, 'set_pdf_radio_group_value', return_value=False):
            response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'field_write_failed'))
        self.assertIn('性別（male）', response.json()['fields'])
        VisaReturnApplication.objects.filter(pk=app['id']).update(form_data={'pinyin_name1': 'WANG', 'gender': 'unknown'})
        response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'field_write_failed'))
        self.assertIn('性別（unknown）', response.json()['fields'])

    def test_remaining_form_fields_after_flattening_is_flatten_failed(self):
        app = self.create(guarantor_template=self.template.id)
        with mock.patch.object(fitz.Page, 'delete_widget', side_effect=RuntimeError('locked')), \
                self.assertLogs('apps.accounting.visa_return_pdf', 'WARNING'):
            response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'flatten_failed'))

    def test_unexpected_exception_is_recorded_as_generation_failed(self):
        app = self.create(guarantor_template=self.template.id)
        with mock.patch.object(visa_return_pdf, 'fill_form_pdf', side_effect=KeyError('surprise')), \
                self.assertLogs('apps.accounting.visa_return_pdf', 'ERROR'):  # 詳細はログに残す
            response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'generation_failed'))
        self.assertIn('KeyError', response.json()['detail'])
        self.assertEqual(VisaReturnPdfGeneration.objects.get().error_code, 'generation_failed')

    def test_storage_failure_is_a_recorded_business_error_without_download(self):
        from django.db.models.fields.files import FieldFile

        app = self.create(guarantor_template=self.template.id)
        with mock.patch.object(FieldFile, 'save', side_effect=OSError(28, 'No space left on device')), \
                self.assertLogs('apps.accounting.visa_pdf_generation', 'ERROR'):
            response = self.generate(app['id'])
        self.assertEqual(response.status_code, 422, response.content)
        body = response.json()
        self.assertEqual(body['code'], 'storage_failed')
        self.assertIsNone(body['generation']['download_url'])
        failed = VisaReturnPdfGeneration.objects.get()
        self.assertEqual((failed.status, failed.error_code, failed.file.name or ''), ('failed', 'storage_failed', ''))
        self.assertTrue(AuditLog.objects.filter(action='visa_pdf_failed', extra__code='storage_failed').exists())
        # 保存はできたが実在を確認できない
        with mock.patch('django.core.files.storage.FileSystemStorage.exists', return_value=False):
            response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'output_missing'))
        # 読み出せないファイルは 404（500 にしない）
        ok = self.generate(app['id']).json()
        with mock.patch('django.core.files.storage.FileSystemStorage.open', side_effect=PermissionError('denied')), \
                self.assertLogs('apps.accounting.views', 'ERROR'):
            download = self.get('/api' + ok['download_url'])
        self.assertEqual((download.status_code, download.json()['code']), (404, 'file_missing'))

    def media_files(self):
        from django.conf import settings

        root = Path(settings.MEDIA_ROOT)
        return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()) if root.exists() else []

    def test_legacy_pdf_endpoint_is_gone_and_generates_nothing(self):
        app = self.create(guarantor_template=self.template.id)
        before_files = self.media_files()
        renderers = [
            mock.patch.object(visa_return_pdf, '_render_visa_return_pdf'),
            mock.patch.object(visa_return_pdf, 'fill_form_pdf'),
            mock.patch.object(visa_return_pdf, 'generate_visa_return_pdf_by_coordinates'),
            mock.patch('apps.accounting.visa_pdf_generation.render_visa_return_pdf'),
            mock.patch('apps.accounting.visa_pdf_generation.generate_and_record'),
            mock.patch('apps.accounting.views.generate_and_record'),
        ]
        mocks = [patcher.start() for patcher in renderers]
        try:
            response = self.get(f"{self.URL}{app['id']}/pdf/")
        finally:
            for patcher in renderers:
                patcher.stop()
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response['Content-Type'], 'application/json')
        body = response.json()
        self.assertEqual(body['code'], 'legacy_pdf_endpoint_disabled')
        self.assertIn('generate-pdf', body['detail'])
        for called in mocks:
            called.assert_not_called()  # 生成関数を一切呼ばない
        self.assertFalse(VisaReturnPdfGeneration.objects.exists())
        self.assertEqual(self.media_files(), before_files)  # ファイルを作らない
        self.assertTrue(AuditLog.objects.filter(action='visa_pdf_legacy_endpoint_called',
                                                object_id=str(app['id'])).exists())
        # 欠けた申請でも同じ 410（旧接口では検証も生成もしない）
        incomplete = self.create(guarantor_template=None, passport_number='')
        self.assertEqual(self.get(f"{self.URL}{incomplete['id']}/pdf/").status_code, 410)
        # 権限・範囲は従来どおり：権限の無い利用者には 403
        self.assertEqual(self.get(f"{self.URL}{app['id']}/pdf/", self.staff_a).status_code, 403)
        # 正式な生成と、生成記録からのダウンロードは引き続き使える
        created = self.generate(app['id'])
        self.assertEqual(created.status_code, 201, created.content)
        generation = created.json()
        download = self.get('/api' + generation['download_url'])
        self.assertEqual(download.status_code, 200)
        content = b''.join(download.streaming_content)
        self.assertTrue(content.startswith(b'%PDF'))
        self.assertEqual(VisaReturnPdfGeneration.objects.filter(status='success').count(), 1)
        self.assertEqual(len(self.media_files()), len(before_files) + 1)

    def test_batch_zip_uses_the_formal_generation_service(self):
        from apps.accounting.models import VisaImportBatch

        batch = VisaImportBatch.objects.create(file_name='qa.csv', file_sha256='0' * 64)
        complete = self.create(guarantor_template=self.template.id)
        incomplete = self.create(guarantor_template=None, passport_number='')
        VisaReturnApplication.objects.filter(pk__in=[complete['id'], incomplete['id']]).update(import_batch=batch)
        VisaReturnApplication.objects.filter(pk=complete['id']).update(import_row_number=2)
        VisaReturnApplication.objects.filter(pk=incomplete['id']).update(import_row_number=3)
        response = self.post(self.li, f'/api/accounting/visa-imports/{batch.id}/pdf-zip/')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response['X-Success-Count'], response['X-Failure-Count']), ('1', '1'))
        import io
        import zipfile

        archive = zipfile.ZipFile(io.BytesIO(response.content))
        pdfs = [name for name in archive.namelist() if name.endswith('.pdf')]
        self.assertEqual(len(pdfs), 1)
        generation = VisaReturnPdfGeneration.objects.get(application_id=complete['id'])
        self.assertEqual((generation.status, generation.details.get('source')), ('success', 'batch_zip'))
        # ZIP に入れたのは生成記録に保存したファイルそのもの
        import hashlib

        self.assertEqual(hashlib.sha256(archive.read(pdfs[0])).hexdigest(), generation.file_sha256)
        result = archive.read('結果.txt').decode('utf-8')
        self.assertIn('3行目', result)
        self.assertIn('旅券番号', result)  # 不足項目を示す（PDF は作らない）
        self.assertFalse(VisaReturnPdfGeneration.objects.filter(application_id=incomplete['id']).exists())

    def test_manual_edit_overrides_template_and_is_marked_manual(self):
        app = self.create(guarantor_template=self.template.id, guarantor_phone='080-9999-9999')
        check = self.get(f"{self.URL}{app['id']}/check/").json()
        sources = {row['key']: (row['value'], row['source']) for row in check['fields']}
        self.assertEqual(sources['guarantor_phone'], ('080-9999-9999', 'manual'))
        self.assertEqual(sources['guarantor_name_jp'][1], 'template')

    def test_missing_required_fields_block_generation_without_record(self):
        app = self.create(guarantor_template=None, passport_number='', birth_date=None)
        response = self.generate(app['id'])
        self.assertEqual(response.status_code, 400)
        fields = {row['field'] for row in response.json()['fields']}
        self.assertTrue({'passport_number', 'birth_date', 'guarantor_name_jp', 'guarantor_phone'} <= fields)
        self.assertFalse(VisaReturnPdfGeneration.objects.exists())

    def test_template_field_mismatch_is_reported_not_silently_degraded(self):
        app = self.create(guarantor_template=self.template.id)
        broken = {'mappings': {'pinyin_name1': {'pdf_field': 'NoSuchField[0]', 'type': 'text'}}}
        with mock.patch.object(visa_return_pdf, 'load_form_field_mapping', return_value=broken), \
                mock.patch.object(visa_return_pdf, 'generate_visa_return_pdf_by_coordinates') as coordinates:
            response = self.generate(app['id'])
        self.assertEqual(response.status_code, 422, response.content)
        body = response.json()
        self.assertEqual(body['code'], 'template_field_mismatch')
        self.assertIn('pinyin_name1→NoSuchField[0]', body['fields'])
        coordinates.assert_not_called()  # 座標方式へ黙って切り替えない
        self.assertIsNone(body['generation']['download_url'])
        failed = VisaReturnPdfGeneration.objects.get()
        self.assertEqual((failed.status, failed.error_code), ('failed', 'template_field_mismatch'))
        # 入力内容は変わらない。修正後（対応表が直った後）に再試行できる
        self.assertEqual(VisaReturnApplication.objects.get(pk=app['id']).passport_number, 'E12345678')
        retry = self.generate(app['id'])
        self.assertEqual(retry.status_code, 201, retry.content)

    def test_broken_template_file_returns_readable_error(self):
        app = self.create(guarantor_template=self.template.id)
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(safe_rmtree, tmp)
        bad = tmp / 'visa_tem.pdf'
        bad.write_bytes(PNG_NOT_PDF)
        with mock.patch.object(visa_return_pdf, 'VISA_FORM_TEMPLATE_PATH', bad):
            response = self.generate(app['id'])
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['code'], 'template_broken')
        self.assertIn('visa_tem.pdf', response.json()['detail'])

    def test_write_and_flatten_failures_are_errors(self):
        app = self.create(guarantor_template=self.template.id)
        with mock.patch.object(visa_return_pdf, 'fill_text_mapping', return_value=False), \
                mock.patch.object(visa_return_pdf, 'draw_value_on_field', return_value=False):
            response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'field_write_failed'))
        with mock.patch.object(visa_return_pdf, 'flatten_form_pdf_bytes', side_effect=RuntimeError('boom')):
            response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'flatten_failed'))
        with mock.patch.object(visa_return_pdf, 'fill_form_pdf', return_value=b'garbage'):
            response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'output_invalid'))
        self.assertEqual(VisaReturnPdfGeneration.objects.filter(status='failed').count(), 3)

    def test_coordinate_method_is_explicit_and_recorded(self):
        app = self.create(guarantor_template=self.template.id)
        with mock.patch.object(visa_return_pdf, 'form_assets_available', return_value=False):
            response = self.generate(app['id'])
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['method'], 'coordinates')
        with mock.patch.object(visa_return_pdf, 'form_assets_available', return_value=False), \
                mock.patch.object(visa_return_pdf, 'coordinate_assets_available', return_value=False):
            response = self.generate(app['id'])
        self.assertEqual((response.status_code, response.json()['code']), (422, 'template_missing'))

    def test_download_requires_existing_file(self):
        app = self.create(guarantor_template=self.template.id)
        generation = self.generate(app['id']).json()
        record = VisaReturnPdfGeneration.objects.get(pk=generation['id'])
        record.file.storage.delete(record.file.name)
        missing = self.get('/api' + generation['download_url'])
        self.assertEqual((missing.status_code, missing.json()['code']), (404, 'file_missing'))
        listed = self.get(f"{self.URL}{app['id']}/pdf-generations/").json()
        self.assertIsNone(listed[0]['download_url'])  # 実在しないファイルにはリンクを出さない
        failed = VisaReturnPdfGeneration.objects.create(application_id=app['id'], status='failed', error_code='x')
        self.assertEqual(self.get(f"{self.URL}{app['id']}/pdf-generations/{failed.pk}/download/").status_code, 404)

    def test_inactive_template_cannot_be_newly_selected(self):
        self.template.is_active = False
        self.template.save()
        response = self.post(self.li, self.URL, {**self.applicant, 'guarantor_template': self.template.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('guarantor_template', response.json())

    def test_visa_permissions(self):
        app = self.create(guarantor_template=self.template.id)
        generation = self.generate(app['id']).json()
        su = make_user('p1_visa_su', superuser=True)
        for user in (self.staff_a, self.jiao, su):
            self.assertEqual(self.generate(app['id'], user).status_code, 403, user.username)
            self.assertEqual(self.get(f"{self.URL}{app['id']}/check/", user).status_code, 403)
            self.assertEqual(self.get('/api' + generation['download_url'], user).status_code, 403)

    def test_legacy_application_without_template_still_generates_from_manual_guarantor(self):
        app = VisaReturnApplication.objects.create(
            applicant_name='旧データ', birth_date='1990-01-01', nationality='中国', passport_number='E1',
            passport_expiry_date='2031-01-01', guarantor_name='手入力 担保人', guarantor_phone='06-0000-0000',
            guarantor_address='大阪', guarantor_snapshot={'template_name': '旧'},
        )
        # 申請人氏名だけで英文姓・中文姓が無い旧データは、氏名欄が空の PDF を作らず不足として返す
        response = self.generate(app.id)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual([f['field'] for f in response.json()['fields']], ['printed_name'])
        self.assertFalse(app.pdf_generations.exists())
        app.form_data = {'chinese_name1': '旧', 'chinese_name2': 'データ'}
        app.save(update_fields=['form_data'])
        response = self.generate(app.id)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(response.json()['guarantor_template'])
