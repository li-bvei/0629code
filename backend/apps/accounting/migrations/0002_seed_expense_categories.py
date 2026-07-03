from django.db import migrations


def seed_expense_categories(apps, schema_editor):
    ExpenseCategory = apps.get_model('accounting', 'ExpenseCategory')
    category_names = [
        '停车费',
        '交通费',
        '邮寄费',
        '住民票',
        '印章证明',
        '办公用品',
        '餐饮费',
        '行政手续费',
        '软件费',
        '其他',
    ]

    for index, name in enumerate(category_names, start=1):
        ExpenseCategory.objects.get_or_create(
            name=name,
            defaults={
                'is_active': True,
                'sort_order': index,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_expense_categories, migrations.RunPython.noop),
    ]
