"""支出カテゴリ：場所などの文字規則からの提案、確定したカテゴリの主档への蓄積、規則の記憶と管理権限。"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.models import Expense, ExpenseCategory, ExpenseCategorySuggestionRule
from apps.audit.models import AuditLog
from apps.authentication.testing import make_user

from .tests_links import AccountingFixture

SUGGEST_URL = '/api/accounting/expenses/category-suggestions/'
RULES_URL = '/api/accounting/expense-category-rules/'
PARKING = '停车费'


class RuleFixture(AccountingFixture):
    def suggest(self, user, **params):
        self.client.force_login(user)
        response = self.client.get(SUGGEST_URL, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def place_names(self, user, **params):
        return [row['name'] for row in self.suggest(user, **params)['place_recommendations']]

    def api(self, user, method, url, data=None):
        self.client.force_login(user)
        return getattr(self.client, method)(url, data if data is not None else {}, content_type='application/json')


class SeedRuleTests(RuleFixture, TestCase):
    def test_initial_rules_point_to_one_existing_parking_category(self):
        rules = ExpenseCategorySuggestionRule.objects.filter(source='seed')
        self.assertTrue(all(rule.owner_id is None for rule in rules))  # 初期規則は事務所共通
        self.assertEqual(sorted(rules.values_list('pattern', flat=True)), ['parking', '停车场', '駐車場'])
        self.assertEqual({rule.expense_category.name for rule in rules}, {PARKING})
        self.assertEqual(ExpenseCategory.objects.filter(name=PARKING).count(), 1)
        self.assertFalse(ExpenseCategory.objects.filter(name__in=['駐車場代', '駐車場', '停車費']).exists())

    def test_both_parking_spellings_and_english_suggest_the_same_category(self):
        for place in ('タイムズ駐車場 新宿', '新宿停车场', 'Times PARKING', 'ｐａｒｋｉｎｇ 東口'):
            self.assertEqual(self.place_names(self.staff_a, place=place), [PARKING], place)
        row = self.suggest(self.staff_a, place='新宿駐車場')['place_recommendations'][0]
        self.assertEqual((row['match_field'], row['pattern'], row['requires_confirmation'], row['scope']),
                         ('place', '駐車場', True, 'office'))
        self.assertEqual(row['reason'], '場所に「駐車場」を含む')
        self.assertEqual(self.place_names(self.staff_a, place='新宿区役所'), [])
        self.assertEqual(self.place_names(self.staff_a), [])
        # 場所の規則は備考・費用対象の文字には反応しない
        self.assertEqual(self.place_names(self.staff_a, note='駐車場', expense_target='駐車場'), [])

    def test_existing_response_keys_are_kept(self):
        data = self.suggest(self.staff_a, place='駐車場')
        for key in ('query', 'matches', 'normalized', 'recommendations', 'place_recommendations', 'source_scope'):
            self.assertIn(key, data)
        self.assertEqual(data['source_scope'], 'own_history')

    def test_suggestion_never_writes_anything(self):
        before = (Expense.objects.count(), ExpenseCategory.objects.count(), ExpenseCategorySuggestionRule.objects.count())
        self.suggest(self.staff_a, q='駐', place='新宿駐車場')
        self.assertEqual(before, (Expense.objects.count(), ExpenseCategory.objects.count(),
                                  ExpenseCategorySuggestionRule.objects.count()))

    def test_disabled_rule_or_disabled_category_is_not_suggested(self):
        ExpenseCategorySuggestionRule.objects.filter(pattern='駐車場').update(is_active=False)
        self.assertEqual(self.place_names(self.staff_a, place='新宿駐車場'), [])
        self.assertEqual(self.place_names(self.staff_a, place='新宿停车场'), [PARKING])
        ExpenseCategory.objects.filter(name=PARKING).update(is_active=False)
        self.assertEqual(self.place_names(self.staff_a, place='新宿停车场'), [])


class CategoryMasterTests(RuleFixture, TestCase):
    def test_saving_does_not_silently_apply_the_suggestion(self):
        response = self.post_expense(self.staff_a, category='雑費', place='新宿駐車場')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['category'], '雑費')
        self.assertNotIn('remember_place_category', response.json())
        self.assertEqual(Expense.objects.get(pk=response.json()['id']).category, '雑費')

    def test_confirmed_suggestion_is_saved_and_reuses_existing_master(self):
        before = ExpenseCategory.objects.count()
        response = self.post_expense(self.staff_a, category=PARKING, place='新宿駐車場')
        self.assertEqual(response.json()['category'], PARKING)
        self.assertEqual(ExpenseCategory.objects.count(), before)

    def test_manual_new_category_becomes_one_shared_master(self):
        self.assertEqual(self.post_expense(self.staff_a, category='翻訳料').status_code, 201)
        master = ExpenseCategory.objects.get(name='翻訳料')
        self.assertTrue(master.is_active)
        self.assertTrue(AuditLog.objects.filter(action='expense_category_auto_created', user=self.staff_a,
                                                object_id=str(master.pk)).exists())
        # 2 回目・表記ゆれ（全角空白・全半角）では増えない。入力した文字はそのまま保存される。
        self.post_expense(self.staff_a, category='翻訳料')
        varied = self.post_expense(self.staff_b, category='翻訳 料')
        self.assertEqual(varied.json()['category'], '翻訳 料')
        self.assertEqual(ExpenseCategory.objects.filter(name__startswith='翻訳').count(), 1)
        # 別の利用者の候補にも主档として出る（共有されるのはカテゴリ名だけ）
        match = next(row for row in self.suggest(self.staff_b, q='翻訳')['matches'] if row['name'] == '翻訳料')
        self.assertEqual(match['source'], 'master')

    def test_disabled_master_is_not_reactivated_or_duplicated(self):
        ExpenseCategory.objects.create(name='廃止分類', is_active=False)
        self.assertEqual(self.post_expense(self.staff_a, category='廃止分類').status_code, 201)
        self.assertEqual(ExpenseCategory.objects.filter(name='廃止分類').count(), 1)
        self.assertFalse(ExpenseCategory.objects.get(name='廃止分類').is_active)

    def test_update_also_settles_category(self):
        created = self.post_expense(self.staff_a, category='翻訳料').json()
        response = self.api(self.staff_a, 'patch', f"/api/accounting/expenses/{created['id']}/", {'category': '通訳料'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(ExpenseCategory.objects.filter(name='通訳料').exists())

    def test_history_of_other_users_is_still_private(self):
        Expense.objects.create(expense_date=date(2026, 8, 3), category='他人の分類', place='秘密の場所',
                               amount=Decimal('999'), owner=self.staff_b)
        data = self.suggest(self.staff_a, q='他人', place='秘密の場所')
        self.assertEqual(data['recommendations'], [])
        self.assertEqual(data['place_recommendations'], [])
        self.assertNotIn('他人の分類', [row['name'] for row in data['matches']])
        self.assertEqual(self.suggest(self.jiao, place='秘密の場所')['recommendations'], [])


class RememberRuleTests(RuleFixture, TestCase):
    PLACE = '喫茶ルノアール'

    def remember(self, user, category='会議費', place=None):
        return self.post_expense(user, category=category, place=place or self.PLACE, remember_place_category=True)

    def test_rule_is_remembered_only_when_explicitly_confirmed(self):
        self.post_expense(self.staff_a, category='会議費', place=self.PLACE)
        self.post_expense(self.staff_a, category='会議費', place=self.PLACE, remember_place_category=False)
        self.assertFalse(ExpenseCategorySuggestionRule.objects.filter(source='user_confirmed').exists())

        response = self.remember(self.staff_a)
        self.assertEqual(response.status_code, 201, response.content)
        rule = ExpenseCategorySuggestionRule.objects.get(source='user_confirmed')
        self.assertEqual((rule.pattern, rule.match_field, rule.expense_category.name, rule.owner, rule.created_by),
                         (self.PLACE, 'place', '会議費', self.staff_a, self.staff_a))
        self.assertTrue(AuditLog.objects.filter(action='expense_category_rule_remembered', user=self.staff_a).exists())

    def test_remembered_rule_is_visible_only_to_its_owner(self):
        self.remember(self.staff_a)
        row = self.suggest(self.staff_a, place='喫茶ルノアール 新宿店')['place_recommendations'][0]
        self.assertEqual((row['name'], row['scope']), ('会議費', 'personal'))
        # 他の利用者・全件閲覧権限者・管理者の提案には出ない（具体的な場所名を公共の提案に混ぜない）
        for other in (self.staff_b, self.jiao, self.li):
            self.assertEqual(self.place_names(other, place='喫茶ルノアール 新宿店'), [], other.username)

    def test_each_user_keeps_an_own_rule_and_own_rule_is_not_overwritten(self):
        self.remember(self.staff_a)
        self.remember(self.staff_a, category='接待交際費')  # 本人の既存規則は上書きしない
        self.remember(self.staff_b, category='接待交際費', place='喫茶 ルノアール')
        rules = {rule.owner: rule.expense_category.name
                 for rule in ExpenseCategorySuggestionRule.objects.filter(source='user_confirmed')}
        self.assertEqual(rules, {self.staff_a: '会議費', self.staff_b: '接待交際費'})
        self.assertEqual(self.place_names(self.staff_a, place=self.PLACE), ['会議費'])
        self.assertEqual(self.place_names(self.staff_b, place=self.PLACE), ['接待交際費'])

    def test_own_rule_comes_before_office_rule(self):
        self.remember(self.staff_a, category='雑費', place='新宿駐車場')
        self.assertEqual(self.place_names(self.staff_a, place='新宿駐車場'), ['雑費', PARKING])
        self.assertEqual(self.place_names(self.staff_b, place='新宿駐車場'), [PARKING])

    def test_no_personal_copy_when_office_rule_already_says_the_same(self):
        self.remember(self.staff_a, category=PARKING, place='駐車場')
        self.assertFalse(ExpenseCategorySuggestionRule.objects.filter(source='user_confirmed').exists())

    def test_remember_without_place_is_ignored(self):
        self.post_expense(self.staff_a, category='会議費', remember_place_category=True)
        self.assertFalse(ExpenseCategorySuggestionRule.objects.filter(source='user_confirmed').exists())


class PromoteRuleTests(RuleFixture, TestCase):
    PLACE = '喫茶ルノアール'

    def setUp(self):
        super().setUp()
        self.post_expense(self.staff_a, category='会議費', place=self.PLACE, remember_place_category=True)
        self.rule = ExpenseCategorySuggestionRule.objects.get(source='user_confirmed')
        self.url = f'{RULES_URL}{self.rule.id}/promote/'

    def test_only_category_manager_can_promote(self):
        for user in (self.staff_a, self.staff_b, self.jiao, make_user('promote_su', superuser=True)):
            self.assertEqual(self.api(user, 'post', self.url).status_code, 403, user.username)
        self.assertEqual(ExpenseCategorySuggestionRule.objects.get(pk=self.rule.pk).owner, self.staff_a)
        self.assertEqual(self.place_names(self.staff_b, place=self.PLACE), [])

    def test_manager_sees_personal_rules_and_promotes_to_office_wide(self):
        listed = self.api(self.li, 'get', RULES_URL, {'scope': 'personal'}).json()['results']
        self.assertEqual([(row['pattern'], row['scope'], row['owner_name']) for row in listed],
                         [(self.PLACE, 'personal', 'A')])
        response = self.api(self.li, 'post', self.url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['scope'], response.json()['owner_name']), ('office', ''))
        for user in (self.staff_a, self.staff_b):
            self.assertEqual(self.place_names(user, place='喫茶ルノアール 新宿店'), ['会議費'])
        audit = AuditLog.objects.get(action='expense_category_rule_promoted')
        self.assertEqual((audit.user, audit.extra['previous_owner']), (self.li, 'staff_a'))
        self.assertEqual(self.api(self.li, 'post', self.url).status_code, 400)  # 既に事務所共通

    def test_promote_is_rejected_when_office_rule_with_same_text_exists(self):
        category = ExpenseCategory.objects.get(name=PARKING)
        created = self.api(self.li, 'post', RULES_URL, {'pattern': self.PLACE, 'match_field': 'place',
                                                        'expense_category': category.id})
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(self.api(self.li, 'post', self.url).status_code, 400)
        self.assertEqual(ExpenseCategorySuggestionRule.objects.get(pk=self.rule.pk).owner, self.staff_a)

    def test_scope_cannot_be_changed_through_ordinary_update(self):
        response = self.api(self.li, 'patch', f'{RULES_URL}{self.rule.id}/', {'owner': None, 'scope': 'office'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(ExpenseCategorySuggestionRule.objects.get(pk=self.rule.pk).owner, self.staff_a)


class RuleManagementPermissionTests(RuleFixture, TestCase):
    def body(self, **extra):
        category = ExpenseCategory.objects.get(name=PARKING)
        return {'pattern': 'コインパーキング', 'match_field': 'place', 'expense_category': category.id, **extra}

    def test_ordinary_expense_user_cannot_list_or_maintain_rules(self):
        rule = ExpenseCategorySuggestionRule.objects.first()
        for user in (self.staff_a, self.jiao):
            self.assertEqual(self.api(user, 'get', RULES_URL).status_code, 403)
            self.assertEqual(self.api(user, 'post', RULES_URL, self.body()).status_code, 403)
            self.assertEqual(self.api(user, 'patch', f'{RULES_URL}{rule.id}/', {'is_active': False}).status_code, 403)
            self.assertEqual(self.api(user, 'delete', f'{RULES_URL}{rule.id}/').status_code, 403)
        self.assertTrue(ExpenseCategorySuggestionRule.objects.get(pk=rule.pk).is_active)

    def test_superuser_without_explicit_permission_is_denied(self):
        outsider = make_user('rule_su', superuser=True)
        self.assertEqual(self.api(outsider, 'get', RULES_URL).status_code, 403)

    def test_category_manager_can_create_edit_disable_and_delete(self):
        self.assertEqual(self.api(self.li, 'get', RULES_URL).json()['count'], 3)
        created = self.api(self.li, 'post', RULES_URL, self.body(source='seed'))
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual((created.json()['source'], created.json()['scope']), ('manual', 'office'))  # 後端が決める
        url = f"{RULES_URL}{created.json()['id']}/"
        self.assertEqual(self.api(self.li, 'post', RULES_URL, self.body(pattern='コイン パーキング')).status_code, 400)
        self.assertEqual(self.api(self.li, 'post', RULES_URL, self.body(pattern='  ')).status_code, 400)
        self.assertEqual(self.api(self.li, 'patch', url, {'is_active': False}).status_code, 200)
        self.assertEqual(self.api(self.li, 'patch', url, {'pattern': 'コインP', 'match_field': 'note'}).status_code, 200)
        rule = ExpenseCategorySuggestionRule.objects.get(pk=created.json()['id'])
        self.assertEqual((rule.pattern_key, rule.updated_by), ('コインp', self.li))
        self.assertEqual(self.api(self.li, 'delete', url).status_code, 204)
        for action in ('expense_category_rule_created', 'expense_category_rule_updated', 'expense_category_rule_deleted'):
            self.assertTrue(AuditLog.objects.filter(action=action, user=self.li).exists(), action)

    def test_note_and_target_rules_match_their_own_field(self):
        category = ExpenseCategory.objects.get(name=PARKING)
        self.api(self.li, 'post', RULES_URL, {'pattern': '月極', 'match_field': 'note', 'expense_category': category.id})
        self.assertEqual(self.place_names(self.staff_a, note='月極の支払い'), [PARKING])
        self.assertEqual(self.place_names(self.staff_a, place='月極'), [])


class ParkingSeedCheckTests(RuleFixture, TestCase):
    """上線前検査 check_expense_category_rules：カテゴリ「停车费」と初期規則 3 件。"""

    def run_check(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        try:
            call_command('check_expense_category_rules', *args, stdout=out)
            code = 0
        except SystemExit as exc:
            code = exc.code
        return code, out.getvalue()

    def names(self):
        return set(ExpenseCategory.objects.values_list('name', flat=True))

    def test_migrated_database_passes(self):
        code, output = self.run_check()
        self.assertEqual(code, 0, output)
        self.assertIn('カテゴリ「停车费」：有効', output)
        self.assertEqual(output.count('有効 → 停车费'), 3)

    def test_disabled_category_is_reported_and_never_reactivated(self):
        ExpenseCategory.objects.filter(name=PARKING).update(is_active=False)
        before = self.names()
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('無効です', output)
        code, output = self.run_check('--apply', '--yes', '--username', 'li')
        self.assertEqual(code, 1)  # --apply でも有効化しない（管理者の判断）
        self.assertFalse(ExpenseCategory.objects.get(name=PARKING).is_active)
        self.assertEqual(self.names(), before)
        self.assertEqual(self.place_names(self.staff_a, place='新宿駐車場'), [])

    def test_missing_category_is_reported_then_repaired_without_duplicates(self):
        ExpenseCategory.objects.filter(name=PARKING).delete()  # 規則も一緒に消える（CASCADE）
        self.assertEqual(ExpenseCategorySuggestionRule.objects.count(), 0)
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('カテゴリ「停车费」がありません', output)
        self.assertFalse(ExpenseCategory.objects.filter(name=PARKING).exists())  # dry-run は書かない
        code, output = self.run_check('--apply', '--yes', '--username', 'li')
        self.assertEqual(code, 0, output)
        self.assertEqual(ExpenseCategory.objects.filter(name=PARKING, is_active=True).count(), 1)
        self.assertFalse(self.names() & {'駐車場代', '駐車場', '駐車料金'})
        rules = ExpenseCategorySuggestionRule.objects.all()
        self.assertEqual(sorted(rule.pattern for rule in rules), ['parking', '停车场', '駐車場'])
        self.assertTrue(all(rule.owner_id is None and rule.source == 'seed' for rule in rules))
        self.assertTrue(AuditLog.objects.filter(action='expense_category_seed_repaired', user=self.li).exists())
        # もう一度実行しても増えない
        self.run_check('--apply', '--yes', '--username', 'li')
        self.assertEqual(ExpenseCategorySuggestionRule.objects.count(), 3)

    def test_missing_rule_and_lookalike_category_are_reported(self):
        ExpenseCategorySuggestionRule.objects.filter(pattern='parking').delete()
        ExpenseCategory.objects.create(name='駐車場代')
        code, output = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('初期規則「parking」がありません', output)
        self.assertIn('駐車場代', output)
        self.assertEqual(ExpenseCategorySuggestionRule.objects.count(), 2)

    def test_apply_requires_an_actor_and_keeps_personal_rules_personal(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self.run_check('--apply', '--yes')
        self.post_expense(self.staff_a, category='会議費', place='喫茶ルノアール', remember_place_category=True)
        code, output = self.run_check('--apply', '--yes', '--username', 'li')
        self.assertEqual(code, 0, output)
        self.assertIn('本人用の規則：1 件', output)
        self.assertEqual(ExpenseCategorySuggestionRule.objects.get(source='user_confirmed').owner, self.staff_a)
