"""旧コード（P0 以前）互換のための DB 既定値が存在すること（AlterField 等で消えたら検出する）。

完全な確認（旧コードで実際に書き込み、新コードで読む）は scripts/rollback_compat/run.sh で発布前に行う。
"""
from django.db import connection
from django.test import TestCase

from apps.common.db_defaults import EXPRESSION_DEFAULT_COLUMNS, ROLLBACK_COMPAT_DEFAULTS


def column_default(table, column):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT column_default, is_nullable FROM information_schema.columns '
            'WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s', [table, column])
        row = cursor.fetchone()
    assert row is not None, f'{table}.{column} が存在しません'
    return row


def normalize(value):
    # MySQL の表記ゆれ（'active' / active / _utf8mb4\'\'）を吸収する
    text = str(value)
    for token in ("_utf8mb4", "\\'", "'"):
        text = text.replace(token, '')
    return text


class DatabaseDefaultsTests(TestCase):
    def test_not_null_columns_have_database_defaults(self):
        for items in ROLLBACK_COMPAT_DEFAULTS.values():
            for table, column, literal in items:
                default, nullable = column_default(table, column)
                with self.subTest(column=f'{table}.{column}'):
                    self.assertEqual(nullable, 'NO')
                    self.assertIsNotNone(default, f'{table}.{column} に DB 既定値がありません（旧コードの INSERT が失敗します）')
                    self.assertEqual(normalize(default), normalize(literal))

    def test_expression_defaults_remain(self):
        for table, column in EXPRESSION_DEFAULT_COLUMNS:
            default, nullable = column_default(table, column)
            with self.subTest(column=f'{table}.{column}'):
                self.assertTrue(nullable == 'YES' or default is not None, f'{table}.{column} に DB 既定値がありません')

    def test_old_style_insert_without_new_columns(self):
        """新しい列を含めない INSERT（旧コードと同じ形）が成功すること。"""
        from apps.accounting.models import AccountingVoucher

        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO accounting_vouchers (voucher_type, voucher_number, issue_date, recipient_name, '
                'recipient_honorific, recipient_postal_code, recipient_address, title, amount, tax_amount, total_amount, '
                'details, line_items, note, payment_method, issuer_name, issuer_postal_code, issuer_address, issuer_tel, '
                "issuer_registration_number, bank_info, created_at, updated_at) VALUES ('invoice', 'INV-OLD-1', "
                "'2026-09-30', '', '', '', '', '', 1000, 0, 1000, '', '[]', '', '', '', '', '', '', '', '', NOW(), NOW())")
        voucher = AccountingVoucher.objects.get(voucher_number='INV-OLD-1')
        self.assertEqual((voucher.invoice_status, voucher.receipt_status, voucher.issued_snapshot), ('', '', {}))
