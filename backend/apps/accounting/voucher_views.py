"""帳票 API（P2-C11）：見積書・契約書・請求書・領収書。

帳票ごとに別の ViewSet・別の権限・別の状態。共通なのは下の BusinessDocumentViewMixin
（状態遷移・PDF・削除制限・監査の呼び出し方）だけで、どの帳票の状態も他の帳票に連動しない。
「元の帳票から作成」は内容を写した下書きを作るだけで、元の帳票の状態は変えない。
"""
from django.db import transaction as db_transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.authentication.access_rules import CUSTOMER_RULE, COMPANY_RULE, VISIBLE_LEVELS
from apps.authentication.drf import BusinessScopedViewSetMixin, business_api_view

from .models import AccountingVoucher, Contract, Estimate, IssuedLineCostSnapshot
from .pdf import business_document_pdf_response, voucher_pdf_response
from .serializers import (
    AccountingVoucherSerializer,
    ContractSerializer,
    EstimateSerializer,
    VoucherStatusHistorySerializer,
    VoucherTransitionSerializer,
    can_view_floor_price,
)
from .service_lines import strip_service_keys
from .voucher_calculations import decimal_to_number
from .voucher_infra import DocumentConflict, audit, same_version, transition, workflow_for

COPY_FIELDS = (
    'recipient_name', 'recipient_honorific', 'recipient_postal_code', 'recipient_address', 'title', 'line_items',
    'issuer_name', 'issuer_postal_code', 'issuer_address', 'issuer_tel', 'issuer_registration_number',
    'case', 'customer', 'company',
)


def parse_bool(value):
    return str(value or '').lower() in ('1', 'true', 'yes')


