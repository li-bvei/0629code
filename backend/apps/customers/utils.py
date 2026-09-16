from django.db.models import Count, Q

from .models import Customer, FamilyMember

# 双方向に同じ意味を持つ関係のみ自動で逆リンクを作る。親子など非対称な関係は
# 相手側の性別等から自動判定できないため対象外（スタッフが手動で追加する）。
SYMMETRIC_RELATIONSHIPS = {FamilyMember.RELATIONSHIP_SPOUSE, FamilyMember.RELATIONSHIP_SIBLING}


def sync_reverse_family_link(family_member):
    if not family_member.family_customer_id:
        return
    if family_member.relationship not in SYMMETRIC_RELATIONSHIPS:
        return
    reverse_exists = FamilyMember.objects.filter(
        customer_id=family_member.family_customer_id,
        family_customer_id=family_member.customer_id,
    ).exists()
    if reverse_exists:
        return
    FamilyMember.objects.create(
        customer_id=family_member.family_customer_id,
        family_customer_id=family_member.customer_id,
        relationship=family_member.relationship,
    )


def _normalize_name(value):
    """氏名比較用の正規化。全角/半角スペース・記号を除去して素の並びで比較する。"""
    if not value:
        return ''
    cleaned = str(value)
    for ch in (' ', '　', '\t', '\n', '-', '‐', '・', '　'):
        cleaned = cleaned.replace(ch, '')
    return cleaned.lower()


def _normalize_phone_digits(value):
    """電話番号比較用の正規化。ハイフン・国番号（+81 / 81）のゆれを吸収する。"""
    digits = ''.join(c for c in (value or '') if c.isdigit())
    if digits.startswith('81') and len(digits) >= 11:
        digits = '0' + digits[2:]
    return digits


def _phone_digits_match(a_digits, b_digits, tail=8):
    """携帯電話番号は11桁（0+90+8桁）が一般的なので、末尾8桁一致で誤マッチを抑える。"""
    if len(a_digits) < tail or len(b_digits) < tail:
        return False
    return a_digits[-tail:] == b_digits[-tail:]


# マッチ強度
MATCH_STRONG = 'strong'
MATCH_MEDIUM = 'medium'
MATCH_WEAK = 'weak'

_STRENGTH_SCORE = {MATCH_STRONG: 90, MATCH_MEDIUM: 65, MATCH_WEAK: 40}


