"""案件ファイルのアップロード検査（種類・サイズ・ファイル署名）とメタデータ算出。

ウイルス対策ソフトによる検査は行っていない。そのため、許可する拡張子を限定し、主要形式は
先頭バイト（署名）と拡張子の一致を確認し、実行形式・スクリプトは受け付けない。
"""
import hashlib
import mimetypes
import os
import re

from django.conf import settings

ALLOWED_EXTENSIONS = {
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.heic', '.webp', '.tif', '.tiff',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.csv', '.txt', '.zip',
}
# 先頭バイトで形式を確認する拡張子
SIGNATURES = {
    '.pdf': [b'%PDF'],
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.gif': [b'GIF87a', b'GIF89a'],
    '.zip': [b'PK\x03\x04', b'PK\x05\x06'],
    '.docx': [b'PK\x03\x04'],
    '.xlsx': [b'PK\x03\x04'],
    '.pptx': [b'PK\x03\x04'],
}
# 内容が実行形式・スクリプトに見えるものは拡張子に関わらず拒否する
DANGEROUS_PREFIXES = [b'MZ', b'\x7fELF', b'#!', b'<script', b'<?php']


MB = 1024 * 1024
# Windows で予約されている名前（拡張子を除いた部分）。ZIP 展開時にも問題になるため受け付けない
RESERVED_STEMS = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}
MAX_FILENAME_LENGTH = 200


def max_upload_bytes():
    return getattr(settings, 'DOCUMENT_MAX_UPLOAD_BYTES', 20 * MB)


def batch_max_files():
    """一度に選んで登録できるファイル数（P2：複数ファイル登録）。"""
    return getattr(settings, 'DOCUMENT_BATCH_MAX_FILES', 20)


def batch_max_total_bytes():
    return getattr(settings, 'DOCUMENT_BATCH_MAX_TOTAL_BYTES', 200 * MB)


def zip_upload_max_bytes():
    """アップロードする ZIP ファイル 1 件の上限（P6）。通常の 1 件上限より小さくする。
    ZIP は展開せず普通の添付として保存するだけだが、中の一覧（名前・件数・圧縮率）は確認する。"""
    return min(getattr(settings, 'DOCUMENT_ZIP_UPLOAD_MAX_BYTES', 10 * MB), max_upload_bytes())


# アップロードされた ZIP の中身の一覧に対する上限（展開はしない）
ZIP_UPLOAD_MAX_ENTRIES = 200
ZIP_UPLOAD_MAX_UNCOMPRESSED = 100 * MB
ZIP_UPLOAD_MAX_RATIO = 100
NESTED_ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2', '.xz', '.lzh', '.cab'}


def zip_upload_problem(uploaded_file):
    """アップロードされた ZIP の一覧だけを読み、危険な構成を拒否する（ZIP 爆弾・パス・入れ子・件数）。"""
    import zipfile

    uploaded_file.seek(0)
    try:
        with zipfile.ZipFile(uploaded_file) as archive:
            infos = archive.infolist()
    except (zipfile.BadZipFile, OSError, ValueError):
        return 'ZIP ファイルを読み取れません（壊れているか ZIP ではありません）。'
    finally:
        uploaded_file.seek(0)
    if len(infos) > ZIP_UPLOAD_MAX_ENTRIES:
        return f'ZIP の中のファイルが多すぎます（{ZIP_UPLOAD_MAX_ENTRIES} 件まで）。'
    total = 0
    for info in infos:
        name = info.filename.replace('\\', '/')
        parts = [part for part in name.split('/') if part]
        if name.startswith('/') or re.match(r'^[A-Za-z]:', name) or '..' in parts or '\x00' in name:
            return 'ZIP の中に危険なパス（絶対パス・..）が含まれています。'
        if os.path.splitext(name)[1].lower() in NESTED_ARCHIVE_EXTENSIONS:
            return 'ZIP の中に別の圧縮ファイルが含まれています（入れ子の ZIP は登録できません）。'
        total += info.file_size
        if info.compress_size and info.file_size / info.compress_size > ZIP_UPLOAD_MAX_RATIO:
            return 'ZIP の圧縮率が異常に高いため登録できません。'
    if total > ZIP_UPLOAD_MAX_UNCOMPRESSED:
        return f'ZIP を展開した合計サイズが上限（{ZIP_UPLOAD_MAX_UNCOMPRESSED // MB}MB）を超えています。'
    return None


def zip_max_files():
    """ZIP 一括ダウンロードの上限（その場で作るため、応答時間に収まる量に限る）。"""
    return getattr(settings, 'DOCUMENT_ZIP_MAX_FILES', 100)


def zip_max_total_bytes():
    return getattr(settings, 'DOCUMENT_ZIP_MAX_TOTAL_BYTES', 200 * MB)


