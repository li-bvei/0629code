"""旧コード互換のための「データベース既定値」を migration から設定する小さな補助。

P0 以前の旧コードは P1～P3 で追加された列を INSERT に含めない。NOT NULL で DB 既定値の無い列が
あると MySQL は 1364 エラーにする。Django 4.2 はモデルの default を DB に残さないため、
follow-up migration でこの関数を使い、列ごとに DB 既定値を明示的に設定する。
（Django の AlterField は DB 既定値を外すので、該当列を変更したら同じ既定値を再設定すること。
  tests の DatabaseDefaultsTests が欠落を検出する。）
"""

# (テーブル, 列, SQL の既定値リテラル)
ROLLBACK_COMPAT_DEFAULTS = {
    'cases': [
        ('cases', 'work_status', "'active'"),
        ('cases', 'waiting_reason', "''"),
        ('cases', 'archive_reason', "''"),
    ],
    'documents': [
        ('case_documents', 'category', "'other'"),
        ('case_documents', 'is_archived', '0'),
        ('case_documents', 'sha256', "''"),
        ('case_documents', 'archive_reason', "''"),
    ],
    'accounting': [
        ('accounting_vouchers', 'invoice_status', "''"),
        ('accounting_vouchers', 'receipt_status', "''"),
    ],
}

# Django が式既定値として残している列（MySQL 8.0.13+）。欠落していないかをテストで確認する。
EXPRESSION_DEFAULT_COLUMNS = [
    ('cases', 'waiting_note'),
    ('cases', 'next_action_blocked_reason'),
    ('accounting_vouchers', 'issued_snapshot'),
]


def _apply(schema_editor, items, drop=False):
    if schema_editor.connection.vendor not in ('mysql', 'postgresql'):
        return  # SQLite 等は ALTER COLUMN ... SET DEFAULT を持たない（本番・テストは MySQL）
    q = schema_editor.quote_name
    for table, column, literal in items:
        if drop:
            schema_editor.execute(f'ALTER TABLE {q(table)} ALTER COLUMN {q(column)} DROP DEFAULT')
        else:
            schema_editor.execute(f'ALTER TABLE {q(table)} ALTER COLUMN {q(column)} SET DEFAULT {literal}')


def set_defaults(app_label):
    def forward(apps, schema_editor):
        _apply(schema_editor, ROLLBACK_COMPAT_DEFAULTS[app_label])

    def backward(apps, schema_editor):
        _apply(schema_editor, ROLLBACK_COMPAT_DEFAULTS[app_label], drop=True)

    return forward, backward
