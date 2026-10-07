"""案件ファイルの ZIP 一括ダウンロード（P2）。

- ZIP はその場で一時ファイルに作り、応答を返し終えたら消える（業務ファイルとして保存しない）。
- ZIP 内の場所は「資料分類/ファイル名」。ファイル名は元の名前から危険な文字・パスを除いたもの。
- 同じフォルダに同じ名前が複数あるとき（大文字小文字は区別しない）、案件のファイル全体の中で ID が最も小さい
  ものは元の名前のまま、ほかは「名前 (ID 123).拡張子」にする。名前は選んだ範囲ではなく案件全体で決める
  （plan_names）ので、どれを選んでも同じファイルは同じ名前になる。
- 権限・範囲の判定は呼び出し側（ViewSet）が BusinessAccessPolicy で 1 件ずつ行う。ここは並べて書くだけ。
"""
import os
import re
import tempfile
import unicodedata
import zipfile

from .models import Document

CATEGORY_LABELS = dict(Document.CATEGORY_CHOICES)
# すでに圧縮された形式は再圧縮しない（時間がかかるだけで小さくならない）
STORED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.heic', '.webp', '.zip', '.docx', '.xlsx', '.pptx'}
UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')
MAX_NAME_LENGTH = 150


def safe_component(value, fallback):
    """ZIP 内で使える 1 段分の名前（区切り文字・制御文字・先頭の点や空白・.. を除く）。"""
    text = unicodedata.normalize('NFC', str(value or ''))
    text = os.path.basename(text.replace('\\', '/'))
    text = UNSAFE_CHARS.sub('_', text).strip(' .')
    if not text or set(text) <= {'_'}:
        text = fallback
    stem, ext = os.path.splitext(text)
    if len(text) > MAX_NAME_LENGTH:
        ext = ext[:10]
        text = stem[:MAX_NAME_LENGTH - len(ext)] + ext
    return text


def document_zip_name(document):
    # P6：単体ダウンロードと同じ名前（表示名があればそれ、旧データは元のファイル名）
    from .naming import download_name

    ext = os.path.splitext(document.file_name or document.file.name or '')[1].lower()[:10]
    return safe_component(download_name(document) or document.title, f'document-{document.pk}{ext}')


def category_folder(document):
    return safe_component(CATEGORY_LABELS.get(document.category, document.category), 'その他')


def plan_names(universe):
    """案件のファイル全体（universe）について {ID: ZIP 内パス} を決める。

    名前は選んだファイルではなく案件全体で決めるので、どのファイルを選んでも同じファイルは同じ名前になり、
    どの組み合わせを選んでも衝突しない。
    1. 同じフォルダ・同じ名前（大文字小文字を区別しない）の中で ID が最小のものだけが元の名前を使う。
    2. ほかは ID の小さい順に「名前 (ID n).拡張子」。それが既にある名前と重なる特殊な場合だけ「名前 (ID n-2).拡張子」…。
    """
    ordered = sorted(universe, key=lambda d: d.pk)
    planned = {}
    used = set()
    seen_groups = set()
    renamed = []
    for document in ordered:
        folder, name = category_folder(document), document_zip_name(document)
        group = (folder.casefold(), name.casefold())
        if group in seen_groups:
            renamed.append((document, folder, name))
            continue
        seen_groups.add(group)
        planned[document.pk] = f'{folder}/{name}'
        used.add(planned[document.pk].casefold())
    for document, folder, name in renamed:
        stem, ext = os.path.splitext(name)
        candidate, attempt = f'{folder}/{stem} (ID {document.pk}){ext}', 1
        while candidate.casefold() in used:
            attempt += 1
            candidate = f'{folder}/{stem} (ID {document.pk}-{attempt}){ext}'
        planned[document.pk] = candidate
        used.add(candidate.casefold())
    return planned


def plan_entries(documents, universe=None):
    """[(document, ZIP 内パス)] を返す（パス順）。

    universe は名前を決める範囲（通常は利用者が見られる案件のファイル全体）。省略時は documents だけで決める。
    """
    documents = list(documents)
    names = plan_names(list(universe) if universe is not None else documents)
    missing = [document for document in documents if document.pk not in names]
    if missing:  # universe に無いものが渡された場合も名前が決まるようにする
        names = plan_names([*(universe or []), *missing])
    return sorted(((document, names[document.pk]) for document in documents), key=lambda item: item[1])


def write_zip(entries, report_text):
    """一時ファイル（一定サイズまではメモリ）へ ZIP を書き、先頭へ戻して返す。"""
    handle = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
    with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for real_path, arcname in entries:
            ext = os.path.splitext(arcname)[1].lower()
            compress = zipfile.ZIP_STORED if ext in STORED_EXTENSIONS else zipfile.ZIP_DEFLATED
            archive.write(real_path, arcname=arcname, compress_type=compress)
        archive.writestr('ダウンロード結果.txt', report_text)
    handle.seek(0)
    return handle
