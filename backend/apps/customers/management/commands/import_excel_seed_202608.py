"""
2026年8月に受領した会社情報.xlsx / 客様進捗状況.xlsx（顧客の実データ）を取り込むための
一回限りのシードコマンド。事前に整形済みの種子データ
assets/seed_data/excel_import_2026_08.json を読み込み、既存の Company / Customer と
名前・生年月日で突き合わせながら DB へ反映する。

方針（backfill_family_links.py / merge_customers.py と同じ）:
- デフォルトはドライラン。--apply を付けたときのみ実際に書き込む。
- 既存レコードとマッチした場合は「空欄のフィールドを埋めるだけ」。既存の値は上書きしない。
- 生年月日が確定できない・複数ソースで食い違う人物は種子データの時点で既に除外済み
  （assets/seed_data/excel_import_2026_08.json の生成過程で対応済み。詳細は
  ドキュメント参照）。マイナンバーは種子データに一切含まれていない。
"""
import json
import re
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.companies.models import Company, CompanyStaff
from apps.customers.models import Customer, FamilyMember

SEED_PATH = Path(settings.BASE_DIR) / 'assets' / 'seed_data' / 'excel_import_2026_08.json'

CUSTOMER_FILL_FIELDS = [
    'name_kana', 'gender', 'phone', 'postal_code', 'address',
    'passport_no', 'passport_expiry', 'residence_card_no', 'residence_expiry', 'note',
]

COMPANY_FILL_FIELDS = {
    'name_kana': 'name_kana',
    'corporate_number': 'corporate_number',
    'postal_code': 'postal_code',
    'address': 'address',
    'fiscal_month': 'fiscal_month',
    'phone': 'phone',
}


def normalize_name(name):
    return ''.join((name or '').split())


def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(value).date()
    except (ValueError, TypeError):
        return None


def clean_fiscal_month(value):
    """Company.fiscal_month は決算月（例: '05'）を持つ2桁の欄だが、元データの
    決済月セルに決算日そのもの（例: '2025-05-31 00:00:00'）が入っているシートがあるため、
    月の部分だけを取り出す。想定外の形式は捨てる（DBの max_length=2 を超えないように）。"""
    if not value:
        return ''
    text = str(value).strip()
    m = re.match(r'^\d{4}-(\d{2})-\d{2}', text)
    if m:
        return m.group(1)
    if re.match(r'^\d{1,2}$', text):
        return text.zfill(2)
    return ''


def identity_key(identity):
    if not identity:
        return None
    return (normalize_name(identity['name']), parse_date(identity['birth_date']))


