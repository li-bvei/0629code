"""会社の従業員・代表者を「既存の顧客」から選ぶときの候補（/api/customers/?linkable=1）。

- 候補は 1 ページ目に固定されず、後端の検索で全件から探せる（件数 count も返る）。
- 候補は保存時の check_link と同じ条件（関連付けできる顧客だけ）。候補に出るものは保存でき、出ないものは 403。
- 既存の関連は、その後に関連付け不可になっても編集時に保持され、表示用の氏名（customer_name）が返る。
"""
from django.test import TestCase

from apps.authentication.roles import EXPENSE_VIEWER
from apps.authentication.testing import make_user
from apps.companies.models import Company, CompanyStaff
from apps.customers.models import Customer

from .test_case_party_access import AccessFixtureMixin

URL = '/api/customers/'


class CompanyStaffCandidateTests(AccessFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        # 案件の無い顧客を 25 人（既定の 1 ページ 20 件を超える）
        self.many = [Customer.objects.create(name=f'候補者{i:02d}', birth_date='1990-01-01') for i in range(1, 26)]

    def candidates(self, user, **params):
        self.as_user(user)
        response = self.client.get(URL, {'linkable': '1', **params})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def ids(self, data):
        return {row['id'] for row in data['results']}

    def test_more_than_one_page_can_be_searched_and_count_is_reported(self):
        first_page = self.candidates(self.staff_a)
        self.assertEqual(len(first_page['results']), 20)
        self.assertGreater(first_page['count'], 20)  # 画面は「ほかに N 件」と案内できる
        found = self.candidates(self.staff_a, search='候補者25')
        self.assertEqual([row['name'] for row in found['results']], ['候補者25'])
        self.assertNotIn(self.many[-1].id, self.ids(first_page))  # 1 ページ目に無い人も検索で見つかる
        self.assertEqual(self.candidates(self.staff_a, search='該当しない名前zzz')['count'], 0)

    def test_candidates_follow_the_same_rule_as_linking(self):
        a = self.candidates(self.staff_a, page_size=100)
        # cust_a：本人担当 → 可／cust_new：案件なし → 可／cust_b：他担当・未割当の進行中案件あり → 不可
        self.assertIn(self.cust_a.id, self.ids(self.candidates(self.staff_a, search='顧客A')))
        self.assertIn(self.cust_new.id, self.ids(self.candidates(self.staff_a, search='受付のみ')))
        self.assertNotIn(self.cust_b.id, self.ids(self.candidates(self.staff_a, search='顧客B')))
        self.assertTrue(a['count'] >= 27)
        # 保存時の判定と一致する：候補に出る顧客は関連付けでき、出ない顧客は 403
        self.as_user(self.staff_a)
        ok = self.client.post('/api/company-staff/', {'company': self.company_a.id, 'customer': self.cust_new.id,
                                                      'position': '社員'}, content_type='application/json')
        self.assertEqual(ok.status_code, 201, ok.content)
        other = Customer.objects.create(name='他担当の顧客', birth_date='1990-01-01')
        self._case(other, self.emp_b)  # staff_b 担当の進行中案件
        self.assertNotIn(other.id, self.ids(self.candidates(self.staff_a, search='他担当の顧客')))
        self.as_user(self.staff_a)
        denied = self.client.post('/api/company-staff/', {'company': self.company_a.id, 'customer': other.id,
                                                          'position': '社員'}, content_type='application/json')
        self.assertEqual(denied.status_code, 403)

    def test_other_users_scopes(self):
        # staff_b：自分の cust_b は可、staff_a 担当の cust_a は不可
        self.assertIn(self.cust_b.id, self.ids(self.candidates(self.staff_b, search='顧客B')))
        self.assertNotIn(self.cust_a.id, self.ids(self.candidates(self.staff_b, search='顧客A')))
        # 全件閲覧だけの業務管理者（焦）も、他担当の進行中案件がある顧客は関連付けできないので候補に出ない
        self.assertNotIn(self.cust_a.id, self.ids(self.candidates(self.jiao, search='顧客A')))
        # 担当者未関連の利用者：進行中案件のある顧客はすべて不可、案件の無い顧客だけ
        unlinked = self.candidates(self.unlinked, search='顧客')
        self.assertEqual(self.ids(unlinked) & {self.cust_a.id, self.cust_b.id}, set())
        # 明示権限 customer_link_all を持つ李は全員（is_superuser ではなく業務権限で判定）
        self.assertTrue({self.cust_a.id, self.cust_b.id} <= self.ids(self.candidates(self.li, search='顧客')))
        # 業務ロールの無い superuser は is_superuser では通らない（検索自体できない）
        self.as_user(self.su_only)
        self.assertEqual(self.client.get(URL, {'linkable': '1'}).status_code, 403)
        # 案件モジュールの権限が無い利用者も検索できない
        viewer = make_user('viewer_only', roles=[EXPENSE_VIEWER], employee_name='閲覧')
        self.as_user(viewer)
        self.assertEqual(self.client.get(URL, {'linkable': '1'}).status_code, 403)

    def test_existing_link_is_kept_and_shown_when_it_is_no_longer_linkable(self):
        # fixture：company_a の従業員に cust_b（staff_a から見て関連付け不可）が既に関連付いている
        staff = CompanyStaff.objects.get(company=self.company_a, customer=self.cust_b)
        self.assertNotIn(self.cust_b.id, self.ids(self.candidates(self.staff_a, search='顧客B')))
        self.as_user(self.staff_a)
        rows = self.rows(self.client.get('/api/company-staff/', {'company': self.company_a.id}))
        row = next(r for r in rows if r['id'] == staff.id)
        self.assertEqual((row['customer'], row['customer_name']), (self.cust_b.id, '顧客B'))  # 画面の初期表示に使う
        # 役職だけ変えて保存しても関連は消えない（変更していない関連は再判定しない）
        response = self.client.patch(f'/api/company-staff/{staff.id}/',
                                     {'company': self.company_a.id, 'customer': self.cust_b.id, 'position': '課長'},
                                     content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        staff.refresh_from_db()
        self.assertEqual((staff.customer_id, staff.position), (self.cust_b.id, '課長'))

    def test_company_create_and_edit_with_representative_from_candidates(self):
        self.as_user(self.staff_a)
        # 新規作成：1 ページ目に無い候補（候補者25）を代表者にできる
        created = self.client.post('/api/companies/', {'name': '候補テスト会社', 'representative_customer': self.many[-1].id},
                                   content_type='application/json')
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(Company.objects.get(pk=created.json()['id']).representative_customer_id, self.many[-1].id)
        # 編集：担当の会社（company_a）の代表者を候補から設定し、詳細で氏名が返る（編集時の初期表示）
        updated = self.client.patch(f'/api/companies/{self.company_a.id}/', {'representative_customer': self.many[-2].id},
                                    content_type='application/json')
        self.assertEqual(updated.status_code, 200, updated.content)
        detail = self.client.get(f'/api/companies/{self.company_a.id}/').json()
        self.assertEqual((detail['representative_customer'], detail['representative_customer_name']),
                         (self.many[-2].id, '候補者24'))
        # 代表者を変えずに他の項目だけ保存しても、代表者は消えない
        self.client.patch(f'/api/companies/{self.company_a.id}/', {'phone': '03-0000-0000'}, content_type='application/json')
        self.assertEqual(Company.objects.get(pk=self.company_a.id).representative_customer_id, self.many[-2].id)

    def test_without_linkable_the_existing_list_behaviour_is_unchanged(self):
        self.as_user(self.staff_a)
        data = self.client.get(URL, {'search': '顧客B'}).json()
        self.assertIn(self.cust_b.id, self.ids(data))  # 一覧・検索は従来どおり（範囲外は最小情報）
