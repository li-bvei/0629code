"""受保護ダウンロード・プレビュー：権限（担当／他人／業務管理者／李）、監査、Range、
ファイル名エンコード、パストラバーサル、X-Accel-Redirect、公開 /media/ の不在。"""
import os
import tempfile

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.cases.models import Case, CaseApplicationCategory, CaseTypeMaster
from apps.customers.models import Customer
from apps.documents.models import Document
from apps.employees.models import Employee
from apps.common.test_isolation import safe_rmtree


class DocumentFixtureMixin:
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media, PROTECTED_MEDIA_X_ACCEL=False)
        self.override.enable()
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], employee_name='李', superuser=True)
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], employee_name='焦', superuser=True)
        self.staff_a = make_user('staff_a', roles=[STAFF], employee_name='A')
        self.staff_b = make_user('staff_b', roles=[STAFF], employee_name='B')
        case_type, _ = CaseTypeMaster.objects.update_or_create(code='dl', defaults={'name': 'DL種別', 'number_abbreviation': 'DL'})
        category, _ = CaseApplicationCategory.objects.update_or_create(code='dl', defaults={'name': 'DL区分', 'number_abbreviation': 'DL'})
        customer = Customer.objects.create(name='顧客', birth_date='1990-01-01')
        self.case_a = Case.objects.create(
            case_type='x', case_type_master=case_type, application_category=category, status=Case.STATUS_OPEN,
            customer=customer, responsible_employee=Employee.objects.get(user=self.staff_a),
        )
        self.pdf = self._document('在留カード写し.pdf', b'%PDF-1.4 test')
        self.txt = self._document('メモ.txt', b'hello world')

    def tearDown(self):
        self.override.disable()
        safe_rmtree(self.media)

    def _document(self, name, content):
        doc = Document(case=self.case_a, title=name, file_name=name, file_size=len(content), file_path='')
        doc.file.save(name, ContentFile(content), save=True)
        return doc

    def fetch(self, user, doc, kind='download', **extra):
        self.client.logout()
        if user is not None:
            self.client.force_login(user)
        return self.client.get(f'/api/documents/{doc.id}/{kind}/', **extra)

    def body(self, response):
        return b''.join(response.streaming_content) if response.streaming else response.content


