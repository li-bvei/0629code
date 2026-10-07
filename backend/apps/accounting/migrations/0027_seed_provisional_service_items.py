# P6（2026-10-07 用户指示）：サービス項目の基本 8 件を「暫定価格」で登録する。
# 金額は画面の動作確認用の暫定値で、正式な報価基準ではない（管理画面で修正し「価格を確定」する）。
# 対客価格は消費税 10％ 込みの値として登録する（金額が税抜額×1.1 の形のため）。
#
# 冪等：
# - 同じ code の項目があれば、空の項目（分類・単位・専門家・価格が未設定のもの）だけを埋める。価格・状態は上書きしない。
# - code の無い同名（同じ分類・名称）の手作業の項目があれば、その項目に code を付けて同様に扱う（重複を作らない）。
# 逆方向：この migration の値のまま（暫定・未使用・価格が初期値のまま）の項目だけを削除する。
#   変更・確定・使用された項目は残す（code も残す）。
from decimal import Decimal

from django.db import migrations

SEED = [
    # code, 分類, 名称, 対客暫定価格, 委託底価, 専門家, 単位
    ('work_visa_application', '在留資格', '就労ビザ申請', 110000, 55000, 'gyousei', '件'),
    ('permanent_residence', '在留資格', '永住許可申請', 165000, 82500, 'gyousei', '件'),
    ('company_dissolution', '法人手続', '会社解散手続', 220000, 165000, 'judicial_scrivener', '件'),
    ('tax_accounting', '税務', '税理士業務', 110000, 88000, 'tax_accountant', '件'),
    ('highly_skilled_application', '在留資格', '高度専門職申請', 165000, 82500, 'gyousei', '件'),
    ('highly_skilled_annual_support', '顧問・支援', '高度専門職一年サポート', 330000, 264000, 'gyousei', '年'),
    ('business_manager_renewal', '在留資格', '経営・管理更新', 165000, 82500, 'gyousei', '件'),
    ('translation', '翻訳', '翻訳', 5500, 3300, '', '頁'),
]


def forward(apps, schema_editor):
    ServiceItem = apps.get_model('accounting', 'ServiceItem')
    for index, (code, category, name, price, floor, professional, unit) in enumerate(SEED, start=1):
        item = ServiceItem.objects.filter(code=code).first()
        if item is None:
            item = ServiceItem.objects.filter(code__isnull=True, category=category, name=name).first()
        if item is None:
            ServiceItem.objects.create(
                code=code, category=category, name=name, default_price=Decimal(price), floor_price=Decimal(floor),
                price_type='tax_included', professional_type=professional, tax_category='tax_10', unit=unit,
                price_status='provisional', is_active=True, sort_order=index * 10,
            )
            continue
        changed = []
        if not item.code:
            item.code = code
            changed.append('code')
        for field, value in (('category', category), ('unit', unit), ('professional_type', professional)):
            if not getattr(item, field) and value:
                setattr(item, field, value)
                changed.append(field)
        for field, value in (('default_price', price), ('floor_price', floor)):
            if getattr(item, field) is None:
                setattr(item, field, Decimal(value))
                changed.append(field)
        if changed:
            item.save(update_fields=changed)


def backward(apps, schema_editor):
    ServiceItem = apps.get_model('accounting', 'ServiceItem')
    for code, category, name, price, floor, professional, unit in SEED:
        ServiceItem.objects.filter(
            code=code, price_status='provisional', first_used_at__isnull=True,
            default_price=Decimal(price), floor_price=Decimal(floor), name=name,
        ).delete()


class Migration(migrations.Migration):
    dependencies = [('accounting', '0026_db_defaults_for_rollback_compat_p6')]

    operations = [migrations.RunPython(forward, backward)]
