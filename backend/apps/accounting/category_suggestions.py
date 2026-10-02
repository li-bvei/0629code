"""支出カテゴリの入力支援（検索・同義語の規範名提案・本人履歴からの推薦・文字規則からの提案・主档への蓄積）。

- category は自由記述のまま。ここは「候補を示す」だけで、保存値は利用者が確定した文字列。
- 推薦・履歴検索は必ず本人（owner=利用者）の支出だけを使う。他人の報銷内容は読まない
  （expense_view_all を持つ利用者でも同じ）。
- 既存データの一括書き換えはしない。
- 外部の生成 AI は使わず、ローカルの規則と履歴一致だけで判定する。
- 文字規則（ExpenseCategorySuggestionRule）は「場所などに含まれる文字 → カテゴリ」の候補を返すだけ。
  利用者が採用を押すまで入力値も保存値も変えない。提案に使うのは事務所共通の規則と本人用の規則だけで、
  他の利用者が記憶した規則（具体的な場所名）は使わない。
- 利用者が確定して保存したカテゴリは ExpenseCategory 主档に蓄積する（次回から全員の候補になる）。
  共有されるのはカテゴリ名だけで、支出の内容（場所・金額・備考）は共有しない。
"""
import unicodedata
from collections import Counter

from django.db import IntegrityError, transaction
from django.db.models import Max, Q

from apps.audit.services import record

from .models import Expense, ExpenseCategory, ExpenseCategorySuggestionRule

# 規範名 → 同義語。規範名がマスタまたは本人履歴に存在する場合だけ提案に使う。
CATEGORY_SYNONYMS = {
    '交通費': ['交通費用', '交通代', '電車代', 'バス代', 'タクシー代', '乗車賃', '交通', '车费', '交通费'],
    '通信費': ['通信代', '電話代', '携帯代', 'インターネット代', '通信费', '话费'],
    '消耗品費': ['消耗品', '文具', '文房具', '事務用品', '办公用品', '文具费'],
    '会議費': ['会議代', '打合せ費', '打ち合わせ代', '会议费'],
    '接待交際費': ['交際費', '接待費', '招待费'],
    '郵送費': ['郵便代', '切手代', '送料', '郵送代', '快递费', '邮费'],
    '印紙代': ['収入印紙', '印紙', '印紙税'],
    '手数料': ['振込手数料', '支払手数料', '手续费'],
    '証明書代': ['証明書', '証明書手数料', '住民票代', '課税証明代', '证明书费'],
}
HISTORY_LIMIT = 2000
MAX_MATCHES = 15


def normalize_key(value):
    """表記ゆれ比較用のキー（全角半角・大小・空白・末尾の「用」などを吸収）。"""
    text = unicodedata.normalize('NFKC', str(value or '')).strip().lower()
    for ch in (' ', '　', '・', '･', '-', '_'):
        text = text.replace(ch, '')
    if text.endswith('費用'):
        text = text[:-1]
    if text.endswith('费用'):
        text = text[:-1]
    return text


def _synonym_index():
    index = {}
    for canonical, synonyms in CATEGORY_SYNONYMS.items():
        index[normalize_key(canonical)] = canonical
        for synonym in synonyms:
            index.setdefault(normalize_key(synonym), canonical)
    return index


def _own_history(user):
    return Expense.objects.filter(owner=user).order_by('-expense_date', '-id')[:HISTORY_LIMIT]


def _known_names(user):
    master = list(ExpenseCategory.objects.filter(is_active=True).values_list('name', flat=True))
    history = Counter(row.category for row in _own_history(user) if row.category)
    return master, history


def search_categories(user, query):
    master, history = _known_names(user)
    key = normalize_key(query)
    rows = {}
    for name in master:
        if not key or key in normalize_key(name):
            rows[name] = {'name': name, 'source': 'master', 'count': history.get(name, 0)}
    for name, count in history.items():
        if not key or key in normalize_key(name):
            rows.setdefault(name, {'name': name, 'source': 'history', 'count': count})
            rows[name]['count'] = count
    return sorted(rows.values(), key=lambda r: (-r['count'], r['source'] != 'master', r['name']))[:MAX_MATCHES]


