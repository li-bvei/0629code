from django.db import migrations


def encrypt_existing_my_numbers(apps, schema_editor):
    Customer = apps.get_model('customers', 'Customer')
    FamilyMember = apps.get_model('customers', 'FamilyMember')
    for model in (Customer, FamilyMember):
        for obj in model.objects.exclude(my_number=''):
            obj.save(update_fields=['my_number'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0005_alter_customer_my_number_and_more'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing_my_numbers, noop_reverse),
    ]