class BusinessDocumentViewMixin:
    """帳票 ViewSet 共通の操作。status_filter_field は帳票ごとの状態列。"""

    number_field = ''
    status_filter_field = 'status'
    access_action_map = {'transition': 'change', 'pdf': 'view', 'internal_costs': 'view'}

    def filter_common(self, queryset):
        params = self.request.query_params
        if params.get('status'):
            value = params['status']
            queryset = queryset.filter(**{self.status_filter_field: '' if value == 'unset' else value})
        for name in ('case', 'customer', 'company'):
            if params.get(name):
                queryset = queryset.filter(**{f'{name}_id': params[name]})
        if params.get('issue_date_from'):
            queryset = queryset.filter(issue_date__gte=params['issue_date_from'])
        if params.get('issue_date_to'):
            queryset = queryset.filter(issue_date__lte=params['issue_date_to'])
        keyword = params.get('keyword') or params.get('search')
        if keyword:
            queryset = queryset.filter(
                Q(**{f'{self.number_field}__icontains': keyword})
                | Q(recipient_name__icontains=keyword)
                | Q(title__icontains=keyword)
                | Q(note__icontains=keyword)
                | Q(line_items__icontains=keyword)
            )
        return queryset.order_by('-issue_date', '-id')

    def after_create(self, instance):
        audit(self.request, instance, 'created', changes={'total_amount': decimal_to_number(instance.total_amount)})

    def after_update(self, instance):
        audit(self.request, instance, 'updated')

    def perform_update(self, serializer):
        """保存時に行をロックして確認する（P1・P4）。

        - 画面を開いた時は下書きでも、保存時に発行済みなら保存しない（409）。
        - version（画面で見ていた updated_at）が送られ、他の人の保存で変わっていれば保存しない（409）。
          旧画面との互換のため version の無い保存は従来どおり受け付ける（現行の画面は常に送る）。
        """
        model = type(serializer.instance)
        with db_transaction.atomic():
            locked = model.objects.select_for_update().get(pk=serializer.instance.pk)  # access-reviewed: 変更権限を確認済みの同じ帳票をロックする
            workflow = workflow_for(locked)
            if workflow.is_editable(serializer.instance) and not workflow.is_editable(locked):
                raise DocumentConflict(f'この{workflow.label}は他の操作で下書き以外の状態になったため、内容を保存していません。'
                                       '画面を更新してください。')
            if not same_version(locked, self.request.data.get('version')):
                raise DocumentConflict(f'この{workflow.label}は他の人が先に保存しました。入力内容は保存していません。'
                                       '画面を更新して最新の内容を確認してください。', code='version_conflict')
            # ロックした最新の行に対して保存する（送られていない項目を古い内容で上書きしない）
            serializer.instance = locked
            super().perform_update(serializer)

    @action(detail=True, methods=['get'], url_path='internal-costs')
    def internal_costs(self, request, pk=None):
        """委託底価（社内）：現在の明細の底価と、発行ごとの版。底価権限者だけが読める。"""
        obj = self.get_object()
        if not hasattr(obj, 'internal_line_costs'):
            raise NotFound()
        if not can_view_floor_price(self.get_serializer_context()):
            raise PermissionDenied('委託底価を閲覧する権限がありません。')
        workflow = workflow_for(obj)
        versions = IssuedLineCostSnapshot.objects.filter(document_kind=workflow.kind, document_id=obj.pk)
        return Response({
            'current': obj.internal_line_costs or [],
            'issued_versions': [
                {'version': row.version, 'document_number': row.document_number, 'line_costs': row.line_costs,
                 'created_at': row.created_at} for row in versions.order_by('version')
            ],
        })

    def perform_destroy(self, instance):
        workflow = workflow_for(instance)
        if not workflow.is_editable(instance):
            raise ValidationError({'detail': f'発行後の{workflow.label}は削除できません。取消・無効にしてください。'})
        audit(self.request, instance, 'deleted')
        instance.delete()

    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, pk=None):
        obj = self.get_object()
        serializer = VoucherTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        obj = transition(obj, data['status'], request=request, reason=data.get('reason', ''), on_date=data.get('date'),
                         expected_status=data.get('expected_status'),
                         confirm_provisional=data.get('confirm_provisional', False))
        return Response(self.get_serializer(obj).data)

    def pdf_response(self, obj, with_seal):
        raise NotImplementedError

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        obj = self.get_object()
        with_seal = parse_bool(request.query_params.get('with_seal'))
        audit(request, obj, 'pdf_downloaded', extra={'with_seal': with_seal})
        return self.pdf_response(obj, with_seal)

    # --- 元の帳票から下書きを作る -------------------------------------------------

    def create_draft_from(self, source, target_resource, model, extra, serializer_class):
        policy = self.business_policy
        if not policy.module_allowed(target_resource, 'create'):
            raise PermissionDenied('作成先の帳票を利用する権限がありません。')
        data = {name: getattr(source, name) for name in COPY_FIELDS}
        data.update(extra)
        # P4：サービス項目のスナップショットと底価は見積書→請求書のときだけ写す（契約書・領収書は使わない）
        target_uses_services = model is Estimate or data.get('voucher_type') == AccountingVoucher.VOUCHER_TYPE_INVOICE
        if target_uses_services and hasattr(source, 'internal_line_costs'):
            data['internal_line_costs'] = list(source.internal_line_costs or [])
        elif not target_uses_services:
            data['line_items'] = strip_service_keys(data.get('line_items'))
        data.update(policy.rule(target_resource).prepare_create(policy, data))
        draft = model(issue_date=timezone.localdate(), **data)
        draft.save()
        audit(self.request, draft, 'created', extra={'copied_from': f'{workflow_for(source).kind}:{source.number}'})
        context = {**self.get_serializer_context()}
        return Response(serializer_class(draft, context=context).data, status=status.HTTP_201_CREATED)