def normalization_suggestion(user, value):
    """入力値に対する規範名の提案（無ければ None）。入力値自体は変更しない。"""
    if not value:
        return None
    master, history = _known_names(user)
    known = set(master) | set(history)
    key = normalize_key(value)
    # 1) 既存名と表記ゆれだけが違う（全角半角・空白・「費用」→「費」など）
    for name in sorted(known, key=lambda n: (n not in master, -history.get(n, 0))):
        if name != value and normalize_key(name) == key:
            return {'input': value, 'suggestion': name, 'reason': '既存のカテゴリと表記が異なります'}
    # 2) 同義語辞書で規範名に寄せられ、その規範名が既に使われている
    canonical = _synonym_index().get(key)
    if canonical and canonical != value and canonical in known:
        return {'input': value, 'suggestion': canonical, 'reason': '同じ意味の既存カテゴリがあります'}
    return None


def recommend_categories(user, place='', expense_target='', note=''):
    """本人の過去の支出から、場所・費用対象・備考が一致する記録のカテゴリを頻度と新しさで推薦する。"""
    place_key, target_key = normalize_key(place), normalize_key(expense_target)
    note_key = normalize_key(note)
    if not (place_key or target_key or note_key):
        return []
    scores = Counter()
    reasons = {}
    for rank, row in enumerate(_own_history(user)):
        if not row.category:
            continue
        recency = max(0.2, 1 - rank / 500)
        matched = []
        if place_key and normalize_key(row.place) == place_key:
            matched.append('場所')
        if target_key and normalize_key(row.expense_target) == target_key:
            matched.append('費用対象')
        if note_key and len(note_key) >= 2 and note_key in normalize_key(row.note):
            matched.append('備考')
        if matched:
            scores[row.category] += len(matched) * recency
            reasons.setdefault(row.category, set()).update(matched)
    return [
        {'name': name, 'reason': '過去の同じ' + '・'.join(sorted(reasons[name])) + 'の記録', 'score': round(score, 2)}
        for name, score in scores.most_common(3)
    ]


def rule_recommendations(user, place='', expense_target='', note=''):
    """文字規則からのカテゴリ候補。入力文字に規則の文字が含まれるものを、本人用 → 優先度 → 文字の長さ順で返す。

    使うのは事務所共通の規則と本人用の規則だけ（他人が記憶した規則は使わない）。誰の支出記録も読まない。
    無効な規則・無効なカテゴリは提案しない。
    """
    keys = {
        ExpenseCategorySuggestionRule.FIELD_PLACE: normalize_key(place),
        ExpenseCategorySuggestionRule.FIELD_TARGET: normalize_key(expense_target),
        ExpenseCategorySuggestionRule.FIELD_NOTE: normalize_key(note),
    }
    if not any(keys.values()):
        return []
    labels = dict(ExpenseCategorySuggestionRule.FIELD_CHOICES)
    rules = ExpenseCategorySuggestionRule.objects.filter(
        Q(owner__isnull=True) | Q(owner=user), is_active=True, expense_category__is_active=True,
    ).select_related('expense_category')
    hits = [rule for rule in rules if rule.pattern_key and rule.pattern_key in keys.get(rule.match_field, '')]
    hits.sort(key=lambda rule: (rule.owner_id is None, -rule.priority, -len(rule.pattern_key), rule.id))
    rows, seen = [], set()
    for rule in hits:
        name = rule.expense_category.name
        if name in seen:
            continue
        seen.add(name)
        rows.append({
            'name': name, 'match_field': rule.match_field, 'pattern': rule.pattern,
            'scope': 'office' if rule.owner_id is None else 'personal',
            'reason': f'{labels[rule.match_field]}に「{rule.pattern}」を含む',
            'requires_confirmation': True,
        })
    return rows[:3]


