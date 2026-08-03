from django.db import migrations


def encrypt_existing_my_numbers(apps, schema_editor):
    CompanyStaff = apps.get_model('companies', 'CompanyStaff')
    for obj in CompanyStaff.objects.exclude(my_number=''):
        obj.save(update_fields=['my_number'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0006_alter_companystaff_my_number'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing_my_numbers, noop_reverse),
    ]
