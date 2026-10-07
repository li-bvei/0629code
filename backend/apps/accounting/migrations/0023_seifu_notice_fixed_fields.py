from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0022_service_items_line_costs'),
    ]

    operations = [
        migrations.AddField(
            model_name='seifunoticepdfrecord',
            name='recipient_name',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='宛名'),
        ),
        migrations.AddField(
            model_name='seifunoticepdfrecord',
            name='permit_number',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='許可番号'),
        ),
        migrations.AddField(
            model_name='seifunoticepdfrecord',
            name='issue_date',
            field=models.DateField(blank=True, null=True, verbose_name='通知日'),
        ),
        migrations.AddField(
            model_name='seifunoticepdfrecord',
            name='template_key',
            field=models.CharField(blank=True, max_length=60, null=True, verbose_name='テンプレート'),
        ),
    ]
