"""事務所設定（事業年度末月）：DB 優先・環境変数は fallback、変更は system_admin のみ・監査、台帳は快照で遡及しない。"""
from django.test import TestCase, override_settings

from apps.audit.models import AuditLog
from apps.office.models import OfficeSettings
from apps.real_estate.models import LegalLedger
from apps.real_estate.tests import RealEstateFixture

URL = '/api/office-settings/'


class OfficeSettingsApiTests(RealEstateFixture, TestCase):
    def test_fallback_then_database(self):
        body = self.api(self.staff_a, 'get', URL).json()
        self.assertEqual((body['fiscal_year_end_month'], body['source']), (3, 'fallback'))
        with override_settings(REAL_ESTATE_FISCAL_YEAR_END_MONTH=12):
            self.assertEqual(self.api(self.staff_a, 'get', URL).json()['fiscal_year_end_month'], 12)
        self.assertEqual(self.api(self.li, 'patch', URL, {'fiscal_year_end_month': 6}).status_code, 200)
        with override_settings(REAL_ESTATE_FISCAL_YEAR_END_MONTH=12):
            body = self.api(self.staff_a, 'get', URL).json()
        self.assertEqual((body['fiscal_year_end_month'], body['source']), (6, 'database'))
        self.assertEqual(OfficeSettings.objects.count(), 1)

    def test_only_system_admin_and_validation_and_audit(self):
        for user in (self.staff_a, self.jiao):
            self.assertEqual(self.api(user, 'patch', URL, {'fiscal_year_end_month': 12}).status_code, 403)
        for bad in (0, 13, 'x', None):
            self.assertEqual(self.api(self.li, 'patch', URL, {'fiscal_year_end_month': bad}).status_code, 400)
        self.assertEqual(self.api(self.li, 'patch', URL, {'fiscal_year_end_month': 12}).status_code, 200)
        log = AuditLog.objects.get(module='office', action='fiscal_year_end_month_changed')
        self.assertEqual(log.changes, {'fiscal_year_end_month': [3, 12]})
        self.assertEqual(log.user, self.li)


class LedgerSnapshotTests(RealEstateFixture, TestCase):
    def ledger_for(self, date_str):
        tx = self.create_tx(transaction_date=date_str)
        return self.api(self.staff_a, 'post', f"/api/real-estate/transactions/{tx['id']}/ensure-ledger/").json()

    def test_snapshot_not_retroactive(self):
        first = self.ledger_for('2026-09-10')
        self.assertEqual((first['fiscal_year_end_month'], first['fiscal_year'], first['retention_until']), (3, 2027, '2032-03-31'))
        self.api(self.li, 'patch', URL, {'fiscal_year_end_month': 12})
        # 既存の台帳は自分の快照（3 月）で計算を続ける
        edited = self.api(self.staff_a, 'patch', f"/api/real-estate/ledgers/{first['id']}/", {'contract_date': '2026-10-01'}).json()
        self.assertEqual((edited['fiscal_year_end_month'], edited['fiscal_year']), (3, 2027))
        # 新しい台帳は現在の設定（12 月）を快照にする
        second = self.ledger_for('2026-09-10')
        self.assertEqual((second['fiscal_year_end_month'], second['fiscal_year'], second['retention_until']), (12, 2026, '2031-12-31'))

    def test_closed_ledger_is_frozen(self):
        ledger = self.ledger_for('2026-09-10')
        self.api(self.li, 'post', '/api/real-estate/ledgers/close-year/', {'fiscal_year': 2027})
        self.api(self.li, 'patch', URL, {'fiscal_year_end_month': 6})
        corrected = self.api(self.li, 'post', f"/api/real-estate/ledgers/{ledger['id']}/correct/",
                             {'changes': {'contract_date': '2026-05-01'}, 'reason': '日付訂正'}).json()
        self.assertEqual((corrected['fiscal_year_end_month'], corrected['fiscal_year'], corrected['retention_until']),
                         (3, 2027, '2032-03-31'))
        # 締め直しても締め済みは変わらない
        self.api(self.li, 'post', '/api/real-estate/ledgers/close-year/', {'fiscal_year': 2027})
        row = LegalLedger.objects.get(pk=ledger['id'])
        self.assertEqual((row.fiscal_year_end_month, str(row.retention_until)), (3, '2032-03-31'))

    def test_legacy_row_without_snapshot_gets_current_month_at_close(self):
        ledger = self.ledger_for('2026-09-10')
        LegalLedger.objects.filter(pk=ledger['id']).update(fiscal_year_end_month=None)
        result = self.api(self.li, 'post', '/api/real-estate/ledgers/close-year/', {'fiscal_year': 2027}).json()
        self.assertEqual(result['ledgers'], 1)
        row = LegalLedger.objects.get(pk=ledger['id'])
        self.assertEqual(row.fiscal_year_end_month, 3)
        self.assertIsNotNone(row.fiscal_year_closed_at)