def policy_payload():
    """画面に知らせる上限（画面は事前確認に使うだけで、判定は後端が行う）。"""
    return {
        'max_file_bytes': max_upload_bytes(),
        'batch_max_files': batch_max_files(),
        'batch_max_total_bytes': batch_max_total_bytes(),
        'zip_max_files': zip_max_files(),
        'zip_max_total_bytes': zip_max_total_bytes(),
        'zip_upload_max_bytes': zip_upload_max_bytes(),
        'content_label_max_length': 60,
        'allowed_extensions': sorted(ALLOWED_EXTENSIONS),
    }


def filename_problem(raw_name):
    """ファイル名そのものの危険・不正（パス・制御文字・予約名・長さ）。問題なければ None。"""
    name = str(raw_name or '')
    if not name.strip():
        return 'ファイル名がありません。'
    if '/' in name or '\\' in name or '\x00' in name:
        return 'ファイル名にフォルダの区切り文字は使えません。'
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        return 'ファイル名に制御文字が含まれています。'
    if len(name) > MAX_FILENAME_LENGTH:
        return f'ファイル名が長すぎます（{MAX_FILENAME_LENGTH} 文字まで）。'
    stem, _ = os.path.splitext(name)
    if not stem.strip(' .') or name.strip() in ('.', '..'):
        return 'ファイル名が正しくありません。'
    if stem.split('.')[0].strip().lower() in RESERVED_STEMS:
        return 'この名前のファイルは登録できません（予約された名前）。'
    return None


def check_batch(files):
    """登録前の一括確認（files は [{name, size}]）。件数・合計・1 件ごとの名前・種類・大きさを見る。

    返り値：{'errors': [一覧全体の問題], 'files': [{index, name, size, problem}]}。
    中身（署名）の確認は実際の登録時に 1 件ずつ行う。
    """
    errors = []
    rows = []
    if not files:
        errors.append('ファイルが選択されていません。')
    if len(files) > batch_max_files():
        errors.append(f'一度に登録できるのは {batch_max_files()} 件までです（{len(files)} 件選択）。')
    total = 0
    for index, item in enumerate(files):
        name = str((item or {}).get('name') or '')
        try:
            size = int((item or {}).get('size') or 0)
        except (TypeError, ValueError):
            size = 0
        total += max(size, 0)
        problem = filename_problem(name)
        if problem is None:
            ext = os.path.splitext(name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                problem = f'この種類のファイル（{ext or "拡張子なし"}）は登録できません。'
            elif size <= 0:
                problem = '空のファイルは登録できません。'
            elif size > max_upload_bytes():
                problem = f'ファイルが大きすぎます（{max_upload_bytes() // MB}MB まで）。'
            elif ext == '.zip' and size > zip_upload_max_bytes():
                problem = f'ZIP ファイルは {zip_upload_max_bytes() // MB}MB までです。'
        rows.append({'index': index, 'name': name[:255], 'size': size, 'problem': problem})
    if total > batch_max_total_bytes():
        errors.append(f'合計サイズが上限（{batch_max_total_bytes() // MB}MB）を超えています。')
    return {'errors': errors, 'files': rows, 'total_bytes': total}


def validate_upload(uploaded_file):
    """問題があれば理由の文字列を返す（問題なければ None）。"""
    problem = filename_problem(uploaded_file.name)
    if problem:
        return problem
    name = os.path.basename(uploaded_file.name or '')
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f'この種類のファイル（{ext or "拡張子なし"}）は登録できません。PDF・画像・Office 文書などを選択してください。'
    if uploaded_file.size is not None and uploaded_file.size > max_upload_bytes():
        return f'ファイルが大きすぎます（{max_upload_bytes() // (1024 * 1024)}MB まで）。'
    if not uploaded_file.size:
        return '空のファイルは登録できません。'
    if ext == '.zip' and uploaded_file.size > zip_upload_max_bytes():
        return f'ZIP ファイルは {zip_upload_max_bytes() // MB}MB までです。'
    head = _read_head(uploaded_file)
    lowered = head[:16].lower()
    if any(head.startswith(p) or lowered.startswith(p.lower()) for p in DANGEROUS_PREFIXES):
        return '実行形式・スクリプトの可能性があるファイルは登録できません。'
    expected = SIGNATURES.get(ext)
    if expected and not any(head.startswith(sig) for sig in expected):
        return f'ファイルの中身が拡張子（{ext}）と一致しません。'
    if ext == '.zip':
        return zip_upload_problem(uploaded_file)
    return None


def _read_head(uploaded_file, size=16):
    uploaded_file.seek(0)
    head = uploaded_file.read(size)
    uploaded_file.seek(0)
    return head or b''


def file_metadata(uploaded_file):
    """元のファイル名・サイズ・MIME（拡張子から推定）・SHA-256。"""
    digest = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    name = os.path.basename(uploaded_file.name or '')
    guessed, _ = mimetypes.guess_type(name)
    return {
        'file_name': name[:255],
        'file_size': uploaded_file.size,
        # ブラウザが申告する content_type は信用せず、拡張子から推定する
        'content_type': guessed or 'application/octet-stream',
        'sha256': digest.hexdigest(),
    }