def ensure_category_master(name, *, request=None):
    """利用者が確定して保存したカテゴリを主档に蓄積する（既にあれば再利用）。

    表記ゆれだけが違う既存カテゴリがあれば新しく作らない。無効化されたカテゴリは管理者の判断を尊重して
    有効に戻さない。支出の category（入力された文字）は変更しない。
    """
    name = (name or '').strip()
    if not name:
        return None
    key = normalize_key(name)
    existing = ExpenseCategory.objects.filter(name=name).first()
    if existing is None:
        existing = next((row for row in ExpenseCategory.objects.all() if normalize_key(row.name) == key), None)
    if existing is not None:
        return existing
    next_order = (ExpenseCategory.objects.aggregate(value=Max('sort_order'))['value'] or 0) + 1
    try:
        with transaction.atomic():
            category = ExpenseCategory.objects.create(name=name, is_active=True, sort_order=next_order)
    except IntegrityError:
        # 同時に同じ名前が登録された：先に作られた方を使う
        return ExpenseCategory.objects.get(name=name)
    record(module='accounting', action='expense_category_auto_created', request=request, obj=category,
           object_repr=category.name, via_permission='accounting.use_expense')
    return category


def remember_place_rule(place, category, *, request=None):
    """利用者が明示的に「記憶する」を選んだ場合だけ、場所 → カテゴリの「本人用」規則を 1 件追加する。

    - 作るのは本人だけに効く規則（owner=本人）。事務所共通にするのは管理者の昇格操作だけ。
    - 本人の同じ場所の規則が既にある、または同じ場所・同じカテゴリの事務所共通規則が既にある場合は何もしない
      （既存規則の変更・削除は manage_expense_category の管理画面だけ）。
    戻り値は (規則, 新しく作ったか)。
    """
    pattern = (place or '').strip()[:100]
    key = normalize_key(pattern)
    user = getattr(request, 'user', None)
    if not key or category is None or user is None or not user.is_authenticated:
        return None, False
    field = ExpenseCategorySuggestionRule.FIELD_PLACE
    lookup = {'owner': user, 'match_field': field, 'pattern_key': key}
    existing = ExpenseCategorySuggestionRule.objects.filter(**lookup).first() or (
        ExpenseCategorySuggestionRule.objects.filter(
            owner__isnull=True, match_field=field, pattern_key=key, expense_category=category,
        ).first()
    )
    if existing is not None:
        return existing, False
    try:
        with transaction.atomic():
            rule = ExpenseCategorySuggestionRule.objects.create(
                pattern=pattern, match_field=field, expense_category=category, owner=user,
                source=ExpenseCategorySuggestionRule.SOURCE_CONFIRMED, created_by=user, updated_by=user,
            )
    except IntegrityError:
        return ExpenseCategorySuggestionRule.objects.get(**lookup), False
    record(module='accounting', action='expense_category_rule_remembered', request=request, obj=rule,
           object_repr=str(rule), via_permission='accounting.use_expense')
    return rule, True


def build_suggestions(user, query='', place='', expense_target='', note=''):
    return {
        'query': query,
        'matches': search_categories(user, query),
        'normalized': normalization_suggestion(user, query),
        'recommendations': recommend_categories(user, place, expense_target, note),
        'place_recommendations': rule_recommendations(user, place, expense_target, note),
        'source_scope': 'own_history',
    }


# --- 初期規則（駐車場 → 停车费）の上線前検査 -------------------------------------

SEED_PARKING_CATEGORY = '停车费'
SEED_PARKING_PATTERNS = ('駐車場', '停车场', 'parking')
# 「停车费」と同じ意味で別名のカテゴリ（重複主档）を見つけるための文字
PARKING_LOOKALIKE_WORDS = ('駐車', '停车', '停車', 'パーキング', 'parking')


