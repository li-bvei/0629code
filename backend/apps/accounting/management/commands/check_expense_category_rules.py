"""上線前検査：駐車場の初期規則（accounting/0020）と提案先カテゴリ「停车费」の状態。

既定は読むだけ。問題があれば非ゼロで終了する（部署手順で利用）。--apply は不足分の登録だけを行い、
既存のカテゴリ・規則は変更しない（無効なカテゴリの有効化や、別名カテゴリの作成はしない）。
"""
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounting.category_suggestions import SEED_PARKING_CATEGORY, inspect_parking_seed, repair_parking_seed


class Command(BaseCommand):
    help = 'カテゴリ「停车费」と駐車場の初期規則（事務所共通 3 件）が有効かを検査する。既定は dry-run。'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='不足しているカテゴリ・初期規則を登録する')
        parser.add_argument('--yes', action='store_true', help='--apply の確認を省略する')
        parser.add_argument('--username', help='--apply の実行者（監査に記録する。必須）')

    def _report(self, state):
        category = state['category']
        status = '無し' if category is None else ('有効' if category.is_active else '無効')
        self.stdout.write(f'カテゴリ「{SEED_PARKING_CATEGORY}」：{status}')
        for pattern, rule in state['rules']:
            if rule is None:
                text = '無し'
            else:
                text = f'{"有効" if rule.is_active else "無効"} → {rule.expense_category.name}'
            self.stdout.write(f'事務所共通の規則「{pattern}」：{text}')
        self.stdout.write(f'本人用の規則：{state["personal_rule_count"]} 件（本人の提案にだけ使われます）')
        for message in state['warnings']:
            self.stdout.write(self.style.WARNING(f'WARNING: {message}'))
        for message in state['errors']:
            self.stdout.write(self.style.ERROR(f'ERROR: {message}'))

    def handle(self, *args, **options):
        state = inspect_parking_seed()
        self._report(state)
        if options['apply']:
            if not options['username']:
                raise CommandError('--apply には --username（実行者）が必要です。')
            try:
                user = get_user_model().objects.get(username=options['username'], is_active=True)
            except get_user_model().DoesNotExist as exc:
                raise CommandError('指定した実行者が見つかりません。') from exc
            if not options['yes'] and input('不足しているカテゴリ・初期規則を登録します。よろしいですか？ [y/N] ').lower() != 'y':
                raise CommandError('中止しました。')
            created = repair_parking_seed(user)
            self.stdout.write(f'登録：{created or "なし（不足はありません）"}')
            state = inspect_parking_seed()
            self.stdout.write('--- 登録後 ---')
            self._report(state)
        elif state['errors']:
            self.stdout.write('dry-run のため書き込みませんでした。')
        if state['errors']:
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS('OK'))
