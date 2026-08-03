from django.db import migrations


DEFAULT_TAX_CATEGORY = 'tax_10'
DEFAULT_TAX_CATEGORY_LABEL = '10％'


def add_default_tax_category(apps, schema_editor):
    AccountingVoucher = apps.get_model('accounting', 'AccountingVoucher')
    for voucher in AccountingVoucher.objects.all().only('id', 'line_items'):
        line_items = voucher.line_items
        if not isinstance(line_items, list):
            continue

        changed = False
        normalized_items = []
        for item in line_items:
            if not isinstance(item, dict):
                normalized_items.append(item)
                continue

            next_item = dict(item)
            if not next_item.get('tax_category'):
                next_item['tax_category'] = DEFAULT_TAX_CATEGORY
                next_item['tax_category_label'] = DEFAULT_TAX_CATEGORY_LABEL
                changed = True
            normalized_items.append(next_item)

        if changed:
            voucher.line_items = normalized_items
            voucher.save(update_fields=['line_items'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0011_taxrenewalagenttemplate'),
    ]

    operations = [
        migrations.RunPython(add_default_tax_category, noop_reverse),
    ]
