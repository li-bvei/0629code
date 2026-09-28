from django.core.exceptions import SuspiciousFileOperation
from django.http import Http404
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.services import record
from apps.authentication.access_policy import ALLOW, NOT_FOUND
from apps.authentication.drf import BusinessScopedViewSetMixin
from apps.timelines.models import Timeline
from apps.timelines.services import record_case_event

from .models import Document
from .protected_download import build_file_response, is_first_range_request, resolve_document_path
from .serializers import DocumentReplacementSerializer, DocumentSerializer


class DocumentViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    """案件ファイル。権限は親 Case に従う。ダウンロード・プレビューは担当範囲内、
    または documents.document_download_all の明示付与が必要で、すべて監査する。"""

    access_resource = 'document'
    access_action_map = {'download': 'download', 'preview': 'download', 'history': 'view'}
    queryset = Document.objects.select_related('case', 'uploaded_by', 'archived_by').prefetch_related('checklist_items')
    serializer_class = DocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        case_id = params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        if params.get('category'):
            queryset = queryset.filter(category=params['category'])
        # 一覧の既定ではアーカイブ済みを隠す（詳細・ダウンロードは可能）
        archived = params.get('archived')
        if archived in ('1', 'true', 'only'):
            queryset = queryset.filter(is_archived=True)
        elif archived not in ('all',) and self.action == 'list':
            queryset = queryset.filter(is_archived=False)
        return queryset

    def perform_create(self, serializer):
        item = serializer.validated_data.get('_checklist_item_obj')
        super().perform_create(serializer)
        if item is not None:
            self._link_checklist_item(serializer.instance, item)

    def perform_update(self, serializer):
        item = serializer.validated_data.get('_checklist_item_obj')
        self._perform_update_with_audit(serializer)
        if item is not None:
            self._link_checklist_item(serializer.instance, item)

    def _link_checklist_item(self, document, item):
        """登録したファイルを同じ案件の必要資料に関連付ける（受領日は資料受領操作で記録する）。"""
        item.document = document
        item.save(update_fields=['document', 'updated_at'])
        record(module='documents', action='document_checklist_linked', request=self.request, obj=document,
               extra={'case_id': document.case_id, 'checklist_item_id': item.id})

    # --- アーカイブ・復元・差し替え履歴 ---------------------------------------------------
    @action(detail=True, methods=['post'], url_path='archive')
    def archive(self, request, pk=None):
        document = self.get_object()
        if document.is_archived:
            return Response({'detail': '既にアーカイブされています。'}, status=400)
        reason = str(request.data.get('reason') or '').strip()[:255]
        with transaction.atomic():
            document.is_archived = True
            document.archived_at = timezone.now()
            document.archived_by = request.user
            document.archive_reason = reason
            document.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'archive_reason', 'updated_at'])
            record_case_event(document.case, Timeline.EVENT_DOCUMENT_ARCHIVED, f'ファイルをアーカイブ：{document.title}',
                              description=f'理由：{reason}' if reason else '', actor=request.user,
                              metadata={'document_id': document.pk})
            record(module='documents', action='document_archive', request=request, obj=document,
                   reason=reason, extra={'case_id': document.case_id})
        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['post'], url_path='restore')
    def restore(self, request, pk=None):
        document = self.get_object()
        if not document.is_archived:
            return Response({'detail': 'アーカイブされていません。'}, status=400)
        with transaction.atomic():
            document.is_archived = False
            document.archived_at = None
            document.archived_by = None
            document.archive_reason = ''
            document.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'archive_reason', 'updated_at'])
            record_case_event(document.case, Timeline.EVENT_DOCUMENT_RESTORED, f'ファイルを復元：{document.title}',
                              actor=request.user, metadata={'document_id': document.pk})
            record(module='documents', action='document_restore', request=request, obj=document,
                   extra={'case_id': document.case_id})
        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        document = self.get_object()
        return Response(DocumentReplacementSerializer(document.replacements.select_related('replaced_by'), many=True).data)

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

    def _perform_update_with_audit(self, serializer):
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
