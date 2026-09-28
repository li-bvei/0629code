from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet

from apps.audit.services import record
from apps.authentication.access_policy import ALLOW, NOT_FOUND
from apps.authentication.drf import BusinessScopedViewSetMixin
from apps.timelines.models import Timeline
from apps.timelines.services import record_case_event

from .models import Document
from .protected_download import build_file_response, is_first_range_request, resolve_document_path
from .serializers import DocumentSerializer


class DocumentViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    """案件ファイル。権限は親 Case に従う。ダウンロード・プレビューは担当範囲内、
    または documents.document_download_all の明示付与が必要で、すべて監査する。"""

    access_resource = 'document'
    access_action_map = {'download': 'download', 'preview': 'download'}
    queryset = Document.objects.select_related('case')
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        case_id = self.request.query_params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        return queryset

    # --- 受保護ダウンロード ---------------------------------------------------
    def _serve(self, request, pk, *, inline):
        mode = 'preview' if inline else 'download'
        policy = self.business_policy
        audit = is_first_range_request(request)
        document = self.get_queryset().filter(pk=pk).first()
        decision = NOT_FOUND if document is None else policy.decide('document', document, 'download')
        if decision != ALLOW:
            record(module='documents', action='download_denied', request=request, obj=document,
                   object_type='' if document else 'documents.document', object_id='' if document else str(pk),
                   result='denied', reason=decision, extra={'mode': mode})
            if decision == NOT_FOUND:
                raise Http404
            raise PermissionDenied('このファイルをダウンロードする権限がありません。')

        via = policy.via('document', 'download', document)
        if audit:
            record(module='documents', action='download_authorized', request=request, obj=document,
                   via_permission=via, extra={'mode': mode, 'case_id': document.case_id})
        try:
            real_path, rel_path = resolve_document_path(document)
        except (FileNotFoundError, SuspiciousFileOperation) as exc:
            record(module='documents', action='download_error', request=request, obj=document,
                   result='error', reason=str(exc), extra={'mode': mode})
            raise Http404 from exc
        response = build_file_response(document, real_path, rel_path, inline_requested=inline)
        if audit:
            # X-Accel-Redirect を返した／送信を開始したことだけを記録する（完了は証明できない）。
            record(module='documents', action='download_started', request=request, obj=document,
                   via_permission=via, extra={'mode': mode, 'case_id': document.case_id,
                                              'file_size': document.file_size})
        return response

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        return self._serve(request, pk, inline=False)

    @action(detail=True, methods=['get'], url_path='preview')
    def preview(self, request, pk=None):
        return self._serve(request, pk, inline=True)

    # --- 監査 -------------------------------------------------------------
    def after_create(self, instance):
        record(module='documents', action='document_upload', request=self.request, obj=instance,
               extra={'case_id': instance.case_id, 'file_size': instance.file_size})
        if instance.file:
            record_case_event(
                instance.case, Timeline.EVENT_DOCUMENT_UPLOADED, f'ファイル登録：{instance.title}',
                description=f'ファイル名：{instance.file_name}', actor=self.request.user,
                metadata={'document_id': instance.pk},
            )

    def perform_update(self, serializer):
        previous_file = serializer.instance.file.name if serializer.instance.file else ''
        super().perform_update(serializer)
        instance = serializer.instance
        current_file = instance.file.name if instance.file else ''
        action_name = 'document_replace' if current_file != previous_file else 'document_update'
        record(module='documents', action=action_name, request=self.request, obj=instance,
               extra={'case_id': instance.case_id})
        if action_name == 'document_replace' and current_file:
            record_case_event(
                instance.case, Timeline.EVENT_DOCUMENT_UPLOADED, f'ファイル差し替え：{instance.title}',
                description=f'ファイル名：{instance.file_name}', actor=self.request.user,
                metadata={'document_id': instance.pk, 'replaced': True},
            )

    def perform_destroy(self, instance):
        record(module='documents', action='document_delete', request=self.request, obj=instance,
               extra={'case_id': instance.case_id, 'file_name': instance.file_name})
        instance.delete()
