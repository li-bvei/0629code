"""P5 清風合格通知書（固定テンプレート）。すべて合成データ。

本物の MS Mincho はリポジトリに無いため、版面・生成の確認はリポジトリ内の Yu Mincho を MS Mincho として
差し替えて行う（字体名の厳密な確認は別のテストで本来の関数を使う）。保存先は一時ディレクトリ。
"""
import hashlib
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

import fitz
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from apps.accounting.models import SeifuNoticePdfGeneration, SeifuNoticePdfRecord
from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, STAFF
from apps.authentication.testing import make_user

from . import seifu_notice_pdf
from apps.common.test_isolation import safe_rmtree

BASE = '/api/accounting/seifu-notice-records/'
GENERATIONS = '/api/accounting/seifu-notice-generations/'
TEST_FONT = Path(__file__).resolve().parents[2] / 'assets' / 'fonts' / 'YuMincho.ttf'


def files_under(root):
    return [p for p in Path(root).rglob('*') if p.is_file()]


class SeifuFixture:
    def setUp(self):
        self.media = tempfile.mkdtemp(prefix='seifu_test_')
        self.media_override = override_settings(MEDIA_ROOT=self.media)
        self.media_override.enable()
        self.font_patch = mock.patch('apps.accounting.seifu_notice_pdf.exact_font_path', return_value=TEST_FONT)
        self.font_patch.start()
        self.accounting = make_user('seifu_accounting', roles=(ACCOUNTING_ADMIN,), employee_name='会計担当')
        self.staff = make_user('seifu_staff', roles=(STAFF,), employee_name='一般担当')
        self.su_only = make_user('seifu_su_only', superuser=True)

    def tearDown(self):
        self.font_patch.stop()
        self.media_override.disable()
        safe_rmtree(self.media)

    def post(self, user, url, body=None):
        self.client.force_login(user)
        return self.client.post(url, body or {}, content_type='application/json')

    def patch(self, user, url, body):
        self.client.force_login(user)
        return self.client.patch(url, body, content_type='application/json')

    def get(self, user, url):
        self.client.force_login(user)
        return self.client.get(url)

    def create_record(self, **extra):
        body = {'title': 'QA 合格通知書', 'recipient_name': '合成 太郎', 'permit_number': '99a0012',
                'issue_date': '2027-01-15', **extra}
        response = self.post(self.accounting, BASE, body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def generate(self, row_id, user=None, request_id=None):
        body = {'request_id': request_id} if request_id else {}
        return self.post(user or self.accounting, f'{BASE}{row_id}/generate_pdf/', body)

    def assertNoGeneration(self):
        self.assertEqual(SeifuNoticePdfGeneration.objects.count(), 0)
        self.assertEqual(files_under(self.media), [])


class SeifuRecordInputTests(SeifuFixture, TestCase):
    def test_fields_are_normalized_and_notice_number_is_derived_by_server(self):
        row = self.create_record(permit_number='９９ａ００１２')  # 全角は半角・大文字にそろえる
        self.assertEqual((row['permit_number'], row['notice_number']), ('99A0012', '99A0012 A'))
        self.assertEqual(row['template_key'], seifu_notice_pdf.TEMPLATE_KEY)
        self.assertEqual(seifu_notice_pdf.derive_notice_number('99A0012'), row['notice_number'])
        self.assertTrue(AuditLog.objects.filter(action='seifu_notice_created', object_id=str(row['id'])).exists())

    def test_client_cannot_set_derived_fields_template_coordinates_or_font(self):
        for extra in ({'notice_number': 'X1 A'}, {'text_items': [{'text': '任意', 'x': 1, 'y': 1}]}, {'x': 10},
                      {'font': 'Other'}, {'font_size': 70}, {'template_key': 'other_template'},
                      {'enrollment_period': '2000/01/01'}, {'course_years': '3'}):
            response = self.post(self.accounting, BASE, {'title': 't', 'recipient_name': '合成 太郎',
                                                         'permit_number': '99A0012', 'issue_date': '2027-01-15', **extra})
            self.assertEqual(response.status_code, 400, extra)
        self.assertEqual(SeifuNoticePdfRecord.objects.count(), 0)

    def test_each_required_field_and_invalid_values(self):
        valid = {'title': 't', 'recipient_name': '合成 太郎', 'permit_number': '99A0012', 'issue_date': '2027-01-15'}
        for field in ('recipient_name', 'permit_number', 'issue_date'):
            body = {k: v for k, v in valid.items() if k != field}
            response = self.post(self.accounting, BASE, body)
            self.assertEqual(response.status_code, 400, field)
            self.assertIn(field, response.json())
            response = self.post(self.accounting, BASE, {**valid, field: ''})
            self.assertEqual(response.status_code, 400, field)
        for field, value in (
            ('issue_date', '2027-02-30'), ('issue_date', '1999-12-31'), ('issue_date', '2100-01-01'),
            ('permit_number', '番号'), ('permit_number', 'ABC'), ('permit_number', '12'), ('permit_number', '99A0012!'),
            ('permit_number', '1234567890123'), ('permit_number', '-99A0012'), ('permit_number', '99 A0012'),
            ('recipient_name', '合成​太郎'), ('recipient_name', '合成\n太郎'), ('recipient_name', '合成‮太郎'),
            ('recipient_name', 'あ' * 41),
        ):
            response = self.post(self.accounting, BASE, {**valid, field: value})
            self.assertEqual(response.status_code, 400, (field, value))
            self.assertIn(field, response.json(), (field, value))
        self.assertEqual(SeifuNoticePdfRecord.objects.count(), 0)

    def test_names_that_do_not_fit_or_have_no_glyph_are_refused_before_generation(self):
        valid = {'title': 't', 'permit_number': '99A0012', 'issue_date': '2027-01-15'}
        too_wide = self.post(self.accounting, BASE, {**valid, 'recipient_name': '合成合成合成合成合成'})  # 10 文字（字号・長体の下限でも入らない）
        self.assertEqual(too_wide.status_code, 400)
        self.assertIn('収まりません', too_wide.json()['recipient_name'][0])
        no_glyph = self.post(self.accounting, BASE, {**valid, 'recipient_name': '合成 😀'})
        self.assertEqual(no_glyph.status_code, 400)
        self.assertIn('印字できません', no_glyph.json()['recipient_name'][0])

    def test_legacy_records_stay_readable_and_text_items_are_kept_on_update(self):
        legacy = SeifuNoticePdfRecord.objects.create(title='旧記録', text_items=[{'text': '旧', 'x': 1, 'y': 1, 'page': 1}])
        row = self.get(self.accounting, f'{BASE}{legacy.pk}/').json()
        self.assertTrue(row['is_legacy'])
        self.assertEqual((row['notice_number'], row['latest_generation']), ('', None))
        self.assertEqual(self.patch(self.accounting, f'{BASE}{legacy.pk}/', {'note': '備考だけ'}).status_code, 200)
        legacy.refresh_from_db()
        self.assertEqual(len(legacy.text_items), 1)  # 旧データを消さない
        response = self.generate(legacy.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'missing_recipient_name')
        self.assertNoGeneration()
        # 3 項目を入れれば作成できる
        self.assertEqual(self.patch(self.accounting, f'{BASE}{legacy.pk}/', {
            'recipient_name': '合成 次郎', 'permit_number': '99A0013', 'issue_date': '2027-03-09'}).status_code, 200)
        self.assertEqual(self.generate(legacy.pk).status_code, 201)


class SeifuGenerationTests(SeifuFixture, TestCase):
    def test_generate_stores_verified_file_and_records_metadata_then_download(self):
        row = self.create_record()
        response = self.generate(row['id'], request_id='req-00000001')
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        generation = SeifuNoticePdfGeneration.objects.get(pk=data['id'])
        self.assertEqual((generation.status, generation.method), ('success', seifu_notice_pdf.GENERATION_METHOD))
        self.assertEqual((generation.recipient_name, generation.permit_number, generation.notice_number),
                         ('合成 太郎', '99A0012', '99A0012 A'))
        self.assertEqual(generation.issue_date, date(2027, 1, 15))
        self.assertEqual(generation.template_key, seifu_notice_pdf.TEMPLATE_KEY)
        self.assertEqual(len(generation.template_version), 16)
        self.assertEqual(len(generation.font_version), 16)
        self.assertEqual(generation.created_by, self.accounting)
        with default_storage.open(generation.file.name, 'rb') as handle:
            stored = handle.read()
        self.assertEqual((generation.file_size, generation.file_sha256), (len(stored), hashlib.sha256(stored).hexdigest()))
        download = self.get(self.accounting, f'{GENERATIONS}{generation.pk}/download/')
        self.assertEqual(download.status_code, 200)
        body = b''.join(download.streaming_content)
        self.assertEqual(body, stored)
        with fitz.open(stream=body, filetype='pdf') as doc:
            text = doc[0].get_text().replace(' ', '')
        for expected in ('99A0012A', '99A0012', '合成太郎', '2027年01月15日', '2027/04/01～2029/03/31'):
            self.assertIn(expected, text)
        self.assertTrue(AuditLog.objects.filter(action='seifu_notice_pdf_generated').exists())
        self.assertTrue(AuditLog.objects.filter(action='seifu_notice_pdf_downloaded').exists())
        record_row = self.get(self.accounting, f'{BASE}{row["id"]}/').json()
        self.assertEqual(record_row['latest_generation']['id'], generation.pk)

    def test_same_request_id_returns_the_same_generation(self):
        row = self.create_record()
        first = self.generate(row['id'], request_id='req-00000002')
        second = self.generate(row['id'], request_id='req-00000002')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.assertTrue(second.json()['replayed'])
        self.assertEqual(SeifuNoticePdfGeneration.objects.count(), 1)
        self.assertEqual(len(files_under(self.media)), 1)
        other = self.create_record(recipient_name='合成 花子')
        self.assertEqual(self.generate(other['id'], request_id='req-00000002').status_code, 400)
        self.assertEqual(self.generate(other['id'], request_id='bad id!').status_code, 400)
        # request_id が無い通常の操作は毎回作る
        self.assertEqual(self.generate(row['id']).status_code, 201)
        self.assertEqual(SeifuNoticePdfGeneration.objects.count(), 2)

    def test_permissions_without_superuser_bypass(self):
        row = self.create_record()
        generation_id = self.generate(row['id']).json()['id']
        for user in (self.staff, self.su_only):
            self.assertEqual(self.generate(row['id'], user=user).status_code, 403)
            self.assertEqual(self.get(user, f'{GENERATIONS}{generation_id}/download/').status_code, 403)
            self.assertEqual(self.get(user, BASE).status_code, 403)
            self.assertEqual(self.post(user, f'{BASE}{row["id"]}/preview_pdf/').status_code, 403)
        self.assertEqual(self.get(self.accounting, f'{GENERATIONS}999999/download/').status_code, 404)
        self.assertEqual(SeifuNoticePdfGeneration.objects.count(), 1)

    def test_download_when_file_is_missing(self):
        row = self.create_record()
        generation = SeifuNoticePdfGeneration.objects.get(pk=self.generate(row['id']).json()['id'])
        default_storage.delete(generation.file.name)
        response = self.get(self.accounting, f'{GENERATIONS}{generation.pk}/download/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], 'file_missing')
        self.assertTrue(AuditLog.objects.filter(action='seifu_notice_pdf_download_missing').exists())

    def test_preview_does_not_store_or_record(self):
        row = self.create_record()
        response = self.post(self.accounting, f'{BASE}{row["id"]}/preview_pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertNoGeneration()

    def test_legacy_arbitrary_endpoint_is_gone_and_creates_nothing(self):
        with mock.patch('apps.accounting.seifu_notice_pdf.render_seifu_notice_pdf') as render, \
                mock.patch('apps.accounting.seifu_pdf_generation.render_seifu_notice_pdf') as render2:
            response = self.post(self.accounting, '/api/accounting/seifu-notice-pdf/generate/', {
                'items': [{'text': '任意', 'x': 1, 'y': 1, 'page': 1, 'font_size': 40}],
            })
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()['code'], 'legacy_seifu_endpoint_disabled')
        render.assert_not_called()
        render2.assert_not_called()
        self.assertNoGeneration()
        self.assertTrue(AuditLog.objects.filter(action='seifu_legacy_endpoint_called', result='denied').exists())
        self.assertEqual(self.post(self.staff, '/api/accounting/seifu-notice-pdf/generate/', {}).status_code, 403)


class SeifuFailureTests(SeifuFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.row = self.create_record()

    def assertFails(self, code, http_status=422):
        response = self.generate(self.row['id'], request_id='req-failure-1')
        self.assertEqual(response.status_code, http_status, response.content)
        self.assertEqual(response.json()['code'], code)
        self.assertNoGeneration()
        self.assertTrue(AuditLog.objects.filter(action='seifu_notice_pdf_failed', result='error').exists())
        return response

    def test_template_missing_and_broken(self):
        with mock.patch.object(seifu_notice_pdf, 'TEMPLATE_PATH', Path(self.media) / 'none.pdf'):
            self.assertFails('template_missing')
        broken = Path(tempfile.mkdtemp()) / 'broken.pdf'
        broken.write_bytes(b'not a pdf at all')
        try:
            with mock.patch.object(seifu_notice_pdf, 'TEMPLATE_PATH', broken):
                self.assertFails('template_broken')
        finally:
            safe_rmtree(broken.parent)

    def test_font_missing_broken_or_not_ms_mincho(self):
        self.font_patch.stop()
        try:
            folder = Path(tempfile.mkdtemp())
            broken = folder / 'broken.ttf'
            broken.write_bytes(b'garbage font bytes')
            for path, code in ((folder / 'none.ttf', 'font_missing'), (broken, 'font_broken'), (TEST_FONT, 'font_mismatch')):
                with override_settings(SEIFU_MS_MINCHO_FONT_PATH=str(path)):
                    self.assertFails(code)
            safe_rmtree(folder)
        finally:
            self.font_patch.start()

    def test_drawing_failure(self):
        with mock.patch('apps.accounting.seifu_notice_pdf._draw', side_effect=RuntimeError('draw')):
            self.assertFails('generation_failed')

    def test_empty_or_corrupt_output(self):
        for payload in (b'', b'%PDF-1.4 broken' * 100):
            class FakeBuffer:
                def write(self, data):
                    return len(data)

                def getvalue(self, payload=payload):
                    return payload

                def seek(self, *args):
                    return 0

                def tell(self):
                    return 0

                def truncate(self, *args):
                    return 0

            with mock.patch('apps.accounting.seifu_notice_pdf.BytesIO', FakeBuffer):
                self.assertFails('output_invalid')

    def test_output_missing_printed_values(self):
        with mock.patch('apps.accounting.seifu_notice_pdf._draw'):  # 何も描かない＝印字欠け
            self.assertFails('output_invalid')

    def test_storage_failure_and_truncated_write_leave_no_file(self):
        with mock.patch.object(default_storage, 'save', side_effect=OSError('disk full')):
            self.assertFails('storage_failed')
        with mock.patch.object(default_storage, 'size', return_value=1):
            self.assertFails('storage_failed')

    def test_database_failure_after_storing_removes_the_file(self):
        with mock.patch.object(SeifuNoticePdfGeneration, 'save', side_effect=RuntimeError('db')):
            self.assertFails('generation_failed')


class SeifuLayoutTests(SeifuFixture, TestCase):
    """合成の宛名・日付で版面に収まり、印字内容が PDF に入ることを確認する。"""

    def test_synthetic_scenarios_render_within_fields(self):
        cases = [
            ('合成 太郎', '99A0012', date(2027, 1, 5)),        # 常用の漢字
            ('合成長名前子', '99A0012', date(2027, 12, 31)),   # 長めの漢字（縮小）
            ('ゴウセイ タロウ', '99B1234', date(2027, 10, 1)),  # 片仮名
            ('GOSEI TARO', '99C7777', date(2028, 2, 29)),      # 英字
        ]
        font = fitz.Font(fontfile=str(TEST_FONT))
        for name, permit, issued in cases:
            result = seifu_notice_pdf.render_seifu_notice_pdf(name, permit, issued)
            with fitz.open(stream=result.content, filetype='pdf') as doc:
                text = doc[0].get_text().replace(' ', '')
            self.assertIn(name.replace(' ', ''), text)
            self.assertIn(f'{issued.year}年{issued.month:02d}月{issued.day:02d}日', text)
            spec = seifu_notice_pdf.FIELDS['recipient_name']
            size, condense = seifu_notice_pdf._fit(font, 'recipient_name', name)
            self.assertGreaterEqual(size, spec['min_size'])
            self.assertGreaterEqual(condense, seifu_notice_pdf.MIN_CONDENSE)
            width = seifu_notice_pdf._text_width(font, name, size, 0) * condense
            self.assertLessEqual(width + spec['point'][0], spec['max_right'] + 0.05)
            # 実際の印字位置も欄の中（テンプレートの「様」の手前）に収まる
            with fitz.open(stream=result.content, filetype='pdf') as doc:
                spans = [s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']
                         if 295 < s['bbox'][1] < 325 and s['bbox'][0] < 160]
            self.assertTrue(spans)
            self.assertLessEqual(max(s['bbox'][2] for s in spans), spec['max_right'] + 0.5)
        long_latin = 'GOSEI TAROUEMON NAGANAMAE'
        with self.assertRaises(seifu_notice_pdf.SeifuPdfError) as caught:
            seifu_notice_pdf.render_seifu_notice_pdf(long_latin, '99A0012', date(2027, 1, 5))
        self.assertEqual(caught.exception.code, 'recipient_name_too_long')

    def test_font_name_check_uses_the_real_function(self):
        self.font_patch.stop()
        try:
            with override_settings(SEIFU_MS_MINCHO_FONT_PATH=str(TEST_FONT)):
                with self.assertRaises(seifu_notice_pdf.SeifuPdfError) as caught:
                    seifu_notice_pdf.exact_font_path()
            self.assertEqual(caught.exception.code, 'font_mismatch')
        finally:
            self.font_patch.start()
