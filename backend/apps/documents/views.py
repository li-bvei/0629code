import os

from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.services import record
from apps.authentication.access_policy import ALLOW, NOT_FOUND
from apps.authentication.drf import BusinessScopedViewSetMixin
from apps.timelines.models import Timeline
from apps.timelines.services import record_case_event

from .models import Document
from .protected_download import build_file_response, content_disposition, is_first_range_request, resolve_document_path
from .serializers import DocumentReplacementSerializer, DocumentSerializer
from .upload_policy import check_batch, policy_payload, zip_max_files, zip_max_total_bytes
from .zip_export import plan_entries, write_zip


class DocumentViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    """案件ファイル。権限は親 Case に従う。ダウンロード・プレビューは担当範囲内、
    または documents.document_download_all の明示付与が必要で、すべて監査する。"""

    access_resource = 'document'
    access_action_map = {
        'download': 'download', 'preview': 'download', 'history': 'view',
        # 一括登録の事前確認・上限：案件への書き込み可否は action 内で案件ごとに判定する
        'upload_policy': 'list', 'upload_check': 'list',
        # ZIP：ファイルごとの可否は action 内で 1 件ずつ判定する（モジュール権限は閲覧と同じ）
        'download_zip': 'list',
    }
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

    # --- 複数ファイルの登録（P2）：登録そのものは 1 件ずつ POST /documents/ で行う -----------------
    def _writable_case(self, case_id):
        """案件を「見える範囲」から探し、ファイルを追加できるか（担当・アーカイブ）を規則で確認する。"""
        if case_id in (None, ''):
            raise ValidationError({'case': ['案件を指定してください。']})
        case = self.business_policy.queryset('case', 'view').filter(pk=case_id).first()
        if case is None:
            raise Http404
        self.access_rule.prepare_create(self.business_policy, {'case': case})  # 書けなければ PermissionDenied
        return case

    @action(detail=False, methods=['get'], url_path='upload-policy')
    def upload_policy(self, request):
        return Response(policy_payload())

    @action(detail=False, methods=['post'], url_path='upload-check')
    def upload_check(self, request):
        """登録前の一括確認：件数・合計サイズ・1 件ごとの名前・種類・大きさ。何も保存しない。"""
        case = self._writable_case(request.data.get('case'))
        files = request.data.get('files')
        if not isinstance(files, list):
            raise ValidationError({'files': ['ファイルの一覧を指定してください。']})
        result = check_batch(files)
        rejected = [row for row in result['files'] if row['problem']]
        result.update({'case': case.pk, 'ok': not result['errors'], 'policy': policy_payload()})
        if result['errors'] or rejected:
            record(module='documents', action='document_batch_upload_rejected', request=request, obj=case,
                   result='denied', reason='；'.join(result['errors'])[:255],
                   extra={'case_id': case.pk, 'files': len(files), 'rejected': len(rejected),
                          'total_bytes': result['total_bytes']})
        return Response(result, status=200 if result['ok'] else 400)

    # --- ZIP 一括ダウンロード（P2） ------------------------------------------------------------
    @action(detail=False, methods=['post'], url_path='download-zip')
    def download_zip(self, request):
        """選んだファイル、または案件のすべてのファイルを ZIP で返す（同じ案件の中だけ）。

        ファイルごとに download 権限を判定し、権限の無いもの・他の案件のもの・実体の無いものは入れない。
        その場で作る一時ファイルで、保存しない。結果（入れた数・除いた数と理由）は監査に残す。
        """
        policy = self.business_policy
        case_id = request.data.get('case')
        if case_id in (None, ''):
            raise ValidationError({'case': ['案件を指定してください。']})
        visible = self.get_queryset().select_related(None).select_related('case')
        case = policy.queryset('case', 'view').filter(pk=case_id).first()
        if case is None:
            # 案件は範囲外でも、ファイルの全件閲覧権限（document_view_all）で見えている場合がある
            visible_document = visible.filter(case_id=case_id).first()
            case = visible_document.case if visible_document else None
        if case is None:
            raise Http404
        mode = 'all' if request.data.get('all') in (True, 'true', '1', 1) else 'selected'
        skipped = []
        if mode == 'all':
            candidates = list(visible.filter(case_id=case.pk, is_archived=False))
        else:
            raw_ids = request.data.get('ids')
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ValidationError({'ids': ['ダウンロードするファイルを選択してください。']})
            try:
                ids = sorted({int(value) for value in raw_ids})
            except (TypeError, ValueError):
                raise ValidationError({'ids': ['ファイルの指定が正しくありません。']})
            found = {doc.pk: doc for doc in visible.filter(pk__in=ids)}
            candidates = []
            for pk in ids:
                document = found.get(pk)
                if document is None:
                    skipped.append({'id': pk, 'reason': 'not_found'})
                elif document.case_id != case.pk:
                    skipped.append({'id': pk, 'reason': 'other_case'})
                else:
                    candidates.append(document)
        if len(candidates) > zip_max_files():
            return self._zip_refused(request, case, mode, 'zip_too_many_files',
                                     f'一度に ZIP にできるのは {zip_max_files()} 件までです（{len(candidates)} 件）。'
                                     'ファイルを選んで分けてダウンロードしてください。', skipped)
        included = []
        for document in candidates:
            if policy.decide('document', document, 'download') != ALLOW:
                skipped.append({'id': document.pk, 'reason': 'forbidden', 'name': document.file_name})
                continue
            try:
                real_path, _ = resolve_document_path(document)
            except (FileNotFoundError, SuspiciousFileOperation):
                skipped.append({'id': document.pk, 'reason': 'file_missing', 'name': document.file_name})
                continue
            included.append((document, real_path))
        total_bytes = sum(os.path.getsize(path) for _, path in included)
        if not included:
            return self._zip_refused(request, case, mode, 'nothing_to_download',
                                     'ダウンロードできるファイルがありません。', skipped)
        if total_bytes > zip_max_total_bytes():
            return self._zip_refused(request, case, mode, 'zip_too_large',
                                     f'合計サイズが ZIP の上限（{zip_max_total_bytes() // (1024 * 1024)}MB）を超えています。'
                                     'ファイルを選んで分けてダウンロードしてください。', skipped)
        paths = {document.pk: path for document, path in included}
        # ZIP 内の名前は、選んだ範囲ではなく案件のファイル全体（アーカイブ済みを含む）で決める（選び方で変わらない）
        universe = (visible.filter(case_id=case.pk).select_related(None).prefetch_related(None)
                    .only('id', 'category', 'file_name', 'display_name', 'title', 'file'))
        entries = [(paths[document.pk], arcname)
                   for document, arcname in plan_entries([d for d, _ in included], universe=universe)]
        report = self._zip_report(case, entries, skipped)
        handle = write_zip(entries, report)
        record(module='documents', action='document_zip_download', request=request, obj=case,
               extra={'case_id': case.pk, 'mode': mode, 'included': len(entries), 'skipped': len(skipped),
                      'skipped_reasons': self._reason_counts(skipped), 'total_bytes': total_bytes,
                      'document_ids': [document.pk for document, _ in included][:200]})
        filename = f'{case.case_number or f"case-{case.pk}"}_files_{timezone.localdate():%Y%m%d}.zip'
        response = FileResponse(handle, content_type='application/zip')
        response['Content-Disposition'] = content_disposition(filename)
        response['X-Zip-Included'] = str(len(entries))
        response['X-Zip-Skipped'] = str(len(skipped))
        response['Access-Control-Expose-Headers'] = 'X-Zip-Included, X-Zip-Skipped, Content-Disposition'
        response['Cache-Control'] = 'private, no-store'
        return response

    SKIP_LABELS = {
        'forbidden': 'ダウンロード権限がありません', 'not_found': '見つかりません（範囲外または削除済み）',
        'other_case': '別の案件のファイル', 'file_missing': 'ファイルの実体がありません',
    }

    @staticmethod
    def _reason_counts(skipped):
        counts = {}
        for row in skipped:
            counts[row['reason']] = counts.get(row['reason'], 0) + 1
        return counts

    def _zip_report(self, case, entries, skipped):
        lines = [f'案件：{case.case_number or case.pk}', f'含めたファイル：{len(entries)} 件', f'除いたファイル：{len(skipped)} 件']
        for row in skipped:
            # 見えない（範囲外）ファイルは名前を書かない
            name = f'「{row["name"]}」' if row.get('name') and row['reason'] in ('forbidden', 'file_missing') else ''
            lines.append(f'  ID {row["id"]}{name}：{self.SKIP_LABELS.get(row["reason"], row["reason"])}')
        return '\n'.join(lines) + '\n'

    def _zip_refused(self, request, case, mode, code, detail, skipped):
        record(module='documents', action='document_zip_refused', request=request, obj=case, result='error',
               reason=code, extra={'case_id': case.pk, 'mode': mode, 'skipped': len(skipped),
                                   'skipped_reasons': self._reason_counts(skipped)})
        return Response({'code': code, 'detail': detail,
                         'skipped': [{'id': r['id'], 'reason': r['reason'],
                                      'label': self.SKIP_LABELS.get(r['reason'], r['reason'])} for r in skipped]},
                        status=400)

    @action(detail=True, methods=['get'], url_path='preview')
    def preview(self, request, pk=None):
        return self._serve(request, pk, inline=True)

    # --- 監査 -------------------------------------------------------------
    def after_create(self, instance):
        record(module='documents', action='document_upload', request=self.request, obj=instance,
               extra={'case_id': instance.case_id, 'file_size': instance.file_size,
                      # P6：資料内容の出所（user＝入力、legacy_derived＝旧 API 互換で派生、legacy_no_party＝顧客・会社なし）
                      'content_label_source': getattr(instance, '_content_label_source', '') or 'user'})
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
