"""全体検索：権限範囲だけ、範囲外の顧客は最小識別情報、機微項目・パス・金額は返さない、監査に検索語を残さない。"""
import json

from django.test import TestCase

from apps.accounting.tests_links import AccountingFixture
from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.documents.models import Document
from apps.real_estate.models import RealEstateTransaction

URL = '/api/search/'
FORBIDDEN_KEYS = {'my_number', 'birth_date', 'phone', 'email', 'address', 'file', 'file_path', 'file_url', 'amount',
                  'passport_number', 'residence_card_number'}


def keys(obj):
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in keys(v)}
    return set()


class GlobalSearchTests(AccountingFixture, TestCase):
    def search(self, user, q):
        self.client.force_login(user)
        response = self.client.get(URL, {'q': q})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def group(self, body, name):
        return next((g['items'] for g in body['groups'] if g['type'] == name), None)

    def test_scope_and_minimal_representation(self):
        Customer.objects.filter(pk=self.other_customer.pk).update(my_number='123456789012', phone='090-0000-0000')
        body = self.search(self.staff_a, '会計')
        self.assertEqual([c['title'] for c in self.group(body, 'case')], [self.case_a.case_number])
        customer = self.group(body, 'customer')[0]
        self.assertEqual((customer['title'], customer['access_level'], customer['can_open']), ('会計顧客', 'full', True))
        self.assertEqual(self.group(body, 'company')[0]['title'], '会計会社')
        # 範囲外の顧客：名前は出るが開けない（最小識別情報のみ）、担当外の案件は出ない
        body = self.search(self.staff_a, '他担当')
        other = self.group(body, 'customer')[0]
        self.assertEqual((other['access_level'], other['can_open'], other['url']), ('minimal', False, ''))
        self.assertEqual(self.group(body, 'case'), [])
        self.assertFalse(keys(body) & FORBIDDEN_KEYS)
        # 機微項目では検索できない
        self.assertEqual(self.group(self.search(self.staff_a, '123456789012'), 'customer'), [])
        self.assertEqual(self.group(self.search(self.staff_a, '090-0000'), 'customer'), [])

    def test_documents_and_real_estate_respect_scope(self):
        Document.objects.create(case=self.case_a, title='在職証明書テスト', file_name='secret_path.pdf')
        RealEstateTransaction.objects.create(party_name='検索 借主', property_name='検索ハイツ',
                                             responsible_employee=self.case_a.responsible_employee)
        body = self.search(self.staff_a, '検索')
        self.assertEqual(len(self.group(body, 'real_estate')), 1)
        docs = self.group(self.search(self.staff_a, '在職証明'), 'document')
        self.assertEqual(docs[0]['url'], f'/cases/{self.case_a.id}')
        self.assertNotIn('secret_path', json.dumps(docs, ensure_ascii=False))
        self.assertEqual(self.group(self.search(self.staff_b, '在職証明'), 'document'), [])
        self.assertEqual(self.group(self.search(self.staff_b, '検索'), 'real_estate'), [])

    def test_audit_without_keyword_and_short_query(self):
        self.assertTrue(self.search(self.staff_a, '会')['query_too_short'])
        self.search(self.staff_a, '他担当顧客')
        log = AuditLog.objects.get(module='search')
        self.assertEqual(log.extra['query_length'], 5)
        self.assertEqual(log.extra['minimal_results'], 1)
        self.assertNotIn('他担当', json.dumps({'extra': log.extra, 'reason': log.reason, 'changes': log.changes,
                                                'repr': log.object_repr}, ensure_ascii=False))
        # 顧客・会社を含まない検索は監査に残さない
        self.search(self.staff_a, 'ZZZ-none')
        self.assertEqual(AuditLog.objects.filter(module='search').count(), 1)
