from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.customers.models import Customer


class Command(BaseCommand):
    help = (
        '2つの Customer が同一人物であると確認できた場合に、duplicate_id を参照している全ての '
        '関連レコード（案件・家族関係・会社従業員・関連会社など）を keep_id に付け替える。'
        'duplicate_id の Customer 行そのものは削除しない（付け替え後、必要なら手動で削除する）。'
        'デフォルトはドライラン（変更しない）。'
    )

    def add_arguments(self, parser):
        parser.add_argument('keep_id', type=int, help='残す側（正）の Customer id')
        parser.add_argument('duplicate_id', type=int, help='統合して消す側の Customer id')
        parser.add_argument('--apply', action='store_true', help='実際にデータベースへ変更を書き込む。')

    def handle(self, *args, **options):
        keep_id = options['keep_id']
        duplicate_id = options['duplicate_id']
        apply_changes = options['apply']

        if keep_id == duplicate_id:
            raise CommandError('keep_id と duplicate_id は異なる Customer id を指定してください。')

        try:
            keep_customer = Customer.objects.get(pk=keep_id)
        except Customer.DoesNotExist:
            raise CommandError(f'Customer id={keep_id} が見つかりません。')
        try:
            duplicate_customer = Customer.objects.get(pk=duplicate_id)
        except Customer.DoesNotExist:
            raise CommandError(f'Customer id={duplicate_id} が見つかりません。')

        self.stdout.write(self.style.WARNING(
            '=== ドライラン（--apply を付けない限り、DBへの書き込みは行いません） ===' if not apply_changes
            else '=== 適用モード：実際にデータベースを更新します ==='
        ))
        self.stdout.write(f'残す: Customer id={keep_customer.id}（{keep_customer.name} / {keep_customer.birth_date}）')
        self.stdout.write(f'統合して消す: Customer id={duplicate_customer.id}（{duplicate_customer.name} / {duplicate_customer.birth_date}）')

        relations = self._reverse_customer_relations()

        with transaction.atomic():
            total = 0
            for related_model, field_name in relations:
                queryset = related_model.objects.filter(**{field_name: duplicate_customer})
                count = queryset.count()
                if count:
                    self.stdout.write(
                        f'  {related_model.__name__}.{field_name}: {count}件を付け替え'
                    )
                    total += count
                    if apply_changes:
                        queryset.update(**{field_name: keep_customer})

            if not apply_changes:
                transaction.set_rollback(True)

        self.stdout.write(f'合計 {total}件のレコードを付け替え{"ました" if apply_changes else "る予定です"}。')
        self._check_active_employment_conflict(keep_customer, apply_changes)

        if apply_changes:
            self.stdout.write(self.style.SUCCESS(
                f'Customer id={duplicate_customer.id} への参照はすべて id={keep_customer.id} に付け替わりました。'
                f'内容を確認のうえ、不要であれば Customer id={duplicate_customer.id} を手動で削除してください（このコマンドは自動削除しません）。'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('ドライラン完了。問題なければ --apply を付けて再実行してください。'))

    def _reverse_customer_relations(self):
        relations = []
        for field in Customer._meta.get_fields():
            if not (field.is_relation and field.auto_created and not field.concrete):
                continue
            relations.append((field.related_model, field.field.name))
        return relations

    def _check_active_employment_conflict(self, keep_customer, apply_changes):
        from apps.companies.models import CompanyStaff

        count = CompanyStaff.objects.filter(
            customer=keep_customer,
            employment_end_date__isnull=True,
        ).count()
        if count > 1:
            self.stdout.write(self.style.WARNING(
                f'  [要確認] Customer id={keep_customer.id} が在職中（退社日未設定）の CompanyStaff を{count}件保持しています。'
                '同時に複数の会社に在職している状態になっていないか確認してください。'
            ))
