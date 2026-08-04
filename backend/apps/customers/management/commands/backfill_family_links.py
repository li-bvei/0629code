from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.companies.models import CompanyStaff
from apps.customers.models import Customer, FamilyMember

FAMILY_MEMBER_FIELDS = [
    'name', 'name_kana', 'birth_date', 'gender', 'nationality',
    'residence_status', 'residence_card_no', 'residence_expiry',
    'phone', 'postal_code', 'address', 'my_number',
]

COMPANY_STAFF_FIELDS = [
    'name', 'name_kana', 'birth_date', 'gender', 'nationality',
    'residence_status', 'residence_card_no', 'residence_expiry',
    'passport_no', 'passport_expiry', 'phone', 'email',
    'postal_code', 'address', 'my_number',
]


def customer_kwargs_from(row, fields):
    return {field: getattr(row, field) for field in fields if hasattr(Customer, field)}


def normalize_name(name):
    return ''.join((name or '').split())


def match_key(name, birth_date):
    return (normalize_name(name), birth_date)


class Command(BaseCommand):
    help = (
        '既存の FamilyMember / CompanyStaff レコードのうち、まだ family_customer / customer が '
        '設定されていない行に対して、Customer への紐付けを行う（完全一致するものは自動リンク、'
        '一致しないものは新規 Customer を作成してリンクする）。デフォルトはドライラン（変更しない）。'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='実際にデータベースへ変更を書き込む。')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        self.stdout.write(self.style.WARNING(
            '=== ドライラン（--apply を付けない限り、DBへの書き込みは行いません） ===' if not apply_changes
            else '=== 適用モード：実際にデータベースを更新します ==='
        ))

        customers_by_key = defaultdict(list)
        for customer in Customer.objects.all():
            customers_by_key[match_key(customer.name, customer.birth_date)].append(customer)

        with transaction.atomic():
            self._backfill_family_members(customers_by_key, apply_changes)
            self._backfill_company_staff(customers_by_key, apply_changes)
            if not apply_changes:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS('=== 完了 ==='))

    def _backfill_family_members(self, customers_by_key, apply_changes):
        self.stdout.write('\n--- FamilyMember ---')
        targets = list(FamilyMember.objects.filter(family_customer__isnull=True))

        groups = defaultdict(list)
        for row in targets:
            groups[match_key(row.name, row.birth_date)].append(row)

        linked, created, merged_groups = 0, 0, 0
        for key, rows in groups.items():
            name, birth_date = rows[0].name, rows[0].birth_date
            matches = customers_by_key.get(key, [])

            if len(matches) == 1:
                target_customer = matches[0]
                self.stdout.write(f'  [自動リンク] {name}（{birth_date}）→ 既存 Customer id={target_customer.id}（{len(rows)}件）')
                linked += len(rows)
            elif len(matches) > 1:
                self.stdout.write(self.style.WARNING(
                    f'  [要確認] {name}（{birth_date}）が Customer 側に複数件ヒットしました。自動処理をスキップします: '
                    f'{[c.id for c in matches]}'
                ))
                continue
            else:
                first = rows[0]
                if apply_changes:
                    target_customer = Customer.objects.create(**customer_kwargs_from(first, FAMILY_MEMBER_FIELDS))
                else:
                    target_customer = None
                self.stdout.write(f'  [新規作成] {name}（{birth_date}）→ 新しい Customer を作成（{len(rows)}件がリンク）')
                created += len(rows)
                if len(rows) > 1:
                    merged_groups += 1
                    self.stdout.write(self.style.WARNING(
                        f'    ※ 同一の氏名・生年月日を持つ FamilyMember が{len(rows)}件あったため、'
                        '同一人物とみなして1つの Customer にまとめてリンクしました。'
                    ))

            if apply_changes:
                for row in rows:
                    row.family_customer = target_customer
                    row.save(update_fields=['family_customer'])

        self.stdout.write(f'  自動リンク: {linked}件 / 新規作成してリンク: {created}件（うち複数件統合: {merged_groups}グループ）')
        self._report_birth_date_collisions('FamilyMember', targets)

    def _backfill_company_staff(self, customers_by_key, apply_changes):
        self.stdout.write('\n--- CompanyStaff ---')
        targets = list(CompanyStaff.objects.filter(customer__isnull=True))

        linked, created = 0, 0
        for row in targets:
            key = match_key(row.name, row.birth_date)
            matches = customers_by_key.get(key, [])

            if len(matches) == 1:
                target_customer = matches[0]
                self.stdout.write(f'  [自動リンク] {row.name}（{row.birth_date}）→ 既存 Customer id={target_customer.id}')
                linked += 1
            elif len(matches) > 1:
                self.stdout.write(self.style.WARNING(
                    f'  [要確認] {row.name}（{row.birth_date}）が Customer 側に複数件ヒットしました。自動処理をスキップします: '
                    f'{[c.id for c in matches]}'
                ))
                continue
            else:
                if apply_changes:
                    target_customer = Customer.objects.create(**customer_kwargs_from(row, COMPANY_STAFF_FIELDS))
                else:
                    target_customer = None
                self.stdout.write(f'  [新規作成] {row.name}（{row.birth_date}）→ 新しい Customer を作成してリンク')
                created += 1

            if apply_changes:
                row.customer = target_customer
                row.save(update_fields=['customer'])

        self.stdout.write(f'  自動リンク: {linked}件 / 新規作成してリンク: {created}件')
        self._report_birth_date_collisions('CompanyStaff', targets)

    def _report_birth_date_collisions(self, label, rows):
        by_birth_date = defaultdict(set)
        for row in rows:
            if row.birth_date:
                by_birth_date[row.birth_date].add(row.name)
        collisions = {birth_date: names for birth_date, names in by_birth_date.items() if len(names) > 1}
        if not collisions:
            return
        self.stdout.write(self.style.WARNING(
            f'  [参考] {label} 内で同じ生年月日・異なる氏名表記の組み合わせが見つかりました（要人力確認、自動統合はしていません）:'
        ))
        for birth_date, names in collisions.items():
            self.stdout.write(f'    {birth_date}: {sorted(names)}')
