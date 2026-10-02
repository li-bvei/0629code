"""家族の編集画面から、関連付いている人物（Customer）の生年月日・在留情報などを直接修正できること、
およびその入口で他担当の顧客を書き換えられないこと。"""
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.customers.models import Customer, FamilyMember

from .test_case_party_access import AccessFixtureMixin


class FamilyPersonEditTests(AccessFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        # 顧客A（staff_a 担当）の配偶者：案件を持たない人物として登録済み
        self.spouse = Customer.objects.create(name='配偶者', birth_date='1991-03-03', residence_card_no='SP11112222AA',
                                              my_number='999988887777')
        self.link = FamilyMember.objects.create(customer=self.cust_a, family_customer=self.spouse, relationship='spouse')
        self.url = f'/api/family-members/{self.link.id}/'

    def patch(self, user, body, url=None):
        self.as_user(user)
        return self.client.patch(url or self.url, body, content_type='application/json')

    def base(self, **person):
        return {'customer': self.cust_a.id, 'family_customer': self.spouse.id, 'relationship': 'spouse', 'person': person}

    def test_responsible_staff_can_fix_birth_date_and_residence_info_from_family_card(self):
        response = self.patch(self.staff_a, self.base(birth_date='1991-03-04', residence_status='家族滞在',
                                                      residence_card_no='SP99990000BB', residence_expiry='2027-05-01',
                                                      passport_no='P7654321', passport_expiry='2030-01-01'))
        self.assertEqual(response.status_code, 200, response.content)
        self.spouse.refresh_from_db()
        self.assertEqual((str(self.spouse.birth_date), self.spouse.residence_status, self.spouse.residence_card_no,
                          str(self.spouse.residence_expiry), self.spouse.passport_no),
                         ('1991-03-04', '家族滞在', 'SP99990000BB', '2027-05-01', 'P7654321'))
        self.assertEqual(self.spouse.name, '配偶者')            # 送っていない項目は変わらない
        self.assertEqual(self.spouse.my_number, '999988887777')  # 空欄・未指定で消えない
        body = response.json()
        self.assertEqual((body['birth_date'], body['residence_card_no']), ('1991-03-04', 'SP99990000BB'))
        self.assertNotIn('my_number', body)
        audit = AuditLog.objects.get(action='family_person_updated')
        self.assertEqual((audit.user, audit.object_id), (self.staff_a, str(self.spouse.pk)))
        self.assertEqual(audit.changes['birth_date'], {'from': '1991-03-03', 'to': '1991-03-04'})
        self.assertEqual(audit.changes['residence_card_no'], {'changed': True})  # 証件番号の値は監査に残さない

    def test_blank_my_number_keeps_existing_value_and_relationship_only_edit_still_works(self):
        self.assertEqual(self.patch(self.staff_a, self.base(my_number='', nationality='中国')).status_code, 200)
        self.spouse.refresh_from_db()
        self.assertEqual((self.spouse.my_number, self.spouse.nationality), ('999988887777', '中国'))
        body = {'customer': self.cust_a.id, 'family_customer': self.spouse.id, 'relationship': 'other', 'note': '関係のみ'}
        self.assertEqual(self.patch(self.staff_a, body).status_code, 200)
        self.assertFalse(AuditLog.objects.filter(action='family_person_updated', changes__has_key='name').exists())

    def test_invalid_values_and_unknown_fields_are_rejected_with_field_errors(self):
        response = self.patch(self.staff_a, self.base(birth_date='1991-13-40'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('birth_date', response.json()['person'])
        self.assertEqual(self.patch(self.staff_a, self.base(name='')).status_code, 400)
        self.assertEqual(self.patch(self.staff_a, self.base(note='x', id=1)).status_code, 400)
        self.spouse.refresh_from_db()
        self.assertEqual((self.spouse.name, str(self.spouse.birth_date)), ('配偶者', '1991-03-03'))

    def test_person_cannot_be_edited_while_switching_to_another_customer_or_on_create(self):
        body = self.base(birth_date='1991-03-04')
        body['family_customer'] = self.cust_new.id
        self.assertEqual(self.patch(self.staff_a, body).status_code, 400)
        self.as_user(self.staff_a)
        created = self.client.post('/api/family-members/', {
            'customer': self.cust_a.id, 'family_customer': self.cust_new.id, 'relationship': 'child',
            'person': {'birth_date': '2000-01-01'}}, content_type='application/json')
        self.assertEqual(created.status_code, 400)
        self.assertEqual(str(Customer.objects.get(pk=self.cust_new.pk).birth_date), '1992-01-01')

    def test_other_staff_cannot_edit_through_someone_elses_customer(self):
        self.assertIn(self.patch(self.staff_b, self.base(birth_date='1991-03-04')).status_code, (403, 404))
        self.assertIn(self.patch(self.jiao, self.base(birth_date='1991-03-04')).status_code, (403, 404))
        self.spouse.refresh_from_db()
        self.assertEqual(str(self.spouse.birth_date), '1991-03-03')

    def test_family_link_is_not_a_way_to_rewrite_another_staffs_active_customer(self):
        # 顧客A の家族として、staff_b 担当の進行中案件を持つ 顧客B が関連付いている場合
        link = FamilyMember.objects.create(customer=self.cust_a, family_customer=self.cust_b, relationship='sibling')
        body = {'customer': self.cust_a.id, 'family_customer': self.cust_b.id, 'relationship': 'sibling',
                'person': {'birth_date': '1999-09-09'}}
        response = self.patch(self.staff_a, body, url=f'/api/family-members/{link.id}/')
        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn('他の担当者', response.json()['detail'])
        self.assertEqual(str(Customer.objects.get(pk=self.cust_b.pk).birth_date), '1991-01-01')
        # 関係だけの変更は従来どおりできる。李（case_change_all）は人物情報も修正できる。
        body.pop('person')
        self.assertEqual(self.patch(self.staff_a, {**body, 'note': '兄'}, url=f'/api/family-members/{link.id}/').status_code, 200)
        allowed = self.patch(self.li, {**body, 'person': {'birth_date': '1999-09-09'}}, url=f'/api/family-members/{link.id}/')
        self.assertEqual(allowed.status_code, 200, allowed.content)
        self.assertEqual(str(Customer.objects.get(pk=self.cust_b.pk).birth_date), '1999-09-09')
