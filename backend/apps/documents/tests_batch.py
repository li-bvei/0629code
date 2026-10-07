"""P2：複数ファイル登録（事前確認・1 件ずつの登録と再試行）と ZIP 一括ダウンロード。"""
import io
import tempfile
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.cases.models import Case, CaseApplicationCategory, CaseTypeMaster
from apps.customers.models import Customer
from apps.documents.models import Document
from apps.documents.upload_policy import filename_problem, validate_upload
from apps.documents.zip_export import plan_entries, safe_component
from apps.employees.models import Employee
from apps.common.test_isolation import safe_rmtree

PDF = b'%PDF-1.4 batch test'
PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 32


class DocumentBatchFixture(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(safe_rmtree, self.media)
        override = override_settings(MEDIA_ROOT=self.media, PROTECTED_MEDIA_X_ACCEL=False)
        override.enable()
        self.addCleanup(override.disable)
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], superuser=True, employee_name='李')
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], superuser=True, employee_name='焦')
        self.staff_a = make_user('staff_a', roles=[STAFF], employee_name='A')
        self.staff_b = make_user('staff_b', roles=[STAFF], employee_name='B')
        ct, _ = CaseTypeMaster.objects.update_or_create(code='db', defaults={'name': '一括試験種別', 'number_abbreviation': '一試'})
        cat, _ = CaseApplicationCategory.objects.update_or_create(code='db', defaults={'name': '一括試験区分', 'number_abbreviation': '一区'})
        customer = Customer.objects.create(name='一括顧客', birth_date='1990-01-01')

        def make_case(user):
            return Case.objects.create(case_type='x', case_type_master=ct, application_category=cat, status=Case.STATUS_OPEN,
                                       customer=customer, responsible_employee=Employee.objects.get(user=user))

        self.case_a = make_case(self.staff_a)
        self.case_b = make_case(self.staff_b)

    # P2 の ZIP 名前規則は「表示名の無い旧データ（元のファイル名）」で確認する（P6 の表示名は tests_p6_documents）
    legacy_names = False

    def upload(self, user, name, content=PDF, case=None, category='other'):
        self.client.force_login(user)
        response = self.client.post('/api/documents/', {
            'case': (case or self.case_a).id, 'title': name, 'category': category,
            'content_label': '合成資料', 'file': SimpleUploadedFile(name, content),
        })
        if self.legacy_names and response.status_code == 201:
            Document.objects.filter(pk=response.json()['id']).update(content_label='', display_name='')
        return response

    def check(self, user, files, case=None):
        self.client.force_login(user)
        return self.client.post('/api/documents/upload-check/', {'case': (case or self.case_a).id, 'files': files},
                                content_type='application/json')

    def zip(self, user, case=None, **body):
        self.client.force_login(user)
        return self.client.post('/api/documents/download-zip/', {'case': (case or self.case_a).id, **body},
                                content_type='application/json')

    @staticmethod
    def read_zip(response):
        content = b''.join(response.streaming_content)
        return zipfile.ZipFile(io.BytesIO(content))


