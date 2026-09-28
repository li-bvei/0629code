"""案件ファイルのアップロード検査（種類・サイズ・ファイル署名）とメタデータ算出。

ウイルス対策ソフトによる検査は行っていない。そのため、許可する拡張子を限定し、主要形式は
先頭バイト（署名）と拡張子の一致を確認し、実行形式・スクリプトは受け付けない。
"""
import hashlib
import mimetypes
import os

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


def max_upload_bytes():
    return getattr(settings, 'DOCUMENT_MAX_UPLOAD_BYTES', 20 * 1024 * 1024)


def validate_upload(uploaded_file):
    """問題があれば理由の文字列を返す（問題なければ None）。"""
    name = os.path.basename(uploaded_file.name or '')
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f'この種類のファイル（{ext or "拡張子なし"}）は登録できません。PDF・画像・Office 文書などを選択してください。'
    if uploaded_file.size is not None and uploaded_file.size > max_upload_bytes():
        return f'ファイルが大きすぎます（{max_upload_bytes() // (1024 * 1024)}MB まで）。'
    if not uploaded_file.size:
        return '空のファイルは登録できません。'
    head = _read_head(uploaded_file)
    lowered = head[:16].lower()
    if any(head.startswith(p) or lowered.startswith(p.lower()) for p in DANGEROUS_PREFIXES):
        return '実行形式・スクリプトの可能性があるファイルは登録できません。'
    expected = SIGNATURES.get(ext)
    if expected and not any(head.startswith(sig) for sig in expected):
        return f'ファイルの中身が拡張子（{ext}）と一致しません。'
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