class EstimateViewSet(BusinessDocumentViewMixin, BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'estimate'
    access_action_map = {**BusinessDocumentViewMixin.access_action_map,
                         'create_contract': 'view', 'create_invoice': 'view'}
    queryset = Estimate.objects.select_related('case', 'customer', 'company')
    serializer_class = EstimateSerializer
    number_field = 'estimate_number'

    def get_queryset(self):
        return self.filter_common(super().get_queryset())

    def pdf_response(self, obj, with_seal):
        return business_document_pdf_response('estimate', obj, with_seal=with_seal)

    @action(detail=True, methods=['post'], url_path='create-contract')
    def create_contract(self, request, pk=None):
        estimate = self.get_object()
        return self.create_draft_from(estimate, 'contract', Contract, {
            'source_estimate': estimate, 'status': Contract.STATUS_DRAFT,
        }, ContractSerializer)

    @action(detail=True, methods=['post'], url_path='create-invoice')
    def create_invoice(self, request, pk=None):
        estimate = self.get_object()
        return self.create_draft_from(estimate, 'voucher', AccountingVoucher, {
            'voucher_type': AccountingVoucher.VOUCHER_TYPE_INVOICE,
            'invoice_status': AccountingVoucher.INVOICE_STATUS_DRAFT,
            'source_estimate': estimate, 'amount': estimate.amount, 'tax_amount': estimate.tax_amount,
        }, AccountingVoucherSerializer)


class ContractViewSet(BusinessDocumentViewMixin, BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'contract'
    access_action_map = {**BusinessDocumentViewMixin.access_action_map, 'create_invoice': 'view'}
    queryset = Contract.objects.select_related('case', 'customer', 'company', 'source_estimate')
    serializer_class = ContractSerializer
    number_field = 'contract_number'

    def get_queryset(self):
        return self.filter_common(super().get_queryset())

    def pdf_response(self, obj, with_seal):
        return business_document_pdf_response('contract', obj, with_seal=with_seal)

    @action(detail=True, methods=['post'], url_path='create-invoice')
    def create_invoice(self, request, pk=None):
        contract = self.get_object()
        return self.create_draft_from(contract, 'voucher', AccountingVoucher, {
            'voucher_type': AccountingVoucher.VOUCHER_TYPE_INVOICE,
            'invoice_status': AccountingVoucher.INVOICE_STATUS_DRAFT,
            'source_contract': contract, 'source_estimate': contract.source_estimate,
            'amount': contract.amount, 'tax_amount': contract.tax_amount,
        }, AccountingVoucherSerializer)


class AccountingVoucherViewSet(BusinessDocumentViewMixin, BusinessScopedViewSetMixin, ModelViewSet):
    """請求書・領収書（既存の表）。状態は invoice_status / receipt_status をそれぞれ使う。"""

    access_resource = 'voucher'
    access_action_map = {**BusinessDocumentViewMixin.access_action_map, 'create_receipt': 'change',
                         'status_history': 'view'}
    queryset = AccountingVoucher.objects.select_related(
        'created_by', 'case', 'customer', 'company', 'source_estimate', 'source_contract', 'source_invoice',
    )
    serializer_class = AccountingVoucherSerializer
    number_field = 'voucher_number'

    @property
    def status_filter_field(self):
        voucher_type = self.request.query_params.get('voucher_type')
        return 'receipt_status' if voucher_type == AccountingVoucher.VOUCHER_TYPE_RECEIPT else 'invoice_status'

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        if params.get('voucher_type'):
            queryset = queryset.filter(voucher_type=params['voucher_type'])
        if params.get('status') and not params.get('voucher_type'):
            raise ValidationError({'status': '状態で絞り込む場合は帳票種別も指定してください。'})

        issue_date_from = params.get('issue_date_from') or params.get('start_date')
        issue_date_to = params.get('issue_date_to') or params.get('end_date')
        if issue_date_from:
            queryset = queryset.filter(issue_date__gte=issue_date_from)
        if issue_date_to:
            queryset = queryset.filter(issue_date__lte=issue_date_to)

        if params.get('recipient_name'):
            queryset = queryset.filter(recipient_name__icontains=params['recipient_name'])
        if params.get('title'):
            keyword = params['title']
            queryset = queryset.filter(Q(title__icontains=keyword) | Q(line_items__icontains=keyword))
        if params.get('amount_min'):
            queryset = queryset.filter(total_amount__gte=params['amount_min'])
        if params.get('amount_max'):
            queryset = queryset.filter(total_amount__lte=params['amount_max'])
        if params.get('payment_due_date_from'):
            queryset = queryset.filter(payment_due_date__gte=params['payment_due_date_from'])
        if params.get('payment_due_date_to'):
            queryset = queryset.filter(payment_due_date__lte=params['payment_due_date_to'])

        keyword = params.get('keyword') or params.get('search')
        if keyword:
            queryset = queryset.filter(
                Q(voucher_number__icontains=keyword)
                | Q(recipient_name__icontains=keyword)
                | Q(title__icontains=keyword)
                | Q(details__icontains=keyword)
                | Q(note__icontains=keyword)
                | Q(bank_info__icontains=keyword)
                | Q(line_items__icontains=keyword)
            )
        if params.get('status'):
            value = params['status']
            queryset = queryset.filter(**{self.status_filter_field: '' if value == 'unset' else value})
        for name in ('case', 'customer', 'company'):
            if params.get(name):
                queryset = queryset.filter(**{f'{name}_id': params[name]})
        return queryset.order_by('-issue_date', '-id')

    def pdf_response(self, obj, with_seal):
        return voucher_pdf_response(obj, with_seal=with_seal)

    @action(detail=True, methods=['get'], url_path='status-history')
    def status_history(self, request, pk=None):
        """状態変更の履歴（新しい順）。各行に変更時点の帳票内容のスナップショットを含む。"""
        voucher = self.get_object()
        rows = voucher.status_history.select_related('changed_by', 'changed_by__employee')[:200]
        return Response(VoucherStatusHistorySerializer(rows, many=True).data)

    @action(detail=True, methods=['post'], url_path='create-receipt')
    def create_receipt(self, request, pk=None):
        invoice = self.get_object()
        if invoice.voucher_type != AccountingVoucher.VOUCHER_TYPE_INVOICE:
            raise ValidationError({'detail': '領収書は請求書から作成してください。'})
        return self.create_draft_from(invoice, 'voucher', AccountingVoucher, {
            'voucher_type': AccountingVoucher.VOUCHER_TYPE_RECEIPT,
            'receipt_status': AccountingVoucher.RECEIPT_STATUS_DRAFT,
            'source_invoice': invoice, 'payment_method': invoice.payment_method,
            'amount': invoice.amount, 'tax_amount': invoice.tax_amount,
        }, AccountingVoucherSerializer)


# --- 案件・顧客・会社から見る帳票の要約 ---------------------------------------------------

def _summary_rows(queryset, number_field, status_field):
    rows = []
    for obj in queryset.order_by('-issue_date', '-id')[:20]:
        labels = dict(obj._meta.get_field(status_field).choices)
        value = getattr(obj, status_field) or ''
        rows.append({
            'id': obj.id, 'number': getattr(obj, number_field), 'issue_date': obj.issue_date,
            'title': obj.title, 'recipient_name': obj.recipient_name,
            'status': value, 'status_display': labels.get(value, '状態未設定（旧データ）'),
            'total_amount': decimal_to_number(obj.total_amount),
        })
    return rows


@business_api_view(['GET'], 'voucher_links')
def voucher_links(request):
    """?case= / ?customer= / ?company= のいずれか 1 つ。対象を見られること、かつ各帳票の権限があるものだけ返す。"""
    policy = request.business_policy
    params = request.query_params
    target = [(name, params.get(name)) for name in ('case', 'customer', 'company') if params.get(name)]
    if len(target) != 1:
        raise ValidationError({'detail': 'case・customer・company のいずれか 1 つを指定してください。'})
    field, value = target[0]
    if field == 'case':
        visible = policy.queryset('case', 'view').filter(pk=value).exists()
    else:
        rule, model_resource = (CUSTOMER_RULE, 'customer') if field == 'customer' else (COMPANY_RULE, 'company')
        obj = policy.queryset(model_resource, 'list').filter(pk=value).first()
        visible = obj is not None and rule.level(policy, obj) in VISIBLE_LEVELS
    if not visible:
        raise PermissionDenied('この対象を閲覧する権限がありません。')

    def block(resource, number_field, status_field, **filters):
        if not policy.module_allowed(resource, 'list'):
            return {'visible': False}
        qs = policy.queryset(resource, 'list').filter(**{f'{field}_id': value}, **filters)
        return {'visible': True, 'count': qs.count(), 'items': _summary_rows(qs, number_field, status_field)}

    return Response({
        'estimates': block('estimate', 'estimate_number', 'status'),
        'contracts': block('contract', 'contract_number', 'status'),
        'invoices': block('voucher', 'voucher_number', 'invoice_status',
                          voucher_type=AccountingVoucher.VOUCHER_TYPE_INVOICE),
        'receipts': block('voucher', 'voucher_number', 'receipt_status',
                          voucher_type=AccountingVoucher.VOUCHER_TYPE_RECEIPT),
    })