class BatchUploadTests(DocumentBatchFixture):
    def test_all_files_succeed_one_record_and_audit_per_file(self):
        names = ['在留カード.pdf', 'パスポート.png', '住民票.pdf']
        manifest = [{'name': n, 'size': 100} for n in names]
        response = self.check(self.staff_a, manifest)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['ok'])
        self.assertTrue(all(row['problem'] is None for row in response.json()['files']))
        for name in names:
            content = PNG if name.endswith('.png') else PDF
            self.assertEqual(self.upload(self.staff_a, name, content).status_code, 201)
        docs = Document.objects.filter(case=self.case_a)
        self.assertEqual(docs.count(), 3)  # 1 ファイル 1 記録（まとめて 1 つにしない）
        self.assertEqual(len({doc.file.name for doc in docs}), 3)
        self.assertEqual(AuditLog.objects.filter(action='document_upload').count(), 3)

    def test_partial_failure_keeps_successes_and_failed_file_can_be_retried(self):
        self.assertEqual(self.upload(self.staff_a, 'ok1.pdf').status_code, 201)
        bad = self.upload(self.staff_a, 'broken.pdf', b'<html>not a pdf')
        self.assertEqual(bad.status_code, 400)
        self.assertIn('file', bad.json())
        self.assertEqual(self.upload(self.staff_a, 'ok2.pdf').status_code, 201)
        self.assertEqual(Document.objects.filter(case=self.case_a).count(), 2)  # 失敗は他を消さない
        # 失敗したファイルだけ（修正して）再試行する
        self.assertEqual(self.upload(self.staff_a, 'broken.pdf', PDF).status_code, 201)
        self.assertEqual(sorted(Document.objects.filter(case=self.case_a).values_list('file_name', flat=True)),
                         ['broken.pdf', 'ok1.pdf', 'ok2.pdf'])

    @override_settings(DOCUMENT_BATCH_MAX_FILES=3, DOCUMENT_BATCH_MAX_TOTAL_BYTES=1000, DOCUMENT_MAX_UPLOAD_BYTES=600)
    def test_limits_count_single_size_and_total(self):
        too_many = self.check(self.staff_a, [{'name': f'{i}.pdf', 'size': 10} for i in range(4)])
        self.assertEqual(too_many.status_code, 400)
        self.assertIn('3 件まで', too_many.json()['errors'][0])
        total = self.check(self.staff_a, [{'name': 'a.pdf', 'size': 500}, {'name': 'b.pdf', 'size': 501}])
        self.assertEqual(total.status_code, 400)
        self.assertIn('合計サイズ', total.json()['errors'][0])
        single = self.check(self.staff_a, [{'name': 'a.pdf', 'size': 601}, {'name': 'b.pdf', 'size': 10}])
        self.assertEqual(single.status_code, 200)  # 1 件だけの問題は一覧全体を止めない
        rows = single.json()['files']
        self.assertIn('大きすぎます', rows[0]['problem'])
        self.assertIsNone(rows[1]['problem'])
        # 実際の登録でも 1 件ごとの上限を後端が確認する
        self.assertEqual(self.upload(self.staff_a, 'big.pdf', PDF + b'0' * 700).status_code, 400)
        self.assertTrue(AuditLog.objects.filter(action='document_batch_upload_rejected').exists())

    def test_dangerous_and_invalid_file_names_are_rejected(self):
        names = ['../etc/passwd.pdf', 'a\\b.pdf', 'tab\tname.pdf', 'CON.pdf', 'nul.txt', 'com1.backup.pdf', '.pdf', '...',
                 'x' * 201 + '.pdf', 'tool.exe', 'noext', '']
        rows = self.check(self.staff_a, [{'name': n, 'size': 10} for n in names]).json()['files']
        self.assertEqual([n for n, row in zip(names, rows) if row['problem'] is None], [])
        self.assertIsNone(filename_problem('在留カード（表）.pdf'))
        self.assertIsNone(filename_problem('report.v2.final.pdf'))
        # 実際の登録：Windows 予約名・制御文字
        self.assertEqual(self.upload(self.staff_a, 'CON.pdf').status_code, 400)
        self.assertEqual(self.upload(self.staff_a, '.pdf').status_code, 400)
        self.assertIn('制御文字', validate_upload(SimpleUploadedFile('a\x07b.pdf', PDF)))
        self.assertFalse(Document.objects.exists())

    def test_permissions_for_check_and_upload(self):
        manifest = [{'name': 'a.pdf', 'size': 10}]
        self.assertEqual(self.check(self.staff_b, manifest).status_code, 404)   # 見えない案件
        self.assertEqual(self.check(self.jiao, manifest).status_code, 403)      # 見えるが書けない
        self.assertEqual(self.upload(self.staff_b, 'a.pdf').status_code, 403)  # 既存の単一登録 API の挙動のまま
        self.assertEqual(self.upload(self.jiao, 'a.pdf').status_code, 403)
        self.assertFalse(Document.objects.exists())
        self.client.force_login(self.staff_a)
        policy = self.client.get('/api/documents/upload-policy/').json()
        self.assertEqual((policy['batch_max_files'], policy['max_file_bytes']), (20, 20 * 1024 * 1024))
        self.assertIn('.pdf', policy['allowed_extensions'])


