"""P6：資料内容・表示ファイル名（資料内容-顧客名.拡張子）・ZIP アップロードの制限。合成データのみ。"""
import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart

from apps.audit.models import AuditLog
from apps.documents.models import Document
from apps.documents.tests_batch import PDF, DocumentBatchFixture
from apps.documents.upload_policy import MB


def make_zip(entries, compress=zipfile.ZIP_DEFLATED):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compress) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return buffer.getvalue()


class ContentLabelTests(DocumentBatchFixture):
    def post(self, name, label, content=PDF, case=None, extra=None):
        self.client.force_login(self.staff_a)
        body = {'case': (case or self.case_a).id, 'title': name, 'category': 'residence',
                'file': SimpleUploadedFile(name, content), **(extra or {})}
        if label is not None:
            body['content_label'] = label
        return self.client.post('/api/documents/', body)

    def setUp(self):
        super().setUp()
        self.case_a.customer.name = '山田 太郎'  # 合成の氏名
        self.case_a.customer.save()

    def test_display_name_uses_label_backend_customer_name_and_original_extension(self):
        response = self.post('scan_0001.PDF', '住民票')
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual((data['content_label'], data['display_name'], data['file_name']),
                         ('住民票', '住民票-山田太郎.pdf', 'scan_0001.PDF'))
        document = Document.objects.get(pk=data['id'])
        self.assertRegex(document.file.name, r'^case_documents/\d{4}/\d{2}/[0-9a-f]{32}\.pdf$')  # 保存名は UUID
        download = self.client.get(f'/api/documents/{document.pk}/download/')
        self.assertEqual(download.status_code, 200)
        self.assertIn("UTF-8''%E4%BD%8F%E6%B0%91%E7%A5%A8-%E5%B1%B1%E7%94%B0%E5%A4%AA%E9%83%8E.pdf", download['Content-Disposition'])
        self.assertTrue(AuditLog.objects.filter(action='document_upload', object_id=str(document.pk)).exists())

    def test_each_file_has_its_own_label_and_duplicates_get_stable_id_suffix(self):
        first = self.post('a.pdf', '住民票').json()
        second = self.post('b.pdf', '住民票').json()
        third = self.post('c.pdf', '在留カード').json()
        self.assertEqual(first['display_name'], '住民票-山田太郎.pdf')
        self.assertEqual(second['display_name'], f'住民票-山田太郎 (ID {second["id"]}).pdf')
        self.assertEqual(third['display_name'], '在留カード-山田太郎.pdf')
        # ZIP（選択範囲に関係なく）と単体ダウンロードの名前が同じ
        self.client.force_login(self.staff_a)
        for ids in ([second['id']], [first['id'], second['id'], third['id']]):
            response = self.client.post('/api/documents/download-zip/', {'case': self.case_a.id, 'ids': ids},
                                        content_type='application/json')
            self.assertEqual(response.status_code, 200)
            body = b''.join(response.streaming_content) if response.streaming else response.content
            names = zipfile.ZipFile(io.BytesIO(body)).namelist()
            self.assertIn(f'在留関係/住民票-山田太郎 (ID {second["id"]}).pdf', names)

    def test_customer_name_cannot_be_forged_and_label_is_validated(self):
        forged = self.post('a.pdf', '住民票', extra={'display_name': '偽物.exe', 'customer_name': '別人'}).json()
        self.assertEqual(forged['display_name'], '住民票-山田太郎.pdf')
        # content_label を送った上で空・不正なら 400（送らない旧 API 互換は LegacySingleUploadTests）
        for label in ('', '   ', '../住民票', 'a/b', 'a\\b', '住民票.', '.hidden', 'CON', 'a' * 61, '住民\x07票',
                      '住民‮票', 'a:b', 'a|b'):
            response = self.post('a.pdf', label)
            self.assertEqual(response.status_code, 400, label)
            self.assertIn('content_label', response.json(), label)
        # 資料内容に拡張子らしい文字を入れても、元の拡張子は変わらない
        self.assertEqual(self.post('a.pdf', '住民票 exe').json()['display_name'], '住民票 exe-山田太郎.pdf')

    def test_company_name_when_customer_name_missing_and_error_when_neither(self):
        from apps.companies.models import Company

        self.case_a.customer.name = ''
        self.case_a.customer.save()
        self.case_a.company = Company.objects.create(name='合成株式会社')
        self.case_a.save()
        self.assertEqual(self.post('a.pdf', '登記簿').json()['display_name'], '登記簿-合成株式会社.pdf')
        self.case_a.company = None
        self.case_a.save()
        response = self.post('a.pdf', '登記簿')
        self.assertEqual(response.status_code, 400)
        self.assertIn('case', response.json())

    def test_dangerous_original_names_rejected_and_legacy_documents_keep_working(self):
        for name in ('CON.pdf', 'evil.exe', 'x.pdf.exe'):  # 制御文字入りの名前は P2 の filename_problem のテストで確認済み
            self.assertEqual(self.post(name, '住民票').status_code, 400, name)
        # パス付きの名前はファイル名部分だけになり、表示名・保存名にパスは入らない
        traversal = self.post('../../x.pdf', '住民票').json()
        self.assertNotIn('..', traversal['file_name'] + traversal['display_name'])
        legacy = Document.objects.create(case=self.case_a, title='旧ファイル', file_name='旧ファイル.pdf', file_path='')
        legacy.file.save('legacy.pdf', SimpleUploadedFile('legacy.pdf', PDF), save=True)
        self.client.force_login(self.staff_a)
        download = self.client.get(f'/api/documents/{legacy.pk}/download/')
        self.assertIn("UTF-8''%E6%97%A7%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB.pdf", download['Content-Disposition'])
        # 後から資料内容を補うと表示名ができる
        response = self.client.patch(f'/api/documents/{legacy.pk}/', {'content_label': 'パスポート'},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['display_name'], 'パスポート-山田太郎.pdf')

    def test_replacement_keeps_label_and_follows_new_extension(self):
        created = self.post('a.pdf', '課税証明書').json()
        self.client.force_login(self.staff_a)
        png = b'\x89PNG\r\n\x1a\n' + b'0' * 100
        response = self.client.patch(f'/api/documents/{created["id"]}/', encode_multipart(BOUNDARY, {
            'case': self.case_a.id, 'title': '課税証明書', 'file': SimpleUploadedFile('photo.png', png),
        }), content_type=MULTIPART_CONTENT)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['display_name'], '課税証明書-山田太郎.png')


