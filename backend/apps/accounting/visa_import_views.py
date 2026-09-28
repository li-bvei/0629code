"""返签 visa 表の一括取込 API（accounting/vouchers の Visa 機能の一部。権限は accounting.use_visa）。"""
import io
import re
import zipfile

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.audit.services import record
from apps.authentication.drf import BusinessScopedViewSetMixin

from .models import VisaImportBatch, VisaReturnApplication
from .serializers import VisaReturnApplicationSerializer
from .visa_import import (
    FIELD_KEYS,
    FIELD_META,
    VisaImportError,
    auto_mapping,
    error_report_csv,
    file_sha256,
    read_upload,
    template_csv,
    to_application_payload,
    validate_rows,
)
from .visa_return_pdf import build_visa_return_pdf_filename, generate_visa_return_pdf


def _attachment(content, filename, content_type):
    from urllib.parse import quote

    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f"attachment; filename=\"download\"; filename*=UTF-8''{quote(filename)}"
    response['Cache-Control'] = 'private, no-store'
    return response


def _batch_summary(batch):
    return {
        'batch_id': batch.id,
        'file_name': batch.file_name,
        'status': batch.status,
        'mode': batch.mode,
        'row_count': batch.row_count,
        'success_count': batch.success_count,
        'error_count': batch.error_count,
        'skipped_count': batch.skipped_count,
    }