class Command(BaseCommand):
    help = (
        '2026年8月受領の会社情報.xlsx / 客様進捗状況.xlsx から整形済みの種子データ '
        '(assets/seed_data/excel_import_2026_08.json) を読み込み、Company / Customer / '
        'CompanyStaff / FamilyMember へ反映する。デフォルトはドライラン（--apply で実行）。'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='実際にデータベースへ変更を書き込む。')

    def handle(self, *args, **options):
        apply_changes = options['apply']
        self.stdout.write(self.style.WARNING(
            '=== ドライラン（--apply を付けない限り、DBへの書き込みは行いません） ===' if not apply_changes
            else '=== 適用モード：実際にデータベースを更新します ==='
        ))

        with open(SEED_PATH, encoding='utf-8') as f:
            seed = json.load(f)

        with transaction.atomic():
            company_by_name = self._process_companies(seed['companies'], apply_changes)
            customer_by_identity = self._process_people(seed['people'], apply_changes)
            self._link_representatives(seed['companies'], company_by_name, customer_by_identity, apply_changes)
            self._process_staff(seed['staff_links'], company_by_name, customer_by_identity, apply_changes)
            self._process_relationships(seed['relationships'], customer_by_identity, apply_changes)

            if not apply_changes:
                transaction.set_rollback(True)

        if seed.get('excluded'):
            self.stdout.write(self.style.WARNING('\n--- 今回は取り込んでいない人物（要確認、別途報告済み） ---'))
            for e in seed['excluded']:
                self.stdout.write(f"  {e['name']}（{e.get('birth_date') or '生年月日不明'}）"
                                   f" - {e.get('company_name') or e.get('source_sheet', '')}")

        self.stdout.write(self.style.SUCCESS('\n=== 完了 ==='))

    # -- companies ---------------------------------------------------------

    def _process_companies(self, companies, apply_changes):
        self.stdout.write('\n--- Company ---')
        existing = list(Company.objects.all())
        by_name = {normalize_name(c.name): c for c in existing}
        by_corp_no = {c.corporate_number: c for c in existing if c.corporate_number}

        result = {}
        created, updated = 0, 0
        for c in companies:
            key = normalize_name(c['name'])
            match = by_name.get(key) or (by_corp_no.get(c['corporate_number']) if c['corporate_number'] else None)

            if match:
                filled = []
                for src_field, dst_field in COMPANY_FILL_FIELDS.items():
                    new_value = c.get(src_field, '')
                    if dst_field == 'fiscal_month':
                        new_value = clean_fiscal_month(new_value)
                    if new_value and not getattr(match, dst_field):
                        filled.append(dst_field)
                        if apply_changes:
                            setattr(match, dst_field, new_value)
                if not match.representative_name and c.get('representative_name_raw'):
                    filled.append('representative_name')
                    if apply_changes:
                        match.representative_name = c['representative_name_raw']
                if not match.representative_name_kana and c.get('representative_kana_raw'):
                    filled.append('representative_name_kana')
                    if apply_changes:
                        match.representative_name_kana = c['representative_kana_raw']
                if filled:
                    self.stdout.write(f"  [空欄補完] {c['name']} → 既存 Company id={match.id}（{', '.join(filled)}）")
                    if apply_changes:
                        match.save(update_fields=filled)
                    updated += 1
                result[key] = match
                continue

            if apply_changes:
                obj = Company.objects.create(
                    name=c['name'],
                    name_kana=c.get('name_kana', ''),
                    corporate_number=c.get('corporate_number', ''),
                    postal_code=c.get('postal_code', ''),
                    address=c.get('address', ''),
                    fiscal_month=clean_fiscal_month(c.get('fiscal_month', '')),
                    phone=c.get('phone', ''),
                    representative_name=c.get('representative_name_raw', ''),
                    representative_name_kana=c.get('representative_kana_raw', ''),
                )
                result[key] = obj
            else:
                result[key] = None
            self.stdout.write(f"  [新規作成] {c['name']}")
            created += 1

        self.stdout.write(f'  新規作成: {created}件 / 空欄補完: {updated}件')
        return result

    # -- people --------------------------------------------------------

    def _process_people(self, people, apply_changes):
        self.stdout.write('\n--- Customer ---')
        existing = list(Customer.objects.all())
        by_key = {}
        for cust in existing:
            by_key.setdefault((normalize_name(cust.name), cust.birth_date), []).append(cust)

        result = {}
        created, updated, unchanged, ambiguous = 0, 0, 0, 0
        for p in people:
            birth_date = parse_date(p['birth_date'])
            if not birth_date:
                self.stdout.write(self.style.WARNING(f"  [スキップ] {p['name']}: 生年月日が確定できません"))
                continue
            key = (normalize_name(p['name']), birth_date)
            matches = by_key.get(key, [])

            if len(matches) > 1:
                self.stdout.write(self.style.WARNING(
                    f"  [要確認] {p['name']}（{birth_date}）が既存 Customer に複数件ヒットしました。"
                    f"スキップします: {[m.id for m in matches]}"
                ))
                ambiguous += 1
                continue

            fields = p.get('fields', {})
            if len(matches) == 1:
                match = matches[0]
                filled = []
                for field in CUSTOMER_FILL_FIELDS:
                    new_value = fields.get(field, '')
                    if field in ('passport_expiry', 'residence_expiry'):
                        new_value = parse_date(new_value)
                        current = getattr(match, field)
                    else:
                        current = getattr(match, field)
                    if new_value and not current:
                        filled.append(field)
                        if apply_changes:
                            setattr(match, field, new_value)
                if filled:
                    self.stdout.write(f"  [空欄補完] {p['name']}（{birth_date}）→ 既存 Customer id={match.id}（{', '.join(filled)}）")
                    if apply_changes:
                        match.save(update_fields=filled)
                    updated += 1
                else:
                    unchanged += 1
                result[key] = match
                continue

            if apply_changes:
                obj = Customer.objects.create(
                    name=p['name'],
                    name_kana=p.get('name_kana', ''),
                    birth_date=birth_date,
                    gender=fields.get('gender', ''),
                    phone=fields.get('phone', ''),
                    postal_code=fields.get('postal_code', ''),
                    address=fields.get('address', ''),
                    passport_no=fields.get('passport_no', ''),
                    passport_expiry=parse_date(fields.get('passport_expiry', '')),
                    residence_card_no=fields.get('residence_card_no', ''),
                    residence_expiry=parse_date(fields.get('residence_expiry', '')),
                )
                result[key] = obj
            else:
                result[key] = None
            self.stdout.write(f"  [新規作成] {p['name']}（{birth_date}）")
            created += 1

        self.stdout.write(
            f'  新規作成: {created}件 / 空欄補完: {updated}件 / '
            f'既存と完全一致（変更なし）: {unchanged}件 / 要確認（スキップ）: {ambiguous}件'
        )
        return result

    # -- links ---------------------------------------------------------

    def _link_representatives(self, companies, company_by_name, customer_by_identity, apply_changes):
        self.stdout.write('\n--- Company.representative_customer ---')
        linked, candidates = 0, 0
        for c in companies:
            name_key = normalize_name(c['name'])
            identity = c.get('representative_identity')  # [name, birth_date] のペア
            if name_key not in company_by_name or not identity or len(identity) != 2:
                continue
            key = (normalize_name(identity[0]), parse_date(identity[1]))
            if key not in customer_by_identity:
                continue
            candidates += 1
            if apply_changes:
                company = company_by_name[name_key]
                customer = customer_by_identity[key]
                if company and customer and company.representative_customer_id != customer.id:
                    company.representative_customer = customer
                    company.save(update_fields=['representative_customer'])
                    linked += 1
        if apply_changes:
            self.stdout.write(f'  代表者リンク: {linked}件')
        else:
            self.stdout.write(f'  代表者リンク対象: {candidates}件（ドライランのため未実行）')

    def _process_staff(self, staff_links, company_by_name, customer_by_identity, apply_changes):
        self.stdout.write('\n--- CompanyStaff ---')
        created = 0
        for s in staff_links:
            name_key = normalize_name(s['company_name'])
            emp = s.get('employee')
            if name_key not in company_by_name or not emp:
                continue
            key = (normalize_name(emp['name']), parse_date(emp['birth_date']))
            if key not in customer_by_identity:
                continue
            if apply_changes:
                company = company_by_name[name_key]
                customer = customer_by_identity[key]
                if company and customer:
                    exists = CompanyStaff.objects.filter(company=company, customer=customer).exists()
                    if not exists:
                        CompanyStaff.objects.create(
                            company=company,
                            customer=customer,
                            name=customer.name,
                            name_kana=customer.name_kana,
                            birth_date=customer.birth_date,
                        )
            self.stdout.write(f"  [従業員] {emp['name']} - {s['company_name']}")
            created += 1
        self.stdout.write(f'  対象: {created}件')

    def _process_relationships(self, relationships, customer_by_identity, apply_changes):
        self.stdout.write('\n--- FamilyMember ---')
        created, skipped = 0, 0
        for r in relationships:
            head = r.get('head')
            dependent = r.get('dependent')
            if not head or not dependent:
                continue
            head_key = (normalize_name(head['name']), parse_date(head['birth_date']))
            dep_key = (normalize_name(dependent['name']), parse_date(dependent['birth_date']))
            head_customer = customer_by_identity.get(head_key)
            dep_customer = customer_by_identity.get(dep_key)

            if apply_changes and head_customer and dep_customer:
                exists = FamilyMember.objects.filter(
                    customer=head_customer, family_customer=dep_customer,
                ).exists()
                if exists:
                    skipped += 1
                    continue
                FamilyMember.objects.create(
                    customer=head_customer,
                    family_customer=dep_customer,
                    relationship=r['relationship'],
                    is_dependent=(r['relationship'] == 'child'),
                )
            self.stdout.write(f"  [{r['relationship']}] {head['name']} - {dependent['name']}")
            created += 1
        self.stdout.write(f'  対象: {created}件（既存と重複しスキップ: {skipped}件、ドライランでは概算）')