class DocumentDownloadTests(DocumentFixtureMixin, TestCase):
    def test_anonymous_rejected(self):
        self.assertIn(self.fetch(None, self.pdf).status_code, (401, 403))

    def test_assignee_downloads_with_audit(self):
        response = self.fetch(self.staff_a, self.pdf)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.body(response), b'%PDF-1.4 test')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn("filename*=UTF-8''%E5%9C%A8%E7%95%99", response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        actions = list(AuditLog.objects.filter(user=self.staff_a, module='documents').values_list('action', flat=True))
        self.assertIn('download_authorized', actions)
        self.assertIn('download_started', actions)
        self.assertNotIn('download_completed', actions)

    def test_other_staff_404_and_business_admin_403_are_denied_in_audit(self):
        self.assertEqual(self.fetch(self.staff_b, self.pdf).status_code, 404)
        self.assertEqual(self.fetch(self.jiao, self.pdf).status_code, 403)
        denied = AuditLog.objects.filter(action='download_denied', result='denied')
        self.assertEqual(set(denied.values_list('user__username', flat=True)), {'staff_b', 'jiao_like'})

    def test_li_downloads_out_of_scope(self):
        response = self.fetch(self.li, self.pdf)
        self.assertEqual(response.status_code, 200)
        log = AuditLog.objects.get(action='download_authorized', user=self.li)
        self.assertEqual(log.via_permission, 'documents.document_download_all')

    def test_preview_inline_only_for_whitelisted_types(self):
        response = self.fetch(self.staff_a, self.pdf, kind='preview')
        self.assertTrue(response['Content-Disposition'].startswith('inline;'))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        response = self.fetch(self.staff_a, self.txt, kind='preview')
        self.assertTrue(response['Content-Disposition'].startswith('attachment;'))
        self.assertEqual(response['Content-Type'], 'application/octet-stream')

    def test_range_continuation_does_not_duplicate_audit(self):
        self.fetch(self.staff_a, self.pdf)
        self.fetch(self.staff_a, self.pdf, HTTP_RANGE='bytes=5-')
        self.assertEqual(AuditLog.objects.filter(action='download_started', user=self.staff_a).count(), 1)

    def test_path_traversal_and_missing_file_are_rejected(self):
        secret = os.path.join(self.media, 'secret.txt')
        with open(secret, 'w') as fh:
            fh.write('secret')
        Document.objects.filter(pk=self.txt.pk).update(file='case_documents/../secret.txt')
        self.txt.refresh_from_db()
        self.assertEqual(self.fetch(self.staff_a, self.txt).status_code, 404)
        self.assertTrue(AuditLog.objects.filter(action='download_error', object_id=str(self.txt.pk)).exists())
        os.symlink(secret, os.path.join(self.media, 'case_documents', 'link.txt'))
        Document.objects.filter(pk=self.txt.pk).update(file='case_documents/link.txt')
        self.assertEqual(self.fetch(self.staff_a, self.txt).status_code, 404)
        Document.objects.filter(pk=self.txt.pk).update(file='case_documents/none.txt')
        self.assertEqual(self.fetch(self.staff_a, self.txt).status_code, 404)

    def test_x_accel_redirect_mode(self):
        with override_settings(PROTECTED_MEDIA_X_ACCEL=True):
            response = self.fetch(self.staff_a, self.pdf)
        self.assertEqual(response.status_code, 200)
        from urllib.parse import quote

        # nginx は X-Accel-Redirect の %xx を復号して internal location に渡す。
        self.assertEqual(response['X-Accel-Redirect'], '/_protected_media/' + quote(self.pdf.file.name, safe='/'))
        self.assertEqual(response.content, b'')

    def test_serializer_never_exposes_public_media_url(self):
        self.client.force_login(self.staff_a)
        data = self.client.get(f'/api/documents/{self.pdf.id}/').json()
        self.assertNotIn('/media/', data['file_url'])
        self.assertNotIn('/media/', data['file'])
        self.assertTrue(data['file_url'].endswith(f'/api/documents/{self.pdf.id}/download/'))
        self.assertTrue(data['preview_url'].endswith(f'/api/documents/{self.pdf.id}/preview/'))

    def test_public_media_path_is_not_routed(self):
        self.client.force_login(self.li)
        self.assertEqual(self.client.get('/media/' + self.pdf.file.name).status_code, 404)

    def test_upload_and_delete_are_audited_and_scoped(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.staff_b)
        response = self.client.post('/api/documents/', {
            'case': self.case_a.id, 'title': 'x', 'content_label': '合成資料', 'file': SimpleUploadedFile('x.txt', b'x'),
        })
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.staff_a)
        response = self.client.post('/api/documents/', {
            'case': self.case_a.id, 'title': 'x', 'content_label': '合成資料', 'file': SimpleUploadedFile('x.txt', b'x'),
        })
        self.assertEqual(response.status_code, 201, response.content)
        doc_id = response.json()['id']
        self.assertTrue(AuditLog.objects.filter(action='document_upload', object_id=str(doc_id)).exists())
        self.assertEqual(self.client.delete(f'/api/documents/{doc_id}/').status_code, 204)
        self.assertTrue(AuditLog.objects.filter(action='document_delete', object_id=str(doc_id)).exists())


class MediaInventoryCommandTests(DocumentFixtureMixin, TestCase):
    def test_inventory_reports_without_changing_anything(self):
        from io import StringIO

        from django.core.management import call_command

        from apps.timelines.models import Timeline

        orphan = os.path.join(self.media, 'case_documents', 'orphan.bin')
        with open(orphan, 'wb') as fh:
            fh.write(b'x')
        Timeline.objects.create(case=self.case_a, title='旧リンク', content='https://example.com/media/case_documents/a.pdf')
        out = StringIO()
        call_command('inventory_media_references', stdout=out)
        text = out.getvalue()
        self.assertIn('実ファイル数: 3', text)
        self.assertIn('Document に紐付かないファイル（削除しない・報告のみ）: 1 件', text)
        self.assertIn('timelines.Timeline.content: 1 件', text)
        self.assertTrue(os.path.exists(orphan))
