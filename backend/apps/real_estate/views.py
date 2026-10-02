"""不動産 API。範囲・権限は BusinessAccessPolicy（access_rules の real_estate* 規則）が決める。"""
import csv
import io

from django.core.exceptions import SuspiciousFileOperation
from django.db import transaction as db_transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.models import AuditLog
from apps.audit.services import record, safe_changes
from apps.authentication.access_policy import ALLOW
from apps.authentication.drf import BusinessScopedViewSetMixin
from apps.documents.protected_download import build_file_response, is_first_range_request, resolve_document_path

from . import bulk_service, ledger_service
from .history import TRANSACTION_FIELDS, serialize_history, transaction_changes, transaction_values
from .models import (
    REAL_ESTATE_FILE_SUBDIR,
    InternalProfitDistribution,
    LegalLedger,
    RealEstateAccountingLink,
    RealEstateFile,
    RealEstateTransaction,
    TransactionParty,
)
from .serializers import (
    InternalProfitDistributionSerializer,
    LedgerCorrectionInputSerializer,
    LegalLedgerCorrectionSerializer,
    LegalLedgerSerializer,
    RealEstateAccountingLinkSerializer,
    RealEstateFileSerializer,
    RealEstateTransactionSerializer,
    TransactionPartySerializer,
)

AUDIT_MODULE = 'real_estate'
PARTY_HISTORY_FIELDS = ('role', 'name', 'address', 'license_number', 'note')


def _audit(request, obj, action, **kwargs):
    record(module=AUDIT_MODULE, action=action, request=request, obj=obj, **kwargs)


class TransactionFilterMixin:
    """?transaction= で親取引を絞る子資源用。"""

    def filter_transaction(self, queryset):
        tx = self.request.query_params.get('transaction')
        return queryset.filter(transaction_id=tx) if tx else queryset


class RealEstateTransactionViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'real_estate'
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    access_action_map = {
        'ensure_ledger': 'ledger', 'audit_log': 'view', 'archive': 'archive', 'restore': 'restore',
        'export': 'export', 'responsible_suggestions': 'view',
        'bulk_preview': 'bulk_change', 'bulk_update': 'bulk_change',
    }
    queryset = RealEstateTransaction.objects.select_related('customer', 'management_company', 'legal_ledger')
    serializer_class = RealEstateTransactionSerializer

    def get_queryset(self):
        p = self.request.query_params
        qs = bulk_service.apply_filters(super().get_queryset(), p)
        if self.action == 'list':
            archive_status = p.get('archive_status', 'active')
            if archive_status == 'active':
                qs = qs.filter(is_archived=False)
            elif archive_status == 'archived':
                qs = qs.filter(is_archived=True)
        return qs.order_by('-created_at', '-id')

    def perform_create(self, serializer):
        self._history_fields = set(serializer.validated_data) & set(TRANSACTION_FIELDS)
        super().perform_create(serializer)

    def after_create(self, instance):
        after = transaction_values(instance, self._history_fields)
        _audit(self.request, instance, 'transaction_created', object_repr=instance.transaction_number,
               changes=safe_changes({}, after))

    def perform_update(self, serializer):
        self._history_fields = set(serializer.validated_data) & set(transaction_values(serializer.instance).keys())
        self._history_before = transaction_values(serializer.instance, self._history_fields)
        super().perform_update(serializer)

    def after_update(self, instance):
        changes = transaction_changes(self._history_before, transaction_values(instance, self._history_fields))
        if changes:
            _audit(self.request, instance, 'transaction_updated', object_repr=instance.transaction_number,
                   changes=changes)

    @action(detail=True, methods=['post'])
    @db_transaction.atomic
    def archive(self, request, pk=None):
        tx = self.get_object()
        if tx.is_archived:
            raise ValidationError({'detail': '既にアーカイブ済みです。'})
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            raise ValidationError({'reason': 'アーカイブ理由を入力してください。'})
        tx.is_archived = True
        tx.archived_at = timezone.now()
        tx.archived_by = request.user
        tx.archive_reason = reason
        tx.restored_at = None
        tx.restored_by = None
        tx.updated_by = request.user
        tx.save(update_fields=['is_archived', 'archived_at', 'archived_by', 'archive_reason', 'restored_at',
                               'restored_by', 'updated_by', 'updated_at'])
        _audit(request, tx, 'transaction_archived', object_repr=tx.transaction_number, reason=reason,
               changes={'archive_state': {'from': '有効', 'to': 'アーカイブ'}})
        return Response(self.get_serializer(tx).data)

    @action(detail=True, methods=['post'])
    @db_transaction.atomic
    def restore(self, request, pk=None):
        tx = self.get_object()
        if not tx.is_archived:
            raise ValidationError({'detail': 'アーカイブされていません。'})
        previous_reason = tx.archive_reason
        tx.is_archived = False
        tx.restored_at = timezone.now()
        tx.restored_by = request.user
        tx.updated_by = request.user
        tx.save(update_fields=['is_archived', 'restored_at', 'restored_by', 'updated_by', 'updated_at'])
        _audit(request, tx, 'transaction_restored', object_repr=tx.transaction_number, reason=previous_reason,
               changes={'archive_state': {'from': 'アーカイブ', 'to': '有効'}})
        return Response(self.get_serializer(tx).data)

    @action(detail=False, methods=['post'], url_path='bulk-preview')
    def bulk_preview(self, request):
        """対象（絞り込み結果の全件、または一覧で選択した記録）と各記録の版を固定した短期トークンを返す。
        書き込みはしない。一括変更はこのトークンでしか実行できない。"""
        queryset = self.business_policy.queryset('real_estate', 'bulk_change')
        return Response(bulk_service.issue_selection_token(queryset, request.data, request.user))

    @action(detail=False, methods=['post'], url_path='bulk-update')
    def bulk_update(self, request):
        """段階・担当者・取引日の一括変更。全件成功か全件中止のどちらか（部分的な書き込みはしない）。"""
        policy = self.business_policy
        result = bulk_service.execute(
            request=request, policy=policy, rule=self.access_rule,
            queryset=policy.queryset('real_estate', 'bulk_change'),
            serializer_class=self.get_serializer_class(), serializer_context=self.get_serializer_context(),
            data=request.data,
        )
        return Response(result)

    @action(detail=False, methods=['get'], url_path='responsible-suggestions')
    def responsible_suggestions(self, request):
        keyword = (request.query_params.get('q') or '').strip()
        qs = self.business_policy.queryset('real_estate', 'list').exclude(responsible_name='')
        if keyword:
            qs = qs.filter(responsible_name__icontains=keyword)
        names = qs.order_by('responsible_name').values_list('responsible_name', flat=True).distinct()[:20]
        return Response([{'name': name} for name in names])

    @action(detail=False, methods=['get'])
    def export(self, request):
        qs = self.get_queryset().order_by('transaction_number')
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['番号', '当事者', '物件名', '部屋番号', '管理会社', '担当者', '取引種別', '段階',
                         '取引日', '賃料・価格', '仲介手数料', '広告料', '手数料', '支払状態', '支払日',
                         '振込状態', 'アーカイブ'])
        count = 0
        for tx in qs:
            writer.writerow([
                tx.transaction_number, tx.party_name, tx.property_name, tx.room_number,
                tx.management_company_name, tx.responsible_name, tx.get_transaction_type_display(),
                tx.get_stage_display(), tx.transaction_date or '', tx.rent_or_price or '',
                tx.brokerage_fee or '', tx.advertising_fee or '', tx.handling_fee or '',
                tx.get_payment_status_display(), tx.payment_date or '', tx.get_transfer_status_display(),
                'はい' if tx.is_archived else '',
            ])
            count += 1
        record(module=AUDIT_MODULE, action='transaction_exported', request=request,
               object_type='real_estate.realestatetransaction', extra={'rows': count})
        response = HttpResponse(('﻿' + buffer.getvalue()).encode('utf-8'), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="real_estate_{timezone.localdate():%Y%m%d}.csv"'
        return response

    @action(detail=True, methods=['post'], url_path='ensure-ledger')
    def ensure_ledger(self, request, pk=None):
        tx = self.get_object()
        if tx.is_archived:
            raise ValidationError({'detail': 'アーカイブ済みの記録は変更できません。先に復元してください。'})
        existed = LegalLedger.objects.filter(transaction=tx).exists()  # access-reviewed: 取引の変更権限を確認済み
        ledger = ledger_service.ensure_ledger(tx)
        if not existed:
            _audit(request, ledger, 'ledger_created', object_repr=tx.transaction_number)
        return Response(LegalLedgerSerializer(ledger, context=self.get_serializer_context()).data,
                        status=status.HTTP_200_OK if existed else status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='audit-log')
    def audit_log(self, request, pk=None):
        """この取引と子資源の監査記録（利益配分は専用権限がある人にだけ含める）。"""
        tx = self.get_object()
        policy = self.business_policy
        targets = Q(object_type='real_estate.realestatetransaction', object_id=str(tx.pk))
        children = {
            'real_estate.transactionparty': tx.parties.values_list('id', flat=True),
            'real_estate.realestatefile': tx.files.values_list('id', flat=True),
            'real_estate.realestateaccountinglink': tx.accounting_links.values_list('id', flat=True),
        }
        if LegalLedger.objects.filter(transaction=tx).exists():  # access-reviewed: 取引の閲覧権限を確認済み
            children['real_estate.legalledger'] = [tx.legal_ledger.pk]
        if policy.rule('real_estate').can_manage_profit(policy):
            children['real_estate.internalprofitdistribution'] = tx.profit_distributions.values_list('id', flat=True)
        for object_type, ids in children.items():
            ids = [str(i) for i in ids]
            if ids:
                targets |= Q(object_type=object_type, object_id__in=ids)
        rows = AuditLog.objects.filter(targets, result=AuditLog.RESULT_SUCCESS).select_related(
            'user', 'employee').order_by('-occurred_at')[:200]  # access-reviewed: 取引の閲覧権限を確認済み、対象は当該取引の記録だけ
        include_technical = policy.has('audit.view_auditlog')
        return Response([serialize_history(row, include_technical=include_technical) for row in rows])


class TransactionPartyViewSet(TransactionFilterMixin, BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'real_estate_party'
    queryset = TransactionParty.objects.select_related('transaction', 'customer', 'company')
    serializer_class = TransactionPartySerializer

    def get_queryset(self):
        return self.filter_transaction(super().get_queryset())

    def perform_create(self, serializer):
        self._history_fields = set(serializer.validated_data) & set(PARTY_HISTORY_FIELDS)
        super().perform_create(serializer)

    def after_create(self, instance):
        after = {field: getattr(instance, field) for field in self._history_fields}
        _audit(self.request, instance, 'party_created', object_repr=instance.name, changes=safe_changes({}, after))

    def perform_update(self, serializer):
        self._history_fields = set(serializer.validated_data) & set(PARTY_HISTORY_FIELDS)
        self._history_before = {field: getattr(serializer.instance, field) for field in self._history_fields}
        super().perform_update(serializer)

    def after_update(self, instance):
        after = {field: getattr(instance, field) for field in self._history_fields}
        changes = safe_changes(self._history_before, after)
        if changes:
            _audit(self.request, instance, 'party_updated', object_repr=instance.name, changes=changes)

    def perform_destroy(self, instance):
        if instance.transaction.is_archived:
            raise ValidationError({'detail': 'アーカイブ済みの記録は変更できません。先に復元してください。'})
        ledger = LegalLedger.objects.filter(transaction_id=instance.transaction_id).first()  # access-reviewed: 当事者の変更権限を確認済み
        if ledger is not None and ledger.is_locked:
            raise ValidationError({'detail': '台帳がロックされているため、当事者は削除できません。'})
        _audit(self.request, instance, 'party_deleted', object_repr=instance.name)
        instance.delete()


class LegalLedgerViewSet(TransactionFilterMixin, BusinessScopedViewSetMixin, ModelViewSet):
    """法定台帳：作成は取引の ensure-ledger、削除は提供しない。"""

    access_resource = 'real_estate_ledger'
    http_method_names = ['get', 'patch', 'post', 'head', 'options']
    access_action_map = {
        'update': 'ledger', 'partial_update': 'ledger', 'lock': 'ledger', 'correct': 'correct',
        'legal_hold': 'ledger', 'corrections': 'view', 'close_year': 'close_year', 'export': 'export',
    }
    queryset = LegalLedger.objects.select_related('transaction')
    serializer_class = LegalLedgerSerializer

    def get_queryset(self):
        qs = self.filter_transaction(super().get_queryset())
        if self.request.query_params.get('fiscal_year'):
            qs = qs.filter(fiscal_year=self.request.query_params['fiscal_year'])
        return qs

    def create(self, request, *args, **kwargs):
        raise ValidationError({'detail': '台帳は取引の画面から作成してください。'})

    def _require(self, permission, message):
        policy = self.business_policy
        if not policy.has(permission):
            record(module=AUDIT_MODULE, action='ledger_manage_denied', request=self.request, result='denied',
                   object_type='real_estate.legalledger', reason=permission)
            raise PermissionDenied(message)

    @staticmethod
    def _reject_archived(ledger):
        if ledger.transaction.is_archived:
            raise ValidationError({'detail': 'アーカイブ済みの記録は変更できません。先に復元してください。'})

    def perform_update(self, serializer):
        self._reject_archived(serializer.instance)
        fields = set(serializer.validated_data)
        before = {field: getattr(serializer.instance, field) for field in fields}
        super().perform_update(serializer)
        ledger = serializer.instance
        ledger_service.refresh_derived(ledger)
        ledger.save(update_fields=['fiscal_year', 'fiscal_year_end_month', 'retention_until', 'updated_at'])
        after = {field: getattr(ledger, field) for field in fields}
        changes = safe_changes(before, after)
        if changes:
            _audit(self.request, ledger, 'ledger_updated', object_repr=ledger.transaction.transaction_number,
                   changes=changes)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        ledger = self.get_object()
        self._reject_archived(ledger)
        self._require('real_estate.manage_legal_ledger', '法定台帳を管理する権限がありません。')
        ledger_service.lock(ledger, request)
        return Response(self.get_serializer(ledger).data)

    @action(detail=True, methods=['post'])
    def correct(self, request, pk=None):
        ledger = self.get_object()
        self._reject_archived(ledger)
        self._require('real_estate.correct_legal_ledger', '法定台帳を更正する権限がありません。')
        data = LedgerCorrectionInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        ledger_service.correct(ledger, data.validated_data['changes'], data.validated_data['reason'], request)
        return Response(self.get_serializer(ledger).data)

    @action(detail=True, methods=['post'], url_path='legal-hold')
    def legal_hold(self, request, pk=None):
        ledger = self.get_object()
        self._reject_archived(ledger)
        self._require('real_estate.manage_legal_ledger', '法定台帳を管理する権限がありません。')
        hold = str(request.data.get('hold', 'true')).lower() in ('1', 'true', 'yes')
        ledger_service.set_legal_hold(ledger, hold, request.data.get('reason', ''), request)
        return Response(self.get_serializer(ledger).data)

    @action(detail=True, methods=['get'])
    def corrections(self, request, pk=None):
        ledger = self.get_object()
        return Response(LegalLedgerCorrectionSerializer(ledger.corrections.select_related('corrected_by'), many=True).data)

    @action(detail=False, methods=['post'], url_path='close-year')
    def close_year(self, request):
        self._require('real_estate.close_legal_ledger_year', '法定台帳の年度を締める権限がありません。')
        try:
            year = int(request.data.get('fiscal_year'))
        except (TypeError, ValueError):
            raise ValidationError({'fiscal_year': '事業年度を指定してください。'})
        return Response(ledger_service.close_fiscal_year(year, self.get_queryset(), request))

    @action(detail=False, methods=['get'])
    def export(self, request):
        """台帳の CSV（事務所で表示・印刷するため）。出力は監査に残す。"""
        self._require('real_estate.manage_legal_ledger', '法定台帳を出力する権限がありません。')
        qs = self.get_queryset().prefetch_related('transaction__parties').order_by('contract_date', 'id')
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['番号', '取引種別', '取引態様', '当事者', '所在地', '物件名', '部屋', '面積㎡', '賃料・価格', '報酬',
                         '広告料', '手数料', '特約', '取引日', '事業年度', '保存期限', 'legal hold', 'ロック', '版'])
        count = 0
        for ledger in qs:
            parties = ' / '.join(f'{p.get_role_display()}:{p.name}' for p in ledger.transaction.parties.all())
            writer.writerow([
                ledger.transaction.transaction_number, ledger.get_transaction_type_display(),
                ledger.get_transaction_form_display(), parties, ledger.property_location, ledger.property_name,
                ledger.room_number, ledger.area_sqm or '', ledger.rent_or_price or '', ledger.remuneration or '',
                ledger.advertising_fee or '', ledger.handling_fee or '', ledger.special_terms,
                ledger.contract_date or '', ledger.fiscal_year or '', ledger.retention_until or '',
                'はい' if ledger.legal_hold else '', 'はい' if ledger.is_locked else '', ledger.version,
            ])
            count += 1
        record(module=AUDIT_MODULE, action='ledger_exported', request=request, object_type='real_estate.legalledger',
               extra={'rows': count, 'fiscal_year': request.query_params.get('fiscal_year', '')})
        response = HttpResponse(('﻿' + buffer.getvalue()).encode('utf-8'), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="legal_ledger_{timezone.localdate():%Y%m%d}.csv"'
        return response


class RealEstateFileViewSet(TransactionFilterMixin, BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'real_estate_file'
    http_method_names = ['get', 'post', 'head', 'options']
    access_action_map = {'download': 'download'}
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = RealEstateFile.objects.select_related('transaction', 'uploaded_by', 'document')
    serializer_class = RealEstateFileSerializer

    def get_queryset(self):
        return self.filter_transaction(super().get_queryset())

    def after_create(self, instance):
        _audit(self.request, instance, 'file_uploaded', object_repr=instance.title,
               extra={'transaction_id': instance.transaction_id, 'file_size': instance.file_size,
                      'document_id': instance.document_id})

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        policy = self.business_policy
        obj = self.get_queryset().filter(pk=pk).first()
        if obj is None or policy.decide('real_estate_file', obj, 'download') != ALLOW:
            raise Http404
        if not obj.file:
            raise ValidationError({'detail': 'このファイルは案件書類の参照です。案件の書類からダウンロードしてください。'})
        audit = is_first_range_request(request)
        try:
            real_path, rel_path = resolve_document_path(obj, subdir=REAL_ESTATE_FILE_SUBDIR)
        except (FileNotFoundError, SuspiciousFileOperation) as exc:
            _audit(request, obj, 'file_download_error', result='error', reason=str(exc))
            raise Http404 from exc
        if audit:
            _audit(request, obj, 'file_download_started', extra={'transaction_id': obj.transaction_id})
        return build_file_response(obj, real_path, rel_path, inline_requested=request.query_params.get('inline') == '1')


class RealEstateAccountingLinkViewSet(TransactionFilterMixin, BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'real_estate_accounting_link'
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    queryset = RealEstateAccountingLink.objects.select_related('transaction', 'income_source', 'voucher')
    serializer_class = RealEstateAccountingLinkSerializer

    def get_queryset(self):
        return self.filter_transaction(super().get_queryset())

    def after_create(self, instance):
        _audit(self.request, instance, 'accounting_linked',
               extra={'income_source_id': instance.income_source_id, 'voucher_id': instance.voucher_id})

    def perform_destroy(self, instance):
        if instance.transaction.is_archived:
            raise ValidationError({'detail': 'アーカイブ済みの記録は変更できません。先に復元してください。'})
        _audit(self.request, instance, 'accounting_unlinked',
               extra={'income_source_id': instance.income_source_id, 'voucher_id': instance.voucher_id})
        instance.delete()


class InternalProfitDistributionViewSet(TransactionFilterMixin, BusinessScopedViewSetMixin, ModelViewSet):
    """内部利益配分：manage_profit_distribution がある人だけ（閲覧も監査に残す）。法定台帳には出さない。"""

    access_resource = 'real_estate_profit'
    access_action_map = {'settle': 'change', 'reopen': 'change'}
    queryset = InternalProfitDistribution.objects.select_related('transaction', 'recipient_employee')
    serializer_class = InternalProfitDistributionSerializer

    def get_queryset(self):
        return self.filter_transaction(super().get_queryset())

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record(module=AUDIT_MODULE, action='profit_distribution_viewed', request=request,
               object_type='real_estate.internalprofitdistribution',
               extra={'transaction_id': request.query_params.get('transaction', ''), 'mode': 'list'})
        return response

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        _audit(request, self.get_object(), 'profit_distribution_viewed', extra={'mode': 'detail'})
        return response

    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance.created_by = self.request.user
        serializer.instance.save(update_fields=['created_by'])

    def after_create(self, instance):
        _audit(self.request, instance, 'profit_distribution_created', changes={'amount': int(instance.amount)})

    def after_update(self, instance):
        _audit(self.request, instance, 'profit_distribution_updated', changes={'amount': int(instance.amount)})

    def perform_destroy(self, instance):
        if instance.transaction.is_archived:
            raise ValidationError({'detail': 'アーカイブ済みの記録は変更できません。先に復元してください。'})
        if instance.status == InternalProfitDistribution.STATUS_SETTLED:
            raise ValidationError({'detail': '結算済みの配分は削除できません。'})
        _audit(self.request, instance, 'profit_distribution_deleted', changes={'amount': int(instance.amount)})
        instance.delete()

    @action(detail=True, methods=['post'])
    def settle(self, request, pk=None):
        obj = self.get_object()
        if obj.transaction.is_archived:
            raise ValidationError({'detail': 'アーカイブ済みの記録は変更できません。先に復元してください。'})
        if obj.status == InternalProfitDistribution.STATUS_SETTLED:
            raise ValidationError({'detail': '既に結算済みです。'})
        obj.status, obj.settled_at = InternalProfitDistribution.STATUS_SETTLED, timezone.now()
        obj.save()
        _audit(request, obj, 'profit_distribution_settled', changes={'amount': int(obj.amount)})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        obj = self.get_object()
        if obj.transaction.is_archived:
            raise ValidationError({'detail': 'アーカイブ済みの記録は変更できません。先に復元してください。'})
        if obj.status != InternalProfitDistribution.STATUS_SETTLED:
            raise ValidationError({'detail': '結算済みではありません。'})
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            raise ValidationError({'reason': '草稿に戻す理由を入力してください。'})
        obj.status, obj.settled_at = InternalProfitDistribution.STATUS_DRAFT, None
        obj.save()
        _audit(request, obj, 'profit_distribution_reopened', reason=reason)
        return Response(self.get_serializer(obj).data)
