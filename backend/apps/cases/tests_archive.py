"""P2 案件アーカイブ：理由・実行者・Timeline・AuditLog、アーカイブ中は通常変更不可、復元で元どおり。削除はしない。"""
from django.test import TestCase

from apps.accounting.tests_links import AccountingFixture
from apps.audit.models import AuditLog
from apps.cases.models import Case, CaseChecklistItem
from apps.timelines.models import Timeline


class CaseArchiveTests(AccountingFixture, TestCase):
    def post(self, user, url, body=None):
        self.client.force_login(user)
        return self.client.post(url, body or {}, content_type='application/json')

    def url(self, suffix=''):
        return f'/api/cases/{self.case_a.id}/{suffix}'

    def archive(self, user=None, **body):
        return self.post(user or self.staff_a, self.url('archive/'), {'reason': '保管期間に移行', **body})

    def test_archive_requires_reason_and_confirmation(self):
        self.assertEqual(self.post(self.staff_a, self.url('archive/'), {'reason': ' '}).status_code, 400)
        response = self.archive()  # 進捗が完了していない → 確認が必要
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json().get('requires_force'))
        self.assertEqual(self.archive(force=True).status_code, 200)
        case = Case.objects.get(pk=self.case_a.pk)
        self.assertEqual(case.registration_status, Case.REGISTRATION_STATUS_ARCHIVED)
        self.assertEqual((case.archived_by, case.archive_reason), (self.staff_a, '保管期間に移行'))
        self.assertIsNotNone(case.archived_at)
        self.assertTrue(Timeline.objects.filter(case=case, event_type=Timeline.EVENT_CASE_ARCHIVED).exists())
        self.assertTrue(AuditLog.objects.filter(module='cases', action='case_archived', reason='保管期間に移行').exists())
        self.assertEqual(self.archive(force=True).status_code, 400)  # 二重アーカイブ不可

    def test_archived_case_is_read_only_until_restored(self):
        item = CaseChecklistItem.objects.create(case=self.case_a, name='在職証明書')
        self.archive(force=True)
        self.client.force_login(self.staff_a)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        patch = self.client.patch(self.url(), {'note': 'x'}, content_type='application/json')
        self.assertEqual(patch.status_code, 400)
        self.assertIn('復元', patch.json()['detail'])
        self.assertEqual(self.post(self.staff_a, self.url('change-status/'), {'new_status': 'applied'}).status_code, 400)
        created = self.post(self.staff_a, '/api/case-checklist-items/', {'case': self.case_a.id, 'name': '追加'})
        self.assertEqual(created.status_code, 403)
        edit = self.client.patch(f'/api/case-checklist-items/{item.id}/', {'name': '変更'}, content_type='application/json')
        self.assertEqual(edit.status_code, 403)
        # 担当外の職員はアーカイブも復元もできない（見えない）
        self.assertEqual(self.post(self.staff_b, self.url('restore/')).status_code, 404)
        # 復元：アーカイブ情報は空に戻り、経過と監査に旧値が残る
        restored = self.post(self.staff_a, self.url('restore/'), {'reason': '再申請のため'})
        self.assertEqual(restored.status_code, 200, restored.content)
        case = Case.objects.get(pk=self.case_a.pk)
        self.assertEqual(case.registration_status, Case.REGISTRATION_STATUS_ACTIVE)
        self.assertEqual((case.archived_at, case.archived_by, case.archive_reason), (None, None, ''))
        self.assertEqual(case.restored_by, self.staff_a)
        self.assertTrue(Timeline.objects.filter(case=case, event_type=Timeline.EVENT_CASE_RESTORED,
                                                content__contains='保管期間に移行').exists())
        log = AuditLog.objects.get(action='case_restored')
        self.assertEqual(log.extra['previous_archive']['archive_reason'], '保管期間に移行')
        self.assertEqual(self.client.patch(self.url(), {'note': '再開'}, content_type='application/json').status_code, 200)
        self.assertTrue(CaseChecklistItem.objects.filter(pk=item.pk).exists())
        self.assertEqual(self.post(self.staff_a, self.url('restore/')).status_code, 400)

    def test_business_admin_cannot_archive_others_case(self):
        self.assertEqual(self.archive(user=self.jiao, force=True).status_code, 403)
