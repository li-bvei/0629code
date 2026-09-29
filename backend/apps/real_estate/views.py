"""不動産 API。範囲・権限は BusinessAccessPolicy（access_rules の real_estate* 規則）が決める。"""
import csv
import io

from django.core.exceptions import SuspiciousFileOperation
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
from apps.audit.services import record
from apps.authentication.access_policy import ALLOW
from apps.authentication.drf import BusinessScopedViewSetMixin
from apps.documents.protected_download import build_file_response, is_first_range_request, resolve_document_path

from . import ledger_service
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


def _audit(request, obj, action, **kwargs):
    record(module=AUDIT_MODULE, action=action, request=request, obj=obj, **kwargs)


class TransactionFilterMixin:
    """?transaction= で親取引を絞る子資源用。"""

    def filter_transaction(self, queryset):
        tx = self.request.query_params.get('transaction')
        return queryset.filter(transaction_id=tx) if tx else queryset


class RealEstateTransactionViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'real_estate'
    access_action_map = {'ensure_ledger': 'change', 'audit_log': 'view'}
    queryset = RealEstateTransaction.objects.select_related('responsible_employee', 'customer', 'management_company',
                                                           'legal_ledger')
    serializer_class = RealEstateTransactionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        if p.get('responsible_employee'):
            qs = qs.filter(responsible_employee_id=p['responsible_employee'])
        if p.get('mine') in ('1', 'true'):
            qs = qs.filter(responsible_employee_id=self.business_policy.employee_id)
        for name in ('stage', 'payment_status', 'transfer_status', 'transaction_type'):
            if p.get(name):
                value = p[name]
                qs = qs.filter(**{name: '' if value == 'unset' else value})
        if p.get('management_company'):
            value = p['management_company']
            qs = qs.filter(Q(management_company_name__icontains=value) | Q(management_company__name__icontains=value))
        if p.get('missing') in ('1', 'true'):
            qs = qs.filter(Q(transaction_date__isnull=True) | Q(responsible_employee__isnull=True)
                           | Q(management_company_name='') | Q(payment_status=''))
        keyword = p.get('keyword') or p.get('search')
        if keyword:
            qs = qs.filter(Q(transaction_number__icontains=keyword) | Q(party_name__icontains=keyword)
                           | Q(property_name__icontains=keyword) | Q(room_number__icontains=keyword)
                           | Q(note__icontains=keyword))
        return qs.order_by('-created_at', '-id')

    def after_create(self, instance):
        _audit(self.request, instance, 'transaction_created', object_repr=instance.transaction_number)

    def after_update(self, instance):
        _audit(self.request, instance, 'transaction_updated', object_repr=instance.transaction_number)

    def perform_destroy(self, instance):
        # 台帳・ファイルがある記録は削除しない（段階を「キャンセル」にする）
        if LegalLedger.objects.filter(transaction=instance).exists() or instance.files.exists():  # access-reviewed: 削除対象の取引は範囲確認済み
            raise ValidationError({'detail': '台帳またはファイルがある記録は削除できません。段階を「キャンセル」にしてください。'})
        _audit(self.request, instance, 'transaction_deleted', object_repr=instance.transaction_number)
        instance.delete()

    @action(detail=True, methods=['post'], url_path='ensure-ledger')
    def ensure_ledger(self, request, pk=None):
        tx = self.get_object()
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
        rows = AuditLog.objects.filter(targets).order_by('-occurred_at')[:200]  # access-reviewed: 取引の閲覧権限を確認済み、対象は当該取引の記録だけ
        return Response([
            {'occurred_at': r.occurred_at, 'user': r.username_snapshot, 'action': r.action, 'object_type': r.object_type,
             'result': r.result, 'reason': r.reason, 'changes': r.changes}
            for r in rows
        ])