class ZipDownloadTests(DocumentBatchFixture):
    legacy_names = True

    def make_doc(self, name, category='other', case=None, content=PDF, user=None):
        response = self.upload(user or self.staff_a, name, content, case=case, category=category)
        self.assertEqual(response.status_code, 201, response.content)
        return Document.objects.get(pk=response.json()['id'])

    def test_selected_files_keep_category_folders_and_stable_duplicate_names(self):
        first = self.make_doc('在留カード.pdf', 'residence')
        second = self.make_doc('在留カード.pdf', 'residence')
        third = self.make_doc('在留カード.PDF', 'residence')  # 大文字小文字だけ違う名前も重複扱い
        other_folder = self.make_doc('在留カード.pdf', 'identity')
        response = self.zip(self.staff_a, ids=[third.pk, first.pk, second.pk, other_folder.pk])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertEqual((response['X-Zip-Included'], response['X-Zip-Skipped']), ('4', '0'))
        names = self.read_zip(response).namelist()
        self.assertEqual(sorted(names), sorted([
            '在留関係/在留カード.pdf', f'在留関係/在留カード (ID {second.pk}).pdf', f'在留関係/在留カード (ID {third.pk}).PDF',
            '本人確認書類/在留カード.pdf', 'ダウンロード結果.txt',
        ]))
        # 選び方が変わっても、同じファイルは同じ名前（元の名前は案件全体で ID 最小の first だけ）
        again = self.read_zip(self.zip(self.staff_a, ids=[second.pk, third.pk])).namelist()
        self.assertEqual(sorted(n for n in again if n.endswith(('.pdf', '.PDF'))),
                         sorted([f'在留関係/在留カード (ID {second.pk}).pdf', f'在留関係/在留カード (ID {third.pk}).PDF']))
        only_second = self.read_zip(self.zip(self.staff_a, ids=[second.pk])).namelist()
        self.assertIn(f'在留関係/在留カード (ID {second.pk}).pdf', only_second)  # 単独で選んでも名前は変わらない
        all_files = self.read_zip(self.zip(self.staff_a, all=True)).namelist()
        self.assertEqual(sorted(all_files), sorted(names))

    def test_names_do_not_depend_on_selection_or_archive_state(self):
        first = self.make_doc('写し.pdf')
        second = self.make_doc('写し.pdf')
        Document.objects.filter(pk=first.pk).update(is_archived=True)  # 最小 ID がアーカイブ済みでも元の名前は first のもの
        for body in ({'ids': [second.pk]}, {'all': True}, {'ids': [first.pk, second.pk]}):
            names = self.read_zip(self.zip(self.staff_a, **body)).namelist()
            self.assertIn(f'その他/写し (ID {second.pk}).pdf', names, body)
        self.assertNotIn('その他/写し.pdf', self.read_zip(self.zip(self.staff_a, all=True)).namelist())  # all は未アーカイブだけ

    def test_generated_name_never_collides_with_a_real_file_name(self):
        first = self.make_doc('写し.pdf')
        second = self.make_doc('写し.pdf')
        literal = self.make_doc('写し.pdf')
        # 実在のファイル名が、second に付くはずの「写し (ID n).pdf」と同じ（特殊な場合）
        Document.objects.filter(pk=literal.pk).update(file_name=f'写し (ID {second.pk}).pdf')
        expected = {
            first.pk: 'その他/写し.pdf',
            literal.pk: f'その他/写し (ID {second.pk}).pdf',   # 元の名前は先に確保される
            second.pk: f'その他/写し (ID {second.pk}-2).pdf',  # 重なるので連番
        }
        names = [n for n in self.read_zip(self.zip(self.staff_a, all=True)).namelist() if n.endswith('.pdf')]
        self.assertEqual(sorted(names), sorted(expected.values()))
        for ids in ([second.pk], [literal.pk], [second.pk, literal.pk]):
            selected = [n for n in self.read_zip(self.zip(self.staff_a, ids=ids)).namelist() if n.endswith('.pdf')]
            self.assertEqual(sorted(selected), sorted(expected[pk] for pk in ids), ids)

    def test_dangerous_stored_names_are_sanitized(self):
        doc = self.make_doc('report.pdf')
        Document.objects.filter(pk=doc.pk).update(file_name='../../etc/pas:swd*.pdf')
        names = self.read_zip(self.zip(self.staff_a, ids=[doc.pk])).namelist()
        self.assertIn('その他/pas_swd_.pdf', names)
        self.assertTrue(all('..' not in name and not name.startswith('/') for name in names))
        self.assertEqual(safe_component('..', 'fallback.pdf'), 'fallback.pdf')
        self.assertEqual(safe_component('a\x00b/c.pdf', 'x'), 'c.pdf')

    def test_all_files_of_case_excludes_archived_and_other_cases(self):
        kept = self.make_doc('a.pdf')
        archived = self.make_doc('b.pdf')
        Document.objects.filter(pk=archived.pk).update(is_archived=True)
        self.make_doc('other.pdf', case=self.case_b, user=self.staff_b)
        archive = self.read_zip(self.zip(self.staff_a, all=True))
        self.assertEqual(sorted(archive.namelist()), ['その他/a.pdf', 'ダウンロード結果.txt'])
        self.assertEqual(archive.read('その他/a.pdf'), PDF)
        log = AuditLog.objects.get(action='document_zip_download')
        self.assertEqual((log.extra['case_id'], log.extra['mode'], log.extra['included'], log.extra['skipped']),
                         (self.case_a.pk, 'all', 1, 0))
        self.assertEqual(log.extra['document_ids'], [kept.pk])

    def test_unauthorized_and_foreign_files_never_enter_the_zip(self):
        mine = self.make_doc('mine.pdf')
        foreign = self.make_doc('secret.pdf', case=self.case_b, user=self.staff_b)
        missing = self.make_doc('lost.pdf')
        missing.file.storage.delete(missing.file.name)
        response = self.zip(self.staff_a, ids=[mine.pk, foreign.pk, missing.pk, 999999])
        self.assertEqual(response.status_code, 200)
        archive = self.read_zip(response)
        self.assertEqual([n for n in archive.namelist() if n.endswith('.pdf')], ['その他/mine.pdf'])
        report = archive.read('ダウンロード結果.txt').decode('utf-8')
        self.assertNotIn('secret', report)  # 見えないファイルの名前は書かない
        self.assertIn('lost.pdf', report)
        log = AuditLog.objects.get(action='document_zip_download')
        self.assertEqual(log.extra['skipped_reasons'], {'not_found': 2, 'file_missing': 1})
        # li（全件ダウンロード権限）が case_a を ZIP にするとき、他案件のファイルは「別の案件」として除く
        response = self.zip(self.li, ids=[mine.pk, foreign.pk])
        self.assertEqual(response['X-Zip-Skipped'], '1')
        self.assertNotIn('その他/secret.pdf', self.read_zip(response).namelist())

    def test_permissions_and_nothing_to_download(self):
        doc = self.make_doc('a.pdf')
        self.assertEqual(self.zip(self.staff_b, all=True).status_code, 404)  # 見えない案件
        refused = self.zip(self.jiao, all=True)  # 見えるがダウンロード権限なし
        self.assertEqual(refused.status_code, 400)
        self.assertEqual(refused.json()['code'], 'nothing_to_download')
        self.assertEqual(refused.json()['skipped'][0]['reason'], 'forbidden')
        self.assertTrue(AuditLog.objects.filter(action='document_zip_refused', extra__skipped=1).exists())
        self.assertEqual(self.zip(self.li, ids=[doc.pk]).status_code, 200)  # 全件ダウンロード権限
        self.assertEqual(self.zip(self.staff_a, ids=[]).status_code, 400)
        self.assertEqual(self.zip(self.staff_a, case=self.case_b, all=True).status_code, 404)
        empty = self.zip(self.li, case=self.case_b, all=True)
        self.assertEqual((empty.status_code, empty.json()['code']), (400, 'nothing_to_download'))

    def test_size_and_count_limits(self):
        docs = [self.make_doc(f'{i}.pdf') for i in range(3)]
        with override_settings(DOCUMENT_ZIP_MAX_FILES=2):
            response = self.zip(self.staff_a, all=True)
        self.assertEqual((response.status_code, response.json()['code']), (400, 'zip_too_many_files'))
        with override_settings(DOCUMENT_ZIP_MAX_TOTAL_BYTES=len(PDF) * 2):
            response = self.zip(self.staff_a, ids=[d.pk for d in docs])
        self.assertEqual((response.status_code, response.json()['code']), (400, 'zip_too_large'))
        self.assertFalse(AuditLog.objects.filter(action='document_zip_download').exists())

    def test_existing_single_file_download_and_preview_still_work(self):
        doc = self.make_doc('a.pdf')
        self.client.force_login(self.staff_a)
        download = self.client.get(f'/api/documents/{doc.pk}/download/')
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), PDF)
        self.assertEqual(self.client.get(f'/api/documents/{doc.pk}/preview/').status_code, 200)

    def test_plan_entries_order_is_independent_of_input_order(self):
        docs = [self.make_doc('x.pdf') for _ in range(3)]
        self.assertEqual(plan_entries(docs), plan_entries(list(reversed(docs))))
        # 名前を決める範囲（universe）を渡すと、選んだ部分集合でも全体のときと同じ名前になる
        whole = dict((d.pk, path) for d, path in plan_entries(docs))
        for subset in ([docs[1]], [docs[2]], [docs[1], docs[2]]):
            self.assertEqual(dict((d.pk, path) for d, path in plan_entries(subset, universe=docs)),
                             {d.pk: whole[d.pk] for d in subset})
