"""返签 visa 表 PDF の正式な生成サービス（単票の generate-pdf と一括 ZIP の共通入口）。

成功した PDF は必ず VisaReturnPdfGeneration に記録し、ファイルを保存してから使う。記録の無い PDF を
直接返す経路（旧 GET /pdf/）は廃止した。失敗も記録と監査を残す（必須項目の不足だけは記録しない）。
"""
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

from django.core.files.base import ContentFile

from apps.audit.services import record

from .models import VisaReturnPdfGeneration
from .visa_return_pdf import VisaPdfError, missing_required_fields, render_visa_return_pdf

logger = logging.getLogger(__name__)

MISSING_FIELDS_DETAIL = '必須項目が不足しているため PDF を作成できません。'


@dataclass
class GenerationOutcome:
    """generation が None のときは必須項目の不足（記録なし）。code が空なら成功。"""

    generation: Optional[VisaReturnPdfGeneration]
    code: str = ''
    detail: str = ''
    fields: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.code and self.generation is not None


def _fail(generation, request, application, code, message, fields=(), source='single'):
    generation.status = VisaReturnPdfGeneration.STATUS_FAILED
    generation.error_code, generation.error_message = code, message
    generation.details = {**(generation.details or {}), 'fields': list(fields)[:50], 'source': source}
    generation.save()
    record(module='accounting', action='visa_pdf_failed', request=request, obj=application, result='error',
           reason=message, extra={'code': code, 'generation_id': generation.pk, 'source': source})
    return GenerationOutcome(generation, code, message, list(fields))


def generate_and_record(application, *, request, source='single'):
    """PDF を生成・保存・記録する。ファイルの実在を確かめてから成功記録にする。"""
    missing = missing_required_fields(application)
    if missing:
        return GenerationOutcome(None, 'missing_fields', MISSING_FIELDS_DETAIL, missing)

    snapshot = application.guarantor_snapshot if isinstance(application.guarantor_snapshot, dict) else {}
    generation = VisaReturnPdfGeneration(
        application=application, created_by=request.user,
        guarantor_template_id=application.guarantor_template_id,
        guarantor_template_version=str(snapshot.get('template_version') or '')[:40],
        details={'source': source},
    )
    try:
        result = render_visa_return_pdf(application)
    except VisaPdfError as exc:
        return _fail(generation, request, application, exc.code, exc.message, exc.fields, source)

    generation.method = result.method
    generation.template_name, generation.template_version = result.template_name, result.template_version
    generation.file_sha256, generation.file_size = hashlib.sha256(result.content).hexdigest(), len(result.content)
    generation.details = {'stats': result.stats, 'source': source}
    # 保存先の障害（容量不足・権限など）も業務エラーとして記録し、ダウンロード先は返さない
    error = None
    try:
        generation.file.save('visa_return.pdf', ContentFile(result.content), save=False)
        if not generation.file.storage.exists(generation.file.name):
            error = ('output_missing', '生成した PDF を保存できませんでした。')
    except Exception as exc:  # noqa: BLE001 ストレージ実装ごとに例外が異なる
        logger.exception('visa PDF could not be stored (application=%s)', application.pk)
        error = ('storage_failed', f'生成した PDF を保存できませんでした（{type(exc).__name__}）。保存先の空き容量・権限を確認してください。')
    if error:
        stored_name, storage = generation.file.name, generation.file.storage
        generation.file = None
        generation.file_sha256, generation.file_size = '', None
        outcome = _fail(generation, request, application, *error, source=source)
        if stored_name:
            try:
                storage.delete(stored_name)  # 途中まで書かれたファイルを残さない
            except Exception:  # noqa: BLE001
                logger.warning('could not remove partial visa PDF %s', stored_name)
        return outcome

    generation.status = VisaReturnPdfGeneration.STATUS_SUCCESS
    try:
        generation.save()
    except Exception:
        generation.file.delete(save=False)  # 記録が残らないファイルを残さない
        raise
    record(module='accounting', action='visa_pdf_generated', request=request, obj=application,
           extra={'generation_id': generation.pk, 'method': result.method, 'template_version': result.template_version,
                  'guarantor_template_id': application.guarantor_template_id, 'source': source})
    return GenerationOutcome(generation)


def read_generated_pdf(generation):
    """成功記録のファイルを読む（一括 ZIP 用）。読めなければ VisaPdfError（file_missing）。"""
    try:
        with generation.file.storage.open(generation.file.name, 'rb') as handle:
            return handle.read()
    except Exception as exc:  # noqa: BLE001
        logger.exception('visa PDF could not be read back (generation=%s)', generation.pk)
        raise VisaPdfError('file_missing', '保存した PDF を読み出せませんでした。') from exc