class TransactionPartyViewSet(TransactionFilterMixin, BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'real_estate_party'
    queryset = TransactionParty.objects.select_related('transaction', 'customer', 'company')
    serializer_class = TransactionPartySerializer

    def get_queryset(self):
        return self.filter_transaction(super().get_queryset())

    def after_create(self, instance):
        _audit(self.request, instance, 'party_created', object_repr=instance.name)

    def after_update(self, instance):
        _audit(self.request, instance, 'party_updated', object_repr=instance.name)

    def perform_destroy(self, instance):
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
        'lock': 'change', 'correct': 'change', 'legal_hold': 'change', 'corrections': 'view',
        'close_year': 'change', 'export': 'export',
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

    def _require_manage(self):
        policy = self.business_policy
        if not policy.rule('real_estate').can_manage_ledger(policy):
            record(module=AUDIT_MODULE, action='ledger_manage_denied', request=self.request, result='denied',
                   object_type='real_estate.legalledger', reason='manage_legal_ledger')
            raise PermissionDenied('法定台帳のロック・更正・年度締め・出力の権限がありません。')

    def perform_update(self, serializer):
        super().perform_update(serializer)
        ledger = serializer.instance
        ledger_service.refresh_derived(ledger)
        ledger.save(update_fields=['fiscal_year', 'fiscal_year_end_month', 'retention_until', 'updated_at'])
        _audit(self.request, ledger, 'ledger_updated', object_repr=ledger.transaction.transaction_number)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        ledger = self.get_object()
        self._require_manage()
        ledger_service.lock(ledger, request)
        return Response(self.get_serializer(ledger).data)

    @action(detail=True, methods=['post'])
    def correct(self, request, pk=None):
        ledger = self.get_object()
        self._require_manage()
        data = LedgerCorrectionInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        ledger_service.correct(ledger, data.validated_data['changes'], data.validated_data['reason'], request)
        return Response(self.get_serializer(ledger).data)

    @action(detail=True, methods=['post'], url_path='legal-hold')
    def legal_hold(self, request, pk=None):
        ledger = self.get_object()
        self._require_manage()
        hold = str(request.data.get('hold', 'true')).lower() in ('1', 'true', 'yes')
        ledger_service.set_legal_hold(ledger, hold, request.data.get('reason', ''), request)
        return Response(self.get_serializer(ledger).data)

    @action(detail=True, methods=['get'])
    def corrections(self, request, pk=None):
        ledger = self.get_object()
        return Response(LegalLedgerCorrectionSerializer(ledger.corrections.select_related('corrected_by'), many=True).data)

    @action(detail=False, methods=['post'], url_path='close-year')
    def close_year(self, request):
        self._require_manage()
        try:
            year = int(request.data.get('fiscal_year'))
        except (TypeError, ValueError):
            raise ValidationError({'fiscal_year': '事業年度を指定してください。'})
        return Response(ledger_service.close_fiscal_year(year, self.get_queryset(), request))

    @action(detail=False, methods=['get'])
    def export(self, request):
        """台帳の CSV（事務所で表示・印刷するため）。出力は監査に残す。"""
        self._require_manage()
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
        if instance.status == InternalProfitDistribution.STATUS_SETTLED:
            raise ValidationError({'detail': '結算済みの配分は削除できません。'})
        _audit(self.request, instance, 'profit_distribution_deleted', changes={'amount': int(instance.amount)})
        instance.delete()

    @action(detail=True, methods=['post'])
    def settle(self, request, pk=None):
        obj = self.get_object()
        if obj.status == InternalProfitDistribution.STATUS_SETTLED:
            raise ValidationError({'detail': '既に結算済みです。'})
        obj.status, obj.settled_at = InternalProfitDistribution.STATUS_SETTLED, timezone.now()
        obj.save()
        _audit(request, obj, 'profit_distribution_settled', changes={'amount': int(obj.amount)})
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        obj = self.get_object()
        if obj.status != InternalProfitDistribution.STATUS_SETTLED:
            raise ValidationError({'detail': '結算済みではありません。'})
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            raise ValidationError({'reason': '草稿に戻す理由を入力してください。'})
        obj.status, obj.settled_at = InternalProfitDistribution.STATUS_DRAFT, None
        obj.save()
        _audit(request, obj, 'profit_distribution_reopened', reason=reason)
        return Response(self.get_serializer(obj).data)