def find_customer_candidates(*, name='', name_kana='', birth_date=None, phone='',
                             email='', residence_card_number='', passport_number='',
                             limit=10):
    """新規受付の「既存顧客らしき候補」をルールベースで探す。

    強マッチ: 証明書番号一致 / 氏名（完全一致）＋生年月日一致
    中マッチ: 氏名（完全一致）＋電話・メール一致 / 氏名の一部＋生年月日一致
    弱マッチ: 氏名（完全一致）のみ一致 / 氏名の一部＋連絡先一致 / 氏名の一部＋生年月日情報あり
    AI は使わず、確認は必ず人が行う前提。氏名が部分一致にとどまる場合は
    生年月日・電話・メールが揃っていても strong にはしない（同姓同名の誤爆防止）。
    """
    name_norm = _normalize_name(name)
    kana_norm = _normalize_name(name_kana)
    phone_digits = _normalize_phone_digits(phone)
    email = (email or '').strip().lower()
    residence_card_number = (residence_card_number or '').strip()
    passport_number = (passport_number or '').strip()

    if not any([name_norm, kana_norm, phone_digits, email,
                residence_card_number, passport_number]):
        return []

    queryset = Customer.objects.all().annotate(
        case_count=Count('cases', distinct=True),
    )

    # 候補の絞り込み（DB 側で粗く絞ってから Python でスコアリング）。
    rough = Q()
    if residence_card_number:
        rough |= Q(residence_card_no__iexact=residence_card_number)
    if passport_number:
        rough |= Q(passport_no__iexact=passport_number)
    if email:
        rough |= Q(email__iexact=email)
    if phone_digits:
        rough |= Q(phone__icontains=phone_digits[-7:] if len(phone_digits) >= 7 else phone_digits)
    # 氏名は「李 明」「李明」などスペースの有無がぶれるため、トークン単位でも引く。
    # 短い氏名（漢字名など）はさらに1文字ずつ OR して取りこぼしを防ぎ、
    # 精密な判定は Python 側の正規化比較で行う。
    def _name_tokens(value):
        cleaned = (value or '').replace('　', ' ')
        tokens = [t for t in cleaned.split() if t]
        compact = cleaned.replace(' ', '')
        if 0 < len(compact) <= 5:
            tokens.extend(list(compact))
        return tokens

    for token in _name_tokens(name):
        rough |= Q(name__icontains=token) | Q(name_kana__icontains=token)
    for token in _name_tokens(name_kana):
        rough |= Q(name_kana__icontains=token) | Q(name__icontains=token)
    if rough:
        queryset = queryset.filter(rough)
    elif name or name_kana:
        # トークンが取れない特殊ケースでも氏名の素の並びで最終フォールバック。
        queryset = queryset.filter(
            Q(name__icontains=(name or name_kana).strip()[:20])
        )

    candidates = []
    for customer in queryset[:200]:
        reasons = []
        strength = None

        cust_name_norm = _normalize_name(customer.name)
        cust_kana_norm = _normalize_name(customer.name_kana)
        name_match = bool(name_norm) and (
            name_norm == cust_name_norm
            or (bool(kana_norm) and kana_norm == cust_kana_norm)
        )
        name_partial = name_match or (
            bool(name_norm) and (name_norm in cust_name_norm or cust_name_norm in name_norm)
        )
        cust_phone_digits = _normalize_phone_digits(customer.phone)
        birth_match = birth_date is not None and customer.birth_date == birth_date
        phone_match = bool(phone_digits) and _phone_digits_match(phone_digits, cust_phone_digits)
        email_match = bool(email) and (customer.email or '').strip().lower() == email
        # name_partial は同姓同名以外の「一部だけ一致」も含むため、name_match（完全一致）
        # とは区別して強度を1段階以上下げる（同姓同名・部分一致だけで strong にしない）。
        name_partial_only = name_partial and not name_match

        if residence_card_number and (customer.residence_card_no or '').strip().lower() == residence_card_number.lower():
            strength = MATCH_STRONG
            reasons.append('在留カード番号が一致')
        elif passport_number and (customer.passport_no or '').strip().lower() == passport_number.lower():
            strength = MATCH_STRONG
            reasons.append('パスポート番号が一致')
        elif name_match and birth_match:
            strength = MATCH_STRONG
            reasons.append('氏名と生年月日が一致')
        elif name_match and phone_match:
            strength = MATCH_MEDIUM
            reasons.append('氏名と電話番号が一致')
        elif name_match and email_match:
            strength = MATCH_MEDIUM
            reasons.append('氏名とメールアドレスが一致')
        elif name_partial_only and birth_match:
            strength = MATCH_MEDIUM
            reasons.append('氏名の一部と生年月日が一致（同姓同名の可能性を確認してください）')
        elif name_match:
            strength = MATCH_WEAK
            reasons.append('氏名が一致')
        elif name_partial_only and (phone_match or email_match):
            strength = MATCH_WEAK
            reasons.append('氏名の一部と連絡先が一致（要確認）')
        elif name_partial_only and birth_date is not None:
            strength = MATCH_WEAK
            reasons.append('氏名が類似し生年月日情報あり')

        if not strength:
            continue

        candidates.append({
            'customer_id': customer.id,
            'name': customer.name,
            'name_kana': customer.name_kana,
            'birth_date': customer.birth_date.isoformat() if customer.birth_date else None,
            'phone': customer.phone,
            'email': customer.email,
            'case_count': customer.case_count,
            'match_strength': strength,
            'match_score': _STRENGTH_SCORE[strength] + (5 if birth_match else 0),
            'match_reason': ' / '.join(reasons),
        })

    candidates.sort(key=lambda c: c['match_score'], reverse=True)
    return candidates[:limit]
