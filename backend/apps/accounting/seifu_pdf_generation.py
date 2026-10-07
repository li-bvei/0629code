"""清風合格通知書 PDF の正式な生成サービス（P5）。

順序：入力の検証 → 一時的にメモリ上で PDF を作って検証（seifu_notice_pdf）→ 保存先へ書き込み → 実在とサイズを
確かめる → 成功記録を作る。どこで失敗しても成功記録は作らず、途中まで書いたファイルは消し、監査に失敗を残す。

同じ記録への生成は行ロックで順番に処理する。画面の 1 回の操作ごとの request_id が既に成功していれば、
もう一度作らずに同じ生成結果を返す（二重クリック・再送で区別できない記録を増やさない）。
"""
import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Optional

from django.core.files.base import ContentFile
from django.db import transaction

from apps.audit.services import record

from .models import SeifuNoticePdfGeneration, SeifuNoticePdfRecord
from .seifu_notice_pdf import GENERATION_METHOD, TEMPLATE_KEY, SeifuPdfError, render_seifu_notice_pdf

logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r'[A-Za-z0-9_-]{8,64}')


@dataclass
class GenerationOutcome:
    generation: Optional[SeifuNoticePdfGeneration] = None
    error: Optional[SeifuPdfError] = None
    replayed: bool = False

    @property
    def ok(self):
        return self.error is None and self.generation is not None


def _fail(request, record_obj, exc):
    record(module='accounting', action='seifu_notice_pdf_failed', request=request, obj=record_obj, result='error',
           reason=exc.message, extra={'code': exc.code})
    return GenerationOutcome(error=exc)


def normalize_request_id(value):
    value = str(value or '').strip()
    if not value:
        return None
    if not REQUEST_ID_PATTERN.fullmatch(value):
        raise SeifuPdfError('invalid_request_id', '操作 ID の形式が正しくありません。画面を更新してください。')
    return value


def _store(content):
    """保存して実在・サイズを確かめる。失敗したら書いたファイルを消して SeifuPdfError。戻り値は FieldFile 用の名前。"""
    field = SeifuNoticePdfGeneration._meta.get_field('file')
    storage = field.storage
    name = None
    try:
        name = storage.save(field.generate_filename(None, 'seifu_notice.pdf'), ContentFile(content))
        if not storage.exists(name) or storage.size(name) != len(content):
            raise OSError('stored file missing or truncated')
        return name
    except Exception as exc:  # noqa: BLE001 ストレージ実装ごとに例外が異なる
        logger.exception('seifu PDF could not be stored')
        if name:
            try:
                storage.delete(name)  # 途中まで書かれたファイルを残さない
            except Exception:  # noqa: BLE001
                logger.warning('could not remove partial seifu PDF %s', name)
        raise SeifuPdfError('storage_failed', '生成した PDF を保存できませんでした。保存先の空き容量・権限を確認して、もう一度お試しください。') from exc


def generate_and_store(record_obj, *, request, request_id=None):
    try:
        request_id = normalize_request_id(request_id)
    except SeifuPdfError as exc:
        return GenerationOutcome(error=exc)
    stored_name = None
    try:
        with transaction.atomic():
            # 同じ記録への生成を順番に処理する（記録の内容も最新を読む）
            locked = SeifuNoticePdfRecord.objects.select_for_update().get(pk=record_obj.pk)  # access-reviewed: 権限確認済みの同じ記録をロックする
            if request_id:
                existing = SeifuNoticePdfGeneration.objects.filter(request_id=request_id).first()
                if existing is not None:
                    if existing.record_id != locked.pk:
                        raise SeifuPdfError('invalid_request_id', '操作 ID が別の記録で使われています。画面を更新してください。')
                    return GenerationOutcome(generation=existing, replayed=True)
            result = render_seifu_notice_pdf(locked.recipient_name, locked.permit_number, locked.issue_date)
            stored_name = _store(result.content)
            generation = SeifuNoticePdfGeneration(
                record=locked, request_id=request_id, recipient_name=result.recipient_name,
                permit_number=result.permit_number, notice_number=result.notice_number, issue_date=result.issue_date,
                template_key=locked.template_key or TEMPLATE_KEY, template_version=result.template_version,
                font_version=result.font_version, method=GENERATION_METHOD,
                file_sha256=hashlib.sha256(result.content).hexdigest(), file_size=len(result.content),
                created_by=request.user,
            )
            generation.file.name = stored_name
            generation.save()
    except SeifuPdfError as exc:
        _cleanup(stored_name)
        return _fail(request, record_obj, exc)
    except Exception:
        _cleanup(stored_name)  # 記録が残らないファイルを残さない
        logger.exception('seifu PDF generation failed unexpectedly (record=%s)', record_obj.pk)
        return _fail(request, record_obj, SeifuPdfError('generation_failed', '合格通知書 PDF の作成中にエラーが発生しました。'))
    record(module='accounting', action='seifu_notice_pdf_generated', request=request, obj=record_obj,
           extra={'generation_id': generation.pk, 'template_key': generation.template_key,
                  'template_version': generation.template_version, 'font_version': generation.font_version,
                  'file_size': generation.file_size, 'file_sha256': generation.file_sha256[:16]})
    return GenerationOutcome(generation=generation)


def _cleanup(name):
    if not name:
        return
    storage = SeifuNoticePdfGeneration._meta.get_field('file').storage
    try:
        storage.delete(name)
    except Exception:  # noqa: BLE001
        logger.warning('could not remove seifu PDF %s', name)


def open_generated_pdf(generation):
    """成功記録のファイルを開く。実在しない・読めない場合は None。"""
    if generation.status != SeifuNoticePdfGeneration.STATUS_SUCCESS or not generation.file:
        return None
    try:
        storage = generation.file.storage
        if not storage.exists(generation.file.name):
            return None
        return storage.open(generation.file.name, 'rb')
    except Exception:  # noqa: BLE001 保存先に読めない場合も「ファイルが無い」として扱う
        logger.exception('seifu PDF could not be opened (generation=%s)', generation.pk)
        return None
