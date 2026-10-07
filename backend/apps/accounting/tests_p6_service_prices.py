"""P6：サービス項目の基本 8 件（暫定価格）・価格の確定・暫定価格のまま帳票／受付に使う流れ。"""
import importlib
import json
from decimal import Decimal

from django.apps import apps as django_apps
from django.test import TestCase

from apps.accounting.models import ServiceItem
from apps.accounting.tests_service_items import ServiceItemFixture, grant
from apps.audit.models import AuditLog
from apps.authentication.testing import make_user
from apps.cases.models import Case

seed_migration = importlib.import_module('apps.accounting.migrations.0027_seed_provisional_service_items')
ITEMS = '/api/accounting/service-items/'
EXPECTED = {
    'work_visa_application': ('在留資格', '就労ビザ申請', 110000, 55000, 'gyousei', '件'),
    'permanent_residence': ('在留資格', '永住許可申請', 165000, 82500, 'gyousei', '件'),
    'company_dissolution': ('法人手続', '会社解散手続', 220000, 165000, 'judicial_scrivener', '件'),
    'tax_accounting': ('税務', '税理士業務', 110000, 88000, 'tax_accountant', '件'),
    'highly_skilled_application': ('在留資格', '高度専門職申請', 165000, 82500, 'gyousei', '件'),
    'highly_skilled_annual_support': ('顧問・支援', '高度専門職一年サポート', 330000, 264000, 'gyousei', '年'),
    'business_manager_renewal': ('在留資格', '経営・管理更新', 165000, 82500, 'gyousei', '件'),
    'translation': ('翻訳', '翻訳', 5500, 3300, '', '頁'),
}


class SeedTests(TestCase):
    def test_eight_provisional_items_with_stable_codes(self):
        items = {item.code: item for item in ServiceItem.objects.filter(code__in=EXPECTED)}
        self.assertEqual(set(items), set(EXPECTED))
        for code, (category, name, price, floor, professional, unit) in EXPECTED.items():
            item = items[code]
            self.assertEqual((item.category, item.name, item.default_price, item.floor_price), (category, name, price, floor))
            self.assertEqual((item.professional_type, item.unit, item.tax_category), (professional, unit, 'tax_10'))
            self.assertEqual((item.price_status, item.is_active), ('provisional', True))

    def test_rerun_is_idempotent_and_never_overwrites_edited_or_confirmed_prices(self):
        visa = ServiceItem.objects.get(code='work_visa_application')
        visa.default_price, visa.price_status = Decimal('120000'), 'confirmed'
        visa.save()
        translation = ServiceItem.objects.get(code='translation')
        translation.unit = ''  # 空になった項目だけは埋め直す
        translation.save()
        seed_migration.forward(django_apps, None)
        seed_migration.forward(django_apps, None)
        self.assertEqual(ServiceItem.objects.filter(code__in=EXPECTED).count(), 8)
        visa.refresh_from_db()
        translation.refresh_from_db()
        self.assertEqual((visa.default_price, visa.price_status), (Decimal('120000'), 'confirmed'))
        self.assertEqual(translation.unit, '頁')

    def test_reverse_only_removes_untouched_seed_items(self):
        ServiceItem.objects.filter(code='permanent_residence').update(default_price=170000)
        seed_migration.backward(django_apps, None)
        self.assertEqual(list(ServiceItem.objects.filter(code__in=EXPECTED).values_list('code', flat=True)),
                         ['permanent_residence'])
        seed_migration.forward(django_apps, None)
        self.assertEqual(ServiceItem.objects.filter(code__in=EXPECTED).count(), 8)


