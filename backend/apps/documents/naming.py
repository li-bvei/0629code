"""案件ファイルの「資料内容」と表示用ファイル名（P6）。

表示名は「資料内容-顧客名.元の拡張子」。顧客名は後端が関連案件から決める（客户端は指定できない）：
案件の顧客の氏名、無ければ案件の会社名。どちらも無ければ字段エラー（推測しない）。
実際の保存名（file）は従来どおり UUID で、表示名をディスク上のパスには使わない。

同じ案件で同じ表示名（大文字小文字を区別しない）が既にあるときは、新しいファイルを
「資料内容-顧客名 (ID 123).拡張子」にして保存する。名前は登録時に決まり、その後の選択範囲で変わらない
（P2 の ZIP と同じ「ID が小さいものが元の名前」の原則）。
"""
import os
import re
import unicodedata

from rest_framework.exceptions import ValidationError

from .upload_policy import ALLOWED_EXTENSIONS, RESERVED_STEMS

CONTENT_LABEL_MAX_LENGTH = 60
UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
FORBIDDEN_LABEL_CHARS = re.compile(r'[\\/:*?"<>|]')
MAX_DISPLAY_NAME_LENGTH = 180


def normalize_content_label(value):
    """登録者が入力した資料内容（必須）。危険な文字・パスにならない名前だけを受け付ける。"""
    label = unicodedata.normalize('NFC', str(value or '')).strip()
    label = re.sub(r'\s+', ' ', label)
    if not label:
        raise ValidationError({'content_label': ['資料内容（例：住民票・在留カード）を入力してください。']})
    if len(label) > CONTENT_LABEL_MAX_LENGTH:
        raise ValidationError({'content_label': [f'資料内容は {CONTENT_LABEL_MAX_LENGTH} 文字以内で入力してください。']})
    if any(unicodedata.category(char) in ('Cc', 'Cf', 'Co', 'Cs', 'Cn', 'Zl', 'Zp') for char in label):
        raise ValidationError({'content_label': ['資料内容に制御文字・書式文字は使えません。']})
    if FORBIDDEN_LABEL_CHARS.search(label):
        raise ValidationError({'content_label': ['資料内容に \\ / : * ? " < > | は使えません。']})
    if label in ('.', '..') or '..' in label or label.endswith(('.', ' ')) or label.startswith('.'):
        raise ValidationError({'content_label': ['資料内容の先頭・末尾に「.」は使えません（「..」も不可）。']})
    if label.split('.')[0].strip().lower() in RESERVED_STEMS:
        raise ValidationError({'content_label': ['この名前は資料内容に使えません（予約された名前）。']})
    return label


LEGACY_LABEL_FALLBACK = '資料'


def legacy_content_label(*candidates):
    """旧クライアント互換（P6 以前の単ファイル登録 API）：content_label を送らない登録に資料内容を派生する。

    候補（必要資料名・タイトル・元のファイル名・分類名の順）から、危険な文字を空白に置き換えて
    normalize_content_label を通る最初の値を使う。どれも使えなければ「資料」。顧客名は派生しない（後端が案件から取る）。
    """
    for raw in candidates:
        text = unicodedata.normalize('NFC', str(raw or ''))
        text = ''.join(' ' if (unicodedata.category(ch) in ('Cc', 'Cf', 'Co', 'Cs', 'Cn', 'Zl', 'Zp')
                               or FORBIDDEN_LABEL_CHARS.match(ch)) else ch for ch in text)
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r'\s+', ' ', text).strip(' .')[:CONTENT_LABEL_MAX_LENGTH].strip(' .')
        if not text:
            continue
        try:
            return normalize_content_label(text)
        except ValidationError:
            continue
    return LEGACY_LABEL_FALLBACK


def has_party_name(case):
    try:
        party_name(case)
    except ValidationError:
        return False
    return True


def party_name(case):
    """表示名に使う相手の名前（顧客の氏名、無ければ会社名）。"""
    customer = getattr(case, 'customer', None)
    name = (getattr(customer, 'name', '') or '').strip() if customer is not None else ''
    if not name and getattr(case, 'company', None) is not None:
        name = (case.company.name or '').strip()
    if not name:
        raise ValidationError({'case': ['案件に顧客または会社が関連付いていないため、ファイル名を作れません。案件を確認してください。']})
    cleaned = UNSAFE_CHARS.sub('_', unicodedata.normalize('NFC', name)).strip(' .')
    return re.sub(r'\s+', '', cleaned) or '_'


def safe_extension(original_name):
    """元のファイルの拡張子（小文字）。許可した拡張子以外は使わない（資料内容で上書きさせない）。"""
    ext = os.path.splitext(os.path.basename(str(original_name or '').replace('\\', '/')))[1].lower()
    return ext if ext in ALLOWED_EXTENSIONS else ''


def build_display_name(label, case, original_name, document_id=None):
    stem = f'{label}-{party_name(case)}'
    suffix = f' (ID {document_id})' if document_id else ''
    ext = safe_extension(original_name)
    limit = MAX_DISPLAY_NAME_LENGTH - len(suffix) - len(ext)
    return f'{stem[:limit]}{suffix}{ext}'


def assign_display_name(document):
    """表示名を決めて保存する。同じ案件に同じ名前があれば ID 付きにする（呼び出し側で案件をロックする）。"""
    from .models import Document

    if not document.content_label:
        return document
    name = build_display_name(document.content_label, document.case, document.file_name)
    clash = Document.objects.filter(case_id=document.case_id, display_name__iexact=name).exclude(pk=document.pk)  # access-reviewed: 同じ案件内の名前の重複確認（出力しない）
    if clash.exists():
        name = build_display_name(document.content_label, document.case, document.file_name, document.pk)
    if name != document.display_name:
        document.display_name = name
        document.save(update_fields=['display_name', 'updated_at'])
    return document


def download_name(document):
    """ダウンロード・ZIP で使う名前：表示名があればそれ、旧データは元のファイル名。

    受保護ダウンロードの共通処理は不動産ファイル（RealEstateFile、表示名の列なし）にも使うため getattr で読む。
    """
    name = getattr(document, 'display_name', '') or document.file_name or os.path.basename(document.file.name or '') or f'document-{document.pk}'
    return os.path.basename(name.replace('\\', '/'))
