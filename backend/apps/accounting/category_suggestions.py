"""支出カテゴリの入力支援（検索・同義語の規範名提案・本人履歴からの推薦）。

- category は自由記述のまま。ここは「候補を示す」だけで、保存値は利用者が確定した文字列。
- 推薦・履歴検索は必ず本人（owner=利用者）の支出だけを使う。他人の報銷内容は読まない
  （expense_view_all を持つ利用者でも同じ）。
- 既存データの一括書き換えはしない。
- 外部の生成 AI は使わず、ローカルの規則と履歴一致だけで判定する。
"""
import unicodedata
from collections import Counter

from .models import Expense, ExpenseCategory

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


def build_suggestions(user, query='', place='', expense_target='', note=''):
    return {
        'query': query,
        'matches': search_categories(user, query),
        'normalized': normalization_suggestion(user, query),
        'recommendations': recommend_categories(user, place, expense_target, note),
        'source_scope': 'own_history',
    }
