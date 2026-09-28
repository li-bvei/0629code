"""返签 visa 表の CSV/XLSX 一括取込：読込・対応付け・検証・重複・作成方式・再試行・PDF ZIP・監査・権限。"""
import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from apps.accounting.models import VisaImportBatch, VisaReturnApplication
from apps.accounting.visa_import import parse_date_value, read_csv
from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, SYSTEM_ADMIN
from apps.authentication.testing import make_user

CSV_TEXT = (
    '氏名,性別,生年月日,旅券番号,電話番号,メール\n'
    '王小明,男,1990/01/02,E12345678,09011112222,wang@example.com\n'
    '\n'
    '李花,女性,1992年3月4日,e 87654321,,\n'
    ',男,1990-01-01,E00000001,,\n'
    '張三,不明,2026-13-01,E11111111,,bad-mail\n'
)


class VisaImportTests(TestCase):
    def setUp(self):
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], superuser=True, employee_name='李')
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], superuser=True, employee_name='焦')
        self.client.force_login(self.li)

    def parse(self, content, name='visa.csv', **extra):
        return self.client.post('/api/accounting/visa-imports/parse/', {'file': SimpleUploadedFile(name, content), **extra})

    def preview(self, batch_id, body):
        return self.client.post(f'/api/accounting/visa-imports/{batch_id}/preview/', body, content_type='application/json')

    def commit(self, batch_id, body):
        return self.client.post(f'/api/accounting/visa-imports/{batch_id}/commit/', body, content_type='application/json')

    # --- 読込 ---------------------------------------------------------------------
    def test_csv_encodings_blank_rows_and_auto_mapping(self):
        for encoding in ('utf-8-sig', 'cp932', 'gb18030'):
            response = self.parse(CSV_TEXT.encode(encoding))
            self.assertEqual(response.status_code, 201, response.content)
            data = response.json()
            self.assertEqual(data['encoding'], encoding)
            self.assertEqual(data['row_count'], 4)
            self.assertEqual(data['blank_rows_skipped'], 1)
            self.assertEqual(data['mapping']['氏名'], 'applicant_name')
            self.assertEqual(data['mapping']['旅券番号'], 'passport_number')
            self.assertEqual(data['rows'][0]['cells']['電話番号'], '09011112222')  # 先頭 0 を保持
        self.assertTrue(AuditLog.objects.filter(action='visa_import_parse', user=self.li).exists())

    def test_xlsx_sheets_dates_and_numeric_leading_zero_warning(self):
        workbook = Workbook()
        workbook.active.title = '一覧'
        other = workbook.create_sheet('申請者')
        from datetime import datetime
        other.append(['申請人氏名', '生年月日', '旅券番号', '電話'])
        other.append(['陳一', datetime(1988, 5, 6), 'G1234567', 9012345678])
        buffer = io.BytesIO()
        workbook.save(buffer)
        response = self.parse(buffer.getvalue(), name='visa.xlsx', sheet='申請者')
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data['sheets'], ['一覧', '申請者'])
        self.assertEqual(data['sheet_name'], '申請者')
        preview = self.preview(data['batch_id'], {'mapping': data['mapping'], 'rows': data['rows']}).json()
        row = preview['results'][0]
        self.assertEqual(row['values']['birth_date'], '1988-05-06')
        self.assertIn('leading_zero', [w['code'] for w in row['warnings']])
        self.assertEqual(self.parse(buffer.getvalue(), name='visa.xlsx', sheet='無い').status_code, 400)

    def test_unsupported_and_empty_files(self):
        self.assertEqual(self.parse(b'x', name='visa.pdf').status_code, 400)
        self.assertEqual(self.parse(b'\n\n', name='visa.csv').status_code, 400)

    def test_date_parsing(self):
        self.assertEqual(parse_date_value('2026.9.1').isoformat(), '2026-09-01')
        self.assertEqual(parse_date_value('20260901').isoformat(), '2026-09-01')
        self.assertEqual(parse_date_value('45536', 'number').isoformat(), '2024-09-01')
        with self.assertRaises(ValueError):
            parse_date_value('9/1/2026')

    # --- 検証・作成 -------------------------------------------------------------------
    def _parsed(self):
        data = self.parse(CSV_TEXT.encode('utf-8')).json()
        return data['batch_id'], data['mapping'], data['rows']

    def test_preview_shows_raw_value_converted_value_and_errors(self):
        batch_id, mapping, rows = self._parsed()
        preview = self.preview(batch_id, {'mapping': mapping, 'rows': rows}).json()
        results = {r['row_number']: r for r in preview['results']}
        ok = results[2]
        self.assertEqual(ok['values']['gender'], 'male')
        self.assertEqual(ok['values']['birth_date'], '1990-01-02')
        self.assertEqual(ok['raw']['birth_date'], '1990/01/02')
        self.assertEqual(results[4]['values']['passport_number'], 'E87654321')
        self.assertIn('申請人氏名は必須です。', [e['message'] for e in results[5]['errors']])
        messages = ' '.join(e['message'] for e in results[6]['errors'])
        self.assertIn('性別', messages)
        self.assertIn('日付形式', messages)
        self.assertIn('メール', messages)
        self.assertEqual(preview['valid_count'], 2)
        self.assertEqual(preview['error_count'], 2)

    def test_valid_only_mode_creates_valid_rows_and_reports_errors_then_retry(self):
        batch_id, mapping, rows = self._parsed()
        response = self.commit(batch_id, {'mapping': mapping, 'rows': rows, 'mode': 'valid_only', 'request_id': 'r1'})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['success_count'], 2)
        self.assertEqual(data['error_count'], 2)
        self.assertEqual(data['status'], 'partial')
        self.assertEqual(VisaReturnApplication.objects.filter(import_batch_id=batch_id).count(), 2)
        # 同じ request_id の再送は何も作らない
        again = self.commit(batch_id, {'mapping': mapping, 'rows': rows, 'mode': 'valid_only', 'request_id': 'r1'}).json()
        self.assertTrue(again['replayed'])
        self.assertEqual(VisaReturnApplication.objects.count(), 2)
        # 誤り行を修正して再試行：作成済みの行は重複作成しない
        fixed = [dict(r, cells=dict(r['cells'])) for r in rows]
        fixed[2]['cells']['氏名'] = '補正太郎'
        fixed[3]['cells'].update({'性別': '男', '生年月日': '2000-01-01', 'メール': ''})
        data = self.commit(batch_id, {'mapping': mapping, 'rows': fixed, 'mode': 'valid_only', 'request_id': 'r2'}).json()
        self.assertEqual(data['success_count'], 4)
        self.assertEqual(data['error_count'], 0)
        self.assertEqual(data['status'], 'completed')
        self.assertEqual(VisaReturnApplication.objects.filter(import_batch_id=batch_id).count(), 4)
        self.assertEqual(AuditLog.objects.filter(action='visa_import_commit', object_id=str(batch_id)).count(), 2)

    def test_all_or_nothing_mode_creates_nothing_on_error(self):
        batch_id, mapping, rows = self._parsed()
        response = self.commit(batch_id, {'mapping': mapping, 'rows': rows, 'mode': 'all_or_nothing'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(VisaReturnApplication.objects.count(), 0)
        self.assertTrue(AuditLog.objects.filter(action='visa_import_commit', result='denied').exists())

    def test_duplicate_detection_existing_file_and_in_file(self):
        VisaReturnApplication.objects.create(applicant_name='王小明', passport_number='E12345678')
        batch_id, mapping, rows = self._parsed()
        preview = self.preview(batch_id, {'mapping': mapping, 'rows': rows}).json()
        self.assertEqual(preview['duplicate_count'], 1)
        data = self.commit(batch_id, {'mapping': mapping, 'rows': rows[:2], 'mode': 'valid_only'}).json()
        self.assertEqual(data['skipped_count'], 1)
        self.assertEqual(data['success_count'], 1)
        # 同じファイルを再度読み込むと「取込済みファイル」と表示される
        again = self.parse(CSV_TEXT.encode('utf-8')).json()
        self.assertTrue(again['duplicate_file'])
        # ファイル内の重複
        dup = self.parse('氏名,旅券番号\nA,X1\nB,x1\n'.encode()).json()
        result = self.preview(dup['batch_id'], {'mapping': dup['mapping'], 'rows': dup['rows']}).json()['results'][1]
        self.assertIn('duplicate_in_file', [w['code'] for w in result['warnings']])

    def test_shared_fields_fill_empty_row_values(self):
        data = self.parse('氏名,旅券番号\nA,P1\n'.encode()).json()
        result = self.preview(data['batch_id'], {'mapping': data['mapping'], 'rows': data['rows'],
                                                 'shared': {'guarantor_name': '在日保証人'}}).json()['results'][0]
        self.assertEqual(result['values']['guarantor_name'], '在日保証人')

    def test_error_report_and_pdf_zip_are_audited(self):
        batch_id, mapping, rows = self._parsed()
        self.commit(batch_id, {'mapping': mapping, 'rows': rows, 'mode': 'valid_only'})
        report = self.client.get(f'/api/accounting/visa-imports/{batch_id}/error-report/')
        self.assertEqual(report.status_code, 200)
        text = report.content.decode('utf-8-sig')
        self.assertIn('行番号', text)
        self.assertIn('申請人氏名は必須です。', text)
        self.assertTrue(AuditLog.objects.filter(action='visa_import_error_report').exists())
        response = self.client.post(f'/api/accounting/visa-imports/{batch_id}/pdf-zip/', {}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        self.assertIn('結果.txt', archive.namelist())
        total = int(response['X-Success-Count']) + int(response['X-Failure-Count'])
        self.assertEqual(total, 2)
        self.assertTrue(AuditLog.objects.filter(action='visa_pdf_zip_export').exists())

    def test_permissions(self):
        self.client.force_login(self.jiao)
        self.assertEqual(self.parse(CSV_TEXT.encode()).status_code, 403)
        self.assertEqual(self.client.get('/api/accounting/visa-imports/template/').status_code, 403)
        self.client.logout()
        self.assertIn(self.parse(CSV_TEXT.encode()).status_code, (401, 403))
        self.client.force_login(self.li)
        template = self.client.get('/api/accounting/visa-imports/template/')
        self.assertEqual(template.status_code, 200)
        self.assertIn('申請人氏名', template.content.decode('utf-8-sig'))

    def test_read_csv_rejects_unknown_encoding(self):
        from apps.accounting.visa_import import VisaImportError

        with self.assertRaises(VisaImportError):
            read_csv(b'\xff\xfe\x00\x00garbage', encoding='ascii')