class LegacySingleUploadTests(DocumentBatchFixture):
    """旧クライアント互換：P6 以前の単ファイル登録 API（content_label を送らない）は 400 にしない。"""

    def legacy_post(self, title, name='scan.pdf', case=None, **extra):
        self.client.force_login(self.staff_a)
        return self.client.post('/api/documents/', {'case': (case or self.case_a).id, 'title': title,
                                                    'file': SimpleUploadedFile(name, PDF), **extra})

    def setUp(self):
        super().setUp()
        self.case_a.customer.name = '山田 太郎'  # 合成の氏名
        self.case_a.customer.save()

    def test_label_is_derived_from_title_and_customer_name_comes_from_the_case(self):
        response = self.legacy_post('在職証明.pdf', name='zaishoku.PDF', customer_name='別人')
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual((data['content_label'], data['display_name'], data['file_name']),
                         ('在職証明', '在職証明-山田太郎.pdf', 'zaishoku.PDF'))
        log = AuditLog.objects.get(action='document_upload', object_id=str(data['id']))
        self.assertEqual(log.extra['content_label_source'], 'legacy_derived')
        # 新しい画面からの登録は user
        new = self.post_with_label('住民票')
        self.assertEqual(AuditLog.objects.get(action='document_upload', object_id=str(new['id'])).extra['content_label_source'], 'user')

    def post_with_label(self, label):
        self.client.force_login(self.staff_a)
        return self.client.post('/api/documents/', {'case': self.case_a.id, 'title': 'x', 'content_label': label,
                                                    'file': SimpleUploadedFile('x.pdf', PDF)}).json()

    def test_checklist_name_then_sanitized_title_then_file_name_then_category(self):
        from apps.cases.models import CaseChecklistItem

        item = CaseChecklistItem.objects.create(case=self.case_a, name='在留カード')
        self.assertEqual(self.legacy_post('何か', checklist_item=item.id).json()['content_label'], '在留カード')
        self.assertEqual(self.legacy_post('a/b:c..d').json()['content_label'], 'a b c.d')
        self.assertEqual(self.legacy_post('///', name='passport_scan.pdf').json()['content_label'], 'passport_scan')
        self.assertEqual(self.legacy_post('CON', name='CON.pdf').status_code, 400)  # 元のファイル名の検査は変わらない
        self.assertEqual(self.legacy_post('..', name='..pdf', category='residence').status_code, 400)

    def test_case_without_customer_or_company_keeps_pre_p6_behaviour(self):
        self.case_a.customer.name = ''
        self.case_a.customer.save()
        response = self.legacy_post('在職証明')
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual((data['content_label'], data['display_name'], data['download_name']), ('', '', 'scan.pdf'))
        log = AuditLog.objects.get(action='document_upload', object_id=str(data['id']))
        self.assertEqual(log.extra['content_label_source'], 'legacy_no_party')
        # 新しい画面（資料内容を送る）では顧客名を推測せず字段エラー
        self.client.force_login(self.staff_a)
        strict = self.client.post('/api/documents/', {'case': self.case_a.id, 'title': 'x', 'content_label': '住民票',
                                                      'file': SimpleUploadedFile('x.pdf', PDF)})
        self.assertEqual(strict.status_code, 400)
        self.assertIn('case', strict.json())

    def test_replacing_a_legacy_document_without_label_still_records_history(self):
        from apps.documents.models import DocumentReplacement

        legacy = Document.objects.create(case=self.case_a, title='旧ファイル', file_name='旧ファイル.pdf', file_path='')
        legacy.file.save('legacy.pdf', SimpleUploadedFile('legacy.pdf', PDF), save=True)
        self.client.force_login(self.staff_a)
        response = self.client.patch(f'/api/documents/{legacy.pk}/', encode_multipart(BOUNDARY, {
            'case': self.case_a.id, 'title': '旧ファイル', 'replace_reason': '再取得',
            'file': SimpleUploadedFile('new.pdf', PDF),
        }), content_type=MULTIPART_CONTENT)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['display_name'], '')  # 資料内容が無い旧データは改名しない
        self.assertEqual(DocumentReplacement.objects.filter(document=legacy).count(), 1)