def inspect_parking_seed():
    """初期規則とその提案先カテゴリの状態を調べる（読むだけ）。"""
    category = ExpenseCategory.objects.filter(name=SEED_PARKING_CATEGORY).first()
    office_rules = {
        rule.pattern_key: rule
        for rule in ExpenseCategorySuggestionRule.objects.filter(
            owner__isnull=True, match_field=ExpenseCategorySuggestionRule.FIELD_PLACE,
            pattern_key__in=[normalize_key(pattern) for pattern in SEED_PARKING_PATTERNS],
        ).select_related('expense_category')
    }
    rules = [(pattern, office_rules.get(normalize_key(pattern))) for pattern in SEED_PARKING_PATTERNS]
    lookalikes = [
        row.name for row in ExpenseCategory.objects.exclude(name=SEED_PARKING_CATEGORY).order_by('id')
        if any(word in normalize_key(row.name) for word in PARKING_LOOKALIKE_WORDS)
    ]
    errors, warnings = [], []
    if category is None:
        errors.append(f'カテゴリ「{SEED_PARKING_CATEGORY}」がありません。--apply でこの名称のカテゴリと初期規則を登録できます'
                      '（別名のカテゴリは作りません）。')
    elif not category.is_active:
        errors.append(f'カテゴリ「{SEED_PARKING_CATEGORY}」が無効です。駐車場の提案は出ません。支出カテゴリの管理画面で'
                      '有効に戻すか、提案が不要なら初期規則を無効にしてください（自動では有効化しません）。')
    for pattern, rule in rules:
        if rule is None:
            errors.append(f'事務所共通の初期規則「{pattern}」がありません。--apply で登録できます。')
        elif category is not None and rule.expense_category_id != category.pk:
            warnings.append(f'規則「{pattern}」の提案先が「{rule.expense_category.name}」です（「{SEED_PARKING_CATEGORY}」ではありません）。')
        elif not rule.is_active:
            warnings.append(f'規則「{pattern}」は無効です（管理者が無効にした場合はこのままで構いません）。')
    if lookalikes:
        warnings.append('駐車場に関する別名のカテゴリがあります：' + '、'.join(lookalikes)
                        + f'。「{SEED_PARKING_CATEGORY}」と重複していないか確認してください。')
    personal = ExpenseCategorySuggestionRule.objects.filter(owner__isnull=False).count()
    return {'category': category, 'rules': rules, 'lookalikes': lookalikes, 'errors': errors, 'warnings': warnings,
            'personal_rule_count': personal}


@transaction.atomic
def repair_parking_seed(user=None):
    """不足しているカテゴリ「停车费」と事務所共通の初期規則だけを登録する。

    既存のカテゴリ・規則は変更しない（無効なカテゴリを有効化しない、提案先を付け替えない、別名を作らない）。
    戻り値は登録した内容の一覧。
    """
    created = []
    category = ExpenseCategory.objects.filter(name=SEED_PARKING_CATEGORY).first()
    if category is None:
        next_order = (ExpenseCategory.objects.aggregate(value=Max('sort_order'))['value'] or 0) + 1
        category = ExpenseCategory.objects.create(name=SEED_PARKING_CATEGORY, is_active=True, sort_order=next_order)
        created.append(f'category:{category.pk}')
    for pattern in SEED_PARKING_PATTERNS:
        key = normalize_key(pattern)
        if ExpenseCategorySuggestionRule.objects.filter(
            owner__isnull=True, match_field=ExpenseCategorySuggestionRule.FIELD_PLACE, pattern_key=key,
        ).exists():
            continue
        rule = ExpenseCategorySuggestionRule.objects.create(
            pattern=pattern, match_field=ExpenseCategorySuggestionRule.FIELD_PLACE, expense_category=category,
            source=ExpenseCategorySuggestionRule.SOURCE_SEED, created_by=user, updated_by=user,
        )
        created.append(f'rule:{rule.pk}')
    if created:
        record(module='accounting', action='expense_category_seed_repaired', user=user,
               object_type='accounting.expensecategorysuggestionrule', extra={'created': created})
    return created