class PriceConfirmationTests(ServiceItemFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.visa = ServiceItem.objects.get(code='work_visa_application')

    def detail(self, user):
        return self.get(user, f'{ITEMS}{self.visa.id}/').json()

    def test_staff_sees_customer_price_and_provisional_flag_but_not_floor(self):
        row = self.detail(self.staff_a)
        self.assertEqual((row['default_price'], row['price_status'], row['price_status_display']),
                         ('110000', 'provisional', '暫定価格'))
        self.assertNotIn('floor_price', row)
        self.assertEqual(self.patch(self.staff_a, f'{ITEMS}{self.visa.id}/', {'default_price': 1, 'version': row['updated_at']}).status_code, 403)
        self.assertEqual(self.post(self.staff_a, f'{ITEMS}{self.visa.id}/confirm-price/', {'version': row['updated_at']}).status_code, 403)

    def test_admin_edits_then_confirms_with_audit_and_version(self):
        row = self.detail(self.accountant)
        edited = self.patch(self.accountant, f'{ITEMS}{self.visa.id}/', {'default_price': 121000, 'version': row['updated_at']})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()['price_status'], 'provisional')
        stale = self.post(self.accountant, f'{ITEMS}{self.visa.id}/confirm-price/', {'version': row['updated_at']})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.post(self.accountant, f'{ITEMS}{self.visa.id}/confirm-price/', {}).status_code, 400)
        confirmed = self.post(self.accountant, f'{ITEMS}{self.visa.id}/confirm-price/', {'version': edited.json()['updated_at']})
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        data = confirmed.json()
        self.assertEqual((data['price_status'], data['price_confirmed_by_name']), ('confirmed', '会計'))
        self.assertTrue(data['price_confirmed_at'])
        log = AuditLog.objects.get(action='service_item_price_confirmed')
        self.assertEqual(log.changes['price_status'], {'from': 'provisional', 'to': 'confirmed'})
        self.assertEqual(self.post(self.accountant, f'{ITEMS}{self.visa.id}/confirm-price/', {'version': data['updated_at']}).status_code, 400)
        # 確定後に価格を変えると暫定に戻る（確定し直す）
        changed = self.patch(self.accountant, f'{ITEMS}{self.visa.id}/', {'default_price': 125000, 'version': data['updated_at']})
        self.assertEqual(changed.json()['price_status'], 'provisional')
        self.assertEqual(changed.json()['price_confirmed_at'], None)

    def test_manager_without_floor_permission_cannot_confirm(self):
        manager = grant(make_user('manager_p6'), 'use_service_item', 'manage_service_item')
        row = self.detail(manager)
        response = self.post(manager, f'{ITEMS}{self.visa.id}/confirm-price/', {'version': row['updated_at']})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AuditLog.objects.filter(action='service_item_price_confirm', result='denied').exists())

    def test_provisional_items_flow_into_reception_and_documents_with_snapshots(self):
        reception = self.client
        self.client.force_login(self.staff_a)
        from apps.cases.models import CaseApplicationCategory, CaseTypeMaster

        response = reception.post('/api/receptions/', {
            'existing_customer_id': self.customer.id,
            'case': {'case_type_master': CaseTypeMaster.objects.get(code='ac').id,
                     'application_category': CaseApplicationCategory.objects.get(code='ac').id,
                     'service_items': [{'service_item': self.visa.id, 'quantity': 1},
                                       {'service_item': ServiceItem.objects.get(code='translation').id, 'quantity': 4}]},
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        case = Case.objects.get(pk=response.json()['case'])
        self.assertEqual([i['price_status'] for i in case.service_items], ['provisional', 'provisional'])
        self.assertEqual(case.service_items[1]['quantity'], 4)

        estimate = self.estimate_with(self.accountant, [{'item_name': '就労ビザ申請', 'quantity': 1, 'unit_price': 100000,
                                                          'tax_category': 'tax_10', 'service_item_id': self.visa.id}])
        line = estimate['line_items'][0]
        self.assertEqual((line['service']['price_status'], line['service']['default_price']), ('provisional', 110000))
        issue = self.move(self.accountant, 'estimates', estimate['id'], 'submitted')
        self.assertEqual(issue.status_code, 400)
        self.assertEqual(issue.json()['code'], 'provisional_price_confirmation_required')
        issued = self.move(self.accountant, 'estimates', estimate['id'], 'submitted', confirm_provisional=True)
        self.assertEqual(issued.status_code, 200, issued.content)
        log = AuditLog.objects.get(action='estimate_status_changed')
        self.assertEqual(log.extra['provisional_price_confirmed_rows'], [1])

        invoice = self.invoice_with(self.accountant, [{'item_name': '翻訳', 'quantity': 3, 'unit_price': 5500,
                                                         'tax_category': 'tax_10', 'service_item_id': ServiceItem.objects.get(code='translation').id}])
        self.assertEqual(self.move(self.accountant, 'vouchers', invoice['id'], 'issued').status_code, 400)
        self.assertEqual(self.move(self.accountant, 'vouchers', invoice['id'], 'issued', confirm_provisional=True).status_code, 200)
        history = self.get(self.accountant, f'/api/accounting/vouchers/{invoice["id"]}/status-history/').json()
        self.assertNotIn('floor', json.dumps(history))

        # マスタの価格を変えて確定しても、過去の受付・帳票の内容は変わらない
        row = self.detail(self.accountant)
        edited = self.patch(self.accountant, f'{ITEMS}{self.visa.id}/', {'default_price': 130000, 'version': row['updated_at']}).json()
        self.post(self.accountant, f'{ITEMS}{self.visa.id}/confirm-price/', {'version': edited['updated_at']})
        case.refresh_from_db()
        self.assertEqual((case.service_items[0]['default_price'], case.service_items[0]['price_status']), (110000, 'provisional'))
        again = self.get(self.accountant, f'/api/accounting/estimates/{estimate["id"]}/').json()
        self.assertEqual(again['line_items'][0]['service']['price_status'], 'provisional')
        self.assertEqual(again['line_items'][0]['service']['default_price'], 110000)

    def test_manual_lines_and_confirmed_items_do_not_require_confirmation(self):
        manual = self.estimate_with(self.accountant, [{'item_name': '手入力', 'quantity': 1, 'unit_price': 1000}])
        self.assertEqual(self.move(self.accountant, 'estimates', manual['id'], 'submitted').status_code, 200)
        ServiceItem.objects.filter(pk=self.visa.pk).update(price_status='confirmed')
        confirmed = self.estimate_with(self.accountant, [{'item_name': '就労ビザ申請', 'quantity': 1, 'unit_price': 110000,
                                                           'service_item_id': self.visa.id}])
        self.assertEqual(self.move(self.accountant, 'estimates', confirmed['id'], 'submitted').status_code, 200)