class VisaImportViewSet(BusinessScopedViewSetMixin, GenericViewSet):
    access_resource = 'visa'
    access_action_map = {'template': 'view', 'error_report': 'export', 'pdf_zip': 'export'}
    queryset = VisaImportBatch.objects.all()
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _input(self, request):
        mapping = request.data.get('mapping') or {}
        rows = request.data.get('rows') or []
        shared = request.data.get('shared') or {}
        if not isinstance(mapping, dict) or not isinstance(rows, list) or not isinstance(shared, dict):
            raise VisaImportError('mapping / rows / shared の形式が正しくありません。')
        mapping = {str(k): (v or '') for k, v in mapping.items() if not v or v in FIELD_META}
        return mapping, rows, shared

    def _error(self, exc):
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='template')
    def template(self, request):
        return _attachment(template_csv(), '返签visa表_取込テンプレート.csv', 'text/csv; charset=utf-8')

    @action(detail=False, methods=['post'], url_path='parse')
    def parse(self, request):
        upload = request.FILES.get('file')
        if upload is None:
            return Response({'file': ['ファイルを選択してください。']}, status=status.HTTP_400_BAD_REQUEST)
        content = upload.read()
        try:
            table = read_upload(upload.name, content, sheet_name=request.data.get('sheet') or None,
                                encoding=request.data.get('encoding') or None)
        except VisaImportError as exc:
            return self._error(exc)
        digest = file_sha256(content)
        previous = list(
            VisaImportBatch.objects.filter(file_sha256=digest, success_count__gt=0).values('id', 'created_at', 'success_count')
        )
        batch = VisaImportBatch.objects.create(
            created_by=request.user, file_name=upload.name[:255], file_sha256=digest,
            sheet_name=table['sheet_name'], encoding=table['encoding'], row_count=len(table['rows']),
            column_mapping=auto_mapping(table['headers']),
        )
        record(module='accounting', action='visa_import_parse', request=request, obj=batch,
               extra={'file_name': upload.name, 'rows': len(table['rows']), 'sha256': digest,
                      'duplicate_file': bool(previous)})
        return Response({
            **_batch_summary(batch),
            'headers': table['headers'],
            'rows': table['rows'],
            'mapping': batch.column_mapping,
            'fields': [{'key': k, **FIELD_META[k]} for k in FIELD_KEYS],
            'sheets': table['sheets'],
            'sheet_name': table['sheet_name'],
            'encoding': table['encoding'],
            'blank_rows_skipped': table['blank_rows_skipped'],
            'duplicate_file': bool(previous),
            'previous_batches': previous,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='preview')
    def preview(self, request, pk=None):
        batch = self.get_object()
        try:
            mapping, rows, shared = self._input(request)
            results = validate_rows(rows, mapping, shared)
        except VisaImportError as exc:
            return self._error(exc)
        batch.column_mapping = mapping
        batch.save(update_fields=['column_mapping', 'updated_at'])
        created = {k for k, v in (batch.results or {}).items() if v.get('status') == 'created'}
        for result in results:
            result['already_created'] = str(result['row_number']) in created
        return Response({
            **_batch_summary(batch),
            'results': results,
            'valid_count': sum(1 for r in results if not r['errors']),
            'error_count': sum(1 for r in results if r['errors']),
            'duplicate_count': sum(1 for r in results if any(w['code'] == 'duplicate_existing' for w in r['warnings'])),
        })

    @action(detail=True, methods=['post'], url_path='commit')
    def commit(self, request, pk=None):
        batch = self.get_object()
        request_id = str(request.data.get('request_id') or '').strip()[:100]
        if request_id and request_id in (batch.committed_request_ids or []):
            # 同じ操作の再送：何も作らずに現在の結果を返す。
            return Response({**_batch_summary(batch), 'results': batch.results, 'replayed': True})
        mode = request.data.get('mode') or VisaImportBatch.MODE_VALID_ONLY
        if mode not in dict(VisaImportBatch.MODE_CHOICES):
            return Response({'mode': ['作成方式が正しくありません。']}, status=status.HTTP_400_BAD_REQUEST)
        skip_duplicates = str(request.data.get('skip_duplicates', 'true')).lower() not in ('0', 'false', 'no')
        try:
            mapping, rows, shared = self._input(request)
            results = validate_rows(rows, mapping, shared)
        except VisaImportError as exc:
            return self._error(exc)

        stored = dict(batch.results or {})
        pending = [r for r in results if stored.get(str(r['row_number']), {}).get('status') != 'created']
        errors = [r for r in pending if r['errors']]
        if mode == VisaImportBatch.MODE_ALL_OR_NOTHING and errors:
            for r in errors:
                stored[str(r['row_number'])] = {'status': 'error', 'errors': r['errors']}
            batch.results, batch.mode = stored, mode
            batch.error_count = sum(1 for v in stored.values() if v.get('status') == 'error')
            batch.save(update_fields=['results', 'mode', 'error_count', 'updated_at'])
            record(module='accounting', action='visa_import_commit', request=request, obj=batch, result='denied',
                   extra={'mode': mode, 'errors': len(errors), 'created': 0})
            return Response({**_batch_summary(batch), 'results': stored,
                             'detail': '誤りのある行があるため、何も作成しませんでした。'},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            batch = VisaImportBatch.objects.select_for_update().get(pk=batch.pk)
            stored = dict(batch.results or {})
            for r in pending:
                key = str(r['row_number'])
                if stored.get(key, {}).get('status') == 'created':
                    continue
                if r['errors']:
                    stored[key] = {'status': 'error', 'errors': r['errors']}
                    continue
                duplicate = next((w for w in r['warnings'] if w['code'] == 'duplicate_existing'), None)
                if duplicate and skip_duplicates:
                    stored[key] = {'status': 'skipped_duplicate', 'existing_ids': duplicate.get('existing_ids', [])}
                    continue
                serializer = VisaReturnApplicationSerializer(data=to_application_payload(r['values']))
                if not serializer.is_valid():
                    stored[key] = {'status': 'error', 'errors': [
                        {'field': field, 'label': FIELD_META.get(field, {}).get('label', field),
                         'raw': r['raw'].get(field, ''), 'message': '；'.join(str(m) for m in messages)}
                        for field, messages in serializer.errors.items()
                    ]}
                    continue
                application = serializer.save(created_by=request.user, import_batch=batch, import_row_number=r['row_number'])
                stored[key] = {'status': 'created', 'application_id': application.id}
            batch.results = stored
            batch.mode = mode
            batch.column_mapping = mapping
            batch.success_count = sum(1 for v in stored.values() if v.get('status') == 'created')
            batch.error_count = sum(1 for v in stored.values() if v.get('status') == 'error')
            batch.skipped_count = sum(1 for v in stored.values() if v.get('status') == 'skipped_duplicate')
            batch.status = VisaImportBatch.STATUS_COMPLETED if batch.error_count == 0 else VisaImportBatch.STATUS_PARTIAL
            if request_id:
                batch.committed_request_ids = [*(batch.committed_request_ids or []), request_id][-50:]
            batch.save()
            record(module='accounting', action='visa_import_commit', request=request, obj=batch,
                   extra={'mode': mode, 'created': batch.success_count, 'errors': batch.error_count,
                          'skipped': batch.skipped_count})
        return Response({**_batch_summary(batch), 'results': batch.results})

    @action(detail=True, methods=['get'], url_path='error-report')
    def error_report(self, request, pk=None):
        batch = self.get_object()
        record(module='accounting', action='visa_import_error_report', request=request, obj=batch,
               extra={'errors': batch.error_count})
        return _attachment(error_report_csv(batch.results or {}), f'返签visa表_取込エラー_{batch.id}.csv',
                           'text/csv; charset=utf-8')

    @action(detail=True, methods=['post'], url_path='pdf-zip')
    def pdf_zip(self, request, pk=None):
        batch = self.get_object()
        applications = VisaReturnApplication.objects.filter(import_batch=batch).order_by('import_row_number', 'id')
        ids = request.data.get('application_ids')
        if isinstance(ids, list) and ids:
            applications = applications.filter(id__in=ids)
        applications = list(applications)
        if not applications:
            return Response({'detail': 'PDF にする申請がありません。'}, status=status.HTTP_400_BAD_REQUEST)
        buffer = io.BytesIO()
        failures = []
        used_names = set()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for application in applications:
                try:
                    content = generate_visa_return_pdf(application)
                except Exception as exc:  # テンプレート不足など：他の申請は続ける
                    failures.append(f'{application.import_row_number}行目（ID {application.id}）：{exc}')
                    continue
                base = re.sub(r'[\\/:*?"<>|]', '_', build_visa_return_pdf_filename(application))
                name = f'{application.import_row_number or 0:03d}_{base}'
                while name in used_names:
                    name = f'{application.id}_{name}'
                used_names.add(name)
                archive.writestr(name, content)
            summary = [f'作成：{len(applications) - len(failures)} 件', f'失敗：{len(failures)} 件', *failures]
            archive.writestr('結果.txt', '\n'.join(summary))
        record(module='accounting', action='visa_pdf_zip_export', request=request, obj=batch,
               extra={'count': len(applications) - len(failures), 'failed': len(failures)})
        response = _attachment(buffer.getvalue(), f'返签visa表_{batch.id}_{timezone.localdate():%Y%m%d}.zip',
                               'application/zip')
        response['X-Success-Count'] = str(len(applications) - len(failures))
        response['X-Failure-Count'] = str(len(failures))
        return response
