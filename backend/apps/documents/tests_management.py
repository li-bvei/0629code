"""P2 文件管理：アップロード検査・メタデータ・分類・Checklist 関連・アーカイブ/復元・差し替え履歴・受保護ダウンロード維持。"""
import hashlib
import os
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart

from apps.audit.models import AuditLog
from apps.authentication.roles import ACCOUNTING_ADMIN, BUSINESS_ADMIN, EXPENSE_VIEWER, STAFF, SYSTEM_ADMIN
from apps.authentication.testing import make_user
from apps.cases.models import Case, CaseApplicationCategory, CaseChecklistItem, CaseTypeMaster
from apps.customers.models import Customer
from apps.documents.models import Document, DocumentReplacement
from apps.employees.models import Employee
from apps.timelines.models import Timeline

PDF = b'%PDF-1.4 test document'


class DocumentManagementTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        override = override_settings(MEDIA_ROOT=self.media, PROTECTED_MEDIA_X_ACCEL=False)
        override.enable()
        self.addCleanup(override.disable)
        self.li = make_user('li', roles=[SYSTEM_ADMIN, ACCOUNTING_ADMIN, BUSINESS_ADMIN], superuser=True, employee_name='李')
        self.jiao = make_user('jiao_like', roles=[BUSINESS_ADMIN, EXPENSE_VIEWER], superuser=True, employee_name='焦')
        self.staff_a = make_user('staff_a', roles=[STAFF], employee_name='A')
        self.staff_b = make_user('staff_b', roles=[STAFF], employee_name='B')
        ct, _ = CaseTypeMaster.objects.update_or_create(code='dm', defaults={'name': '文書試験種別', 'number_abbreviation': '文試'})
        cat, _ = CaseApplicationCategory.objects.update_or_create(code='dm', defaults={'name': '文書試験区分', 'number_abbreviation': '文区'})
        customer = Customer.objects.create(name='文書顧客', birth_date='1990-01-01')
        self.case_a = Case.objects.create(case_type='x', case_type_master=ct, application_category=cat, status=Case.STATUS_OPEN,
                                          customer=customer, responsible_employee=Employee.objects.get(user=self.staff_a))
        self.other_case = Case.objects.create(case_type='x', case_type_master=ct, application_category=cat, status=Case.STATUS_OPEN,
                                              customer=customer, responsible_employee=Employee.objects.get(user=self.staff_a))
        self.item = CaseChecklistItem.objects.create(case=self.case_a, name='在留カード写し')

    def upload(self, user, name='在留カード.pdf', content=PDF, **extra):
        self.client.force_login(user)
        body = {'case': self.case_a.id, 'title': '在留カード', 'category': 'residence',
                'file': SimpleUploadedFile(name, content, content_type='application/x-evil'), **extra}
        return self.client.post('/api/documents/', body)

    def test_upload_records_metadata_uuid_name_and_uploader(self):
        response = self.upload(self.staff_a)
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        doc = Document.objects.get(pk=data['id'])
        self.assertEqual(doc.file_name, '在留カード.pdf')
        self.assertEqual(doc.sha256, hashlib.sha256(PDF).hexdigest())
        self.assertEqual(doc.file_size, len(PDF))
        self.assertEqual(doc.content_type, 'application/pdf')  # ブラウザ申告値ではなく拡張子から推定
        self.assertEqual(doc.uploaded_by, self.staff_a)
        self.assertEqual(data['category_display'], '在留関係')
        self.assertNotIn('在留', os.path.basename(doc.file.name))  # 保存名は UUID
        self.assertTrue(doc.file.name.startswith('case_documents/'))
        self.assertNotIn('/media/', data['file_url'])

    def test_upload_rejects_disallowed_type_signature_mismatch_executable_and_empty(self):
        for name, content in (('tool.exe', b'MZ\x90\x00'), ('script.sh', b'#!/bin/sh'),
                              ('fake.pdf', b'<html>not pdf'), ('evil.txt', b'MZ\x90\x00binary'), ('empty.pdf', b'')):
            response = self.upload(self.staff_a, name=name, content=content)
            self.assertEqual(response.status_code, 400, name)
            self.assertIn('file', response.json())
        with override_settings(DOCUMENT_MAX_UPLOAD_BYTES=10):
            self.assertEqual(self.upload(self.staff_a).status_code, 400)
        self.assertEqual(Document.objects.count(), 0)

    def test_checklist_link_at_upload_same_case_only(self):
        response = self.upload(self.staff_a, checklist_item=self.item.id)
        self.assertEqual(response.status_code, 201, response.content)
        self.item.refresh_from_db()
        self.assertEqual(self.item.document_id, response.json()['id'])
        self.assertTrue(AuditLog.objects.filter(action='document_checklist_linked').exists())
        other_item = CaseChecklistItem.objects.create(case=self.other_case, name='別案件')
        self.assertEqual(self.upload(self.staff_a, checklist_item=other_item.id).status_code, 400)
        detail = self.client.get(f"/api/documents/{response.json()['id']}/").json()
        self.assertEqual(detail['checklist_items'][0]['name'], '在留カード写し')

    def test_replace_keeps_previous_file_and_history(self):
        doc_id = self.upload(self.staff_a).json()['id']
        old_name = Document.objects.get(pk=doc_id).file.name
        body = encode_multipart(BOUNDARY, {
            'file': SimpleUploadedFile('新しい.pdf', b'%PDF-1.7 new'), 'replace_reason': '最新版を受領',
        })
        response = self.client.patch(f'/api/documents/{doc_id}/', body, content_type=MULTIPART_CONTENT)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['replacement_count'], 1)
        self.assertTrue(os.path.exists(os.path.join(self.media, old_name)))  # 旧ファイルは削除しない
        history = self.client.get(f'/api/documents/{doc_id}/history/').json()
        self.assertEqual(history[0]['previous_file_name'], '在留カード.pdf')
        self.assertEqual(history[0]['reason'], '最新版を受領')
        self.assertNotIn('previous_file', history[0])
        self.assertTrue(AuditLog.objects.filter(action='document_replace').exists())
        self.assertEqual(DocumentReplacement.objects.get().replaced_by, self.staff_a)

    def test_archive_and_restore(self):
        doc_id = self.upload(self.staff_a).json()['id']
        response = self.client.post(f'/api/documents/{doc_id}/archive/', {'reason': '古い版'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_archived'])
        self.assertEqual(self.client.get(f'/api/documents/?case={self.case_a.id}').json()['count'], 0)
        self.assertEqual(self.client.get(f'/api/documents/?case={self.case_a.id}&archived=only').json()['count'], 1)
        # アーカイブ後も受保護ダウンロードは可能（ファイルは残る）
        self.assertEqual(self.client.get(f'/api/documents/{doc_id}/download/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/documents/{doc_id}/archive/').status_code, 400)
        response = self.client.post(f'/api/documents/{doc_id}/restore/')
        self.assertFalse(response.json()['is_archived'])
        events = set(Timeline.objects.filter(case=self.case_a).values_list('event_type', flat=True))
        self.assertTrue({Timeline.EVENT_DOCUMENT_ARCHIVED, Timeline.EVENT_DOCUMENT_RESTORED} <= events)
        self.assertTrue(AuditLog.objects.filter(action='document_archive', reason='古い版').exists())
        self.assertTrue(AuditLog.objects.filter(action='document_restore').exists())

    def test_permissions_follow_case(self):
        doc_id = self.upload(self.staff_a).json()['id']
        self.client.force_login(self.staff_b)
        self.assertEqual(self.client.post(f'/api/documents/{doc_id}/archive/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/documents/{doc_id}/history/').status_code, 404)
        self.assertEqual(self.upload(self.staff_b).status_code, 403)
        self.client.force_login(self.jiao)
        self.assertEqual(self.client.get(f'/api/documents/{doc_id}/history/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/documents/{doc_id}/archive/').status_code, 403)
        self.assertEqual(self.client.get(f'/api/documents/{doc_id}/download/').status_code, 403)

    def test_category_filter_and_uploaded_by_not_writable(self):
        self.upload(self.staff_a, uploaded_by=self.li.id)
        self.upload(self.staff_a, category='certificate', title='課税証明')
        self.assertEqual(Document.objects.filter(uploaded_by=self.li).count(), 0)
        data = self.client.get(f'/api/documents/?case={self.case_a.id}&category=certificate').json()
        self.assertEqual([d['title'] for d in data['results']], ['課税証明'])
