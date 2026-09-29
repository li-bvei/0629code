"""受保護ダウンロード：パス検証と応答の組み立て（権限判定は BusinessAccessPolicy が行う）。

- リクエストからのパスやファイル名は一切受け取らない。Document に保存された file.name を
  realpath で解決し、MEDIA_ROOT/case_documents/ 配下の通常ファイルであることを確認する。
- 本番は nginx の internal location へ X-Accel-Redirect（Range・大容量は nginx が処理）、
  開発は FileResponse。
"""
import mimetypes
import os
import re
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, HttpResponse

DOCUMENT_SUBDIR = 'case_documents'
INLINE_MIME_TYPES = {'application/pdf', 'image/png', 'image/jpeg'}


def resolve_document_path(document, subdir=DOCUMENT_SUBDIR):
    """(実パス, MEDIA_ROOT からの相対パス) を返す。範囲外・不在は例外。
    subdir は保存先の許可ディレクトリ（案件書類は case_documents、不動産ファイルは real_estate_files）。"""
    if not document.file or not document.file.name:
        raise FileNotFoundError('ファイルが登録されていません。')
    media_root = os.path.realpath(settings.MEDIA_ROOT)
    allowed_root = os.path.join(media_root, subdir)
    real = os.path.realpath(os.path.join(media_root, document.file.name))
    if not real.startswith(allowed_root + os.sep):
        raise SuspiciousFileOperation('受控ストレージ外のファイルです。')
    if not os.path.isfile(real):
        raise FileNotFoundError('ファイルが存在しません。')
    return real, os.path.relpath(real, media_root)


def display_filename(document):
    name = document.file_name or os.path.basename(document.file.name or '') or f'document-{document.pk}'
    return os.path.basename(name.replace('\\', '/'))


def content_disposition(filename, inline=False):
    """RFC 6266 / 5987：ASCII フォールバックと UTF-8 の filename* を併記する。"""
    ascii_name = re.sub(r'[^A-Za-z0-9._-]+', '_', filename).strip('._') or 'download'
    kind = 'inline' if inline else 'attachment'
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"


def guess_mime(filename):
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or 'application/octet-stream'


def build_file_response(document, real_path, rel_path, *, inline_requested=False):
    filename = display_filename(document)
    mime = guess_mime(filename)
    inline = inline_requested and mime in INLINE_MIME_TYPES
    content_type = mime if inline else (mime if mime in INLINE_MIME_TYPES else 'application/octet-stream')

    if settings.PROTECTED_MEDIA_X_ACCEL:
        response = HttpResponse(content_type=content_type)
        # 検証済みの相対パスだけから内部 URL を組み立てる（ファイル名の直接連結はしない）。
        response['X-Accel-Redirect'] = settings.PROTECTED_MEDIA_X_ACCEL_PREFIX + quote(
            rel_path.replace(os.sep, '/'), safe='/',
        )
    else:
        response = FileResponse(open(real_path, 'rb'), content_type=content_type)
        response['Content-Length'] = str(os.path.getsize(real_path))
    response['Content-Disposition'] = content_disposition(filename, inline=inline)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


def is_first_range_request(request):
    """Range 分割の2回目以降は監査を重複させない。"""
    value = request.META.get('HTTP_RANGE', '')
    return not value or value.replace(' ', '').startswith('bytes=0-')
