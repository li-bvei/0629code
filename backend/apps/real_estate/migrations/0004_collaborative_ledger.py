from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_responsible_text(apps, schema_editor):
    transaction_model = apps.get_model('real_estate', 'RealEstateTransaction')
    for transaction in transaction_model.objects.select_related('responsible_employee').iterator():
        employee = transaction.responsible_employee
        if employee is not None and employee.name:
            transaction.responsible_name = employee.name
            transaction.save(update_fields=['responsible_name'])


def remove_legacy_permissions(apps, schema_editor):
    permission = apps.get_model('auth', 'Permission')
    permission.objects.filter(
        content_type__app_label='real_estate',
        codename__in=('real_estate_view_all', 'real_estate_change_all'),
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('real_estate', '0003_ledger_fiscal_month_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='realestatetransaction',
            name='responsible_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='担当者'),
        ),
        migrations.RunPython(copy_responsible_text, migrations.RunPython.noop),
        migrations.RemoveField(model_name='realestatetransaction', name='responsible_employee'),
        migrations.RemoveField(model_name='realestatetransaction', name='source_billed_to_client_amount'),
        migrations.RemoveField(model_name='realestatetransaction', name='source_billed_to_sunrise_amount'),
        migrations.RemoveField(model_name='realestatetransaction', name='source_sunrise_invoice_amount'),
        migrations.AddField(
            model_name='realestatetransaction',
            name='archive_reason',
            field=models.CharField(blank=True, max_length=500, verbose_name='アーカイブ理由'),
        ),
        migrations.AddField(
            model_name='realestatetransaction',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='アーカイブ日時'),
        ),
        migrations.AddField(
            model_name='realestatetransaction',
            name='archived_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='アーカイブ実行者'),
        ),
        migrations.AddField(
            model_name='realestatetransaction',
            name='is_archived',
            field=models.BooleanField(default=False, verbose_name='アーカイブ済み'),
        ),
        migrations.AddField(
            model_name='realestatetransaction',
            name='restored_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='復元日時'),
        ),
        migrations.AddField(
            model_name='realestatetransaction',
            name='restored_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='復元実行者'),
        ),
        migrations.AddField(
            model_name='realestatetransaction',
            name='source_file_sha256',
            field=models.CharField(blank=True, db_index=True, max_length=64, verbose_name='取込元 SHA-256'),
        ),
        migrations.AddField(
            model_name='realestatetransaction',
            name='source_reference',
            field=models.CharField(blank=True, max_length=100, verbose_name='取込元番号'),
        ),
        migrations.AlterModelOptions(
            name='realestatetransaction',
            options={
                'ordering': ['-created_at', '-id'],
                'permissions': [
                    ('use_real_estate', '不動産モジュールを利用'),
                    ('view_real_estate', '不動産記録を閲覧'),
                    ('create_real_estate', '不動産記録を新規登録'),
                    ('change_real_estate', '不動産記録を編集'),
                    ('archive_real_estate', '不動産記録をアーカイブ'),
                    ('restore_real_estate', '不動産記録を復元'),
                    ('export_real_estate', '不動産記録・台帳を出力'),
                    ('manage_legal_ledger', '不動産：法定台帳を管理'),
                    ('correct_legal_ledger', '不動産：法定台帳を更正'),
                    ('close_legal_ledger_year', '不動産：法定台帳の年度を締める'),
                    ('manage_profit_distribution', '不動産：内部利益配分の閲覧・編集'),
                    ('import_real_estate', '不動産：LIST 取込を実行'),
                ],
                'verbose_name': '不動産取引',
                'verbose_name_plural': '不動産取引',
            },
        ),
        migrations.RunPython(remove_legacy_permissions, migrations.RunPython.noop),
    ]