class ZipUploadLimitTests(DocumentBatchFixture):
    def upload_zip(self, content, name='合成資料.zip'):
        self.client.force_login(self.staff_a)
        return self.client.post('/api/documents/', {
            'case': self.case_a.id, 'title': name, 'content_label': '合成資料', 'file': SimpleUploadedFile(name, content),
        })

    def test_zip_is_stored_as_attachment_with_safe_structure_only(self):
        ok = self.upload_zip(make_zip([('docs/a.txt', b'hello'), ('b.pdf', PDF)]))
        self.assertEqual(ok.status_code, 201, ok.content)
        cases = {
            'traversal': make_zip([('../evil.txt', b'x')]),
            'absolute': make_zip([('/etc/passwd', b'x')]),
            'nested': make_zip([('inner.zip', make_zip([('a.txt', b'x')]))]),
            'bomb': make_zip([('zeros.txt', b'0' * (5 * MB))]),
            'many': make_zip([(f'f{i}.txt', b'x') for i in range(201)]),
            'not_zip': b'PK\x03\x04' + b'garbage' * 10,
        }
        for label, content in cases.items():
            response = self.upload_zip(content)
            self.assertEqual(response.status_code, 400, label)
            self.assertIn('file', response.json(), label)

    @override_settings(DOCUMENT_ZIP_UPLOAD_MAX_BYTES=1000, DOCUMENT_MAX_UPLOAD_BYTES=5000)
    def test_zip_has_a_stricter_size_limit_than_other_files_in_check_and_upload(self):
        big_zip = make_zip([(f'f{i}.bin', bytes(range(256)) * 8) for i in range(2)], compress=zipfile.ZIP_STORED)
        self.assertGreater(len(big_zip), 1000)
        self.assertEqual(self.upload_zip(big_zip).status_code, 400)
        self.client.force_login(self.staff_a)
        check = self.client.post('/api/documents/upload-check/', {'case': self.case_a.id, 'files': [
            {'name': 'a.zip', 'size': 2000}, {'name': 'b.pdf', 'size': 2000}]}, content_type='application/json')
        rows = check.json()['files']
        self.assertIn('ZIP', rows[0]['problem'])
        self.assertIsNone(rows[1]['problem'])
        policy = self.client.get('/api/documents/upload-policy/').json()
        self.assertEqual((policy['zip_upload_max_bytes'], policy['max_file_bytes']), (1000, 5000))
