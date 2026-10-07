"""サービス価格マスタ API（P4）。

- 閲覧・選択：accounting.use_service_item。登録・変更・無効化：accounting.manage_service_item。
- 委託底価：accounting.view_service_floor_price を持つ人だけが見られ・変えられる（serializer が判定）。
- 変更は version（画面で見ていた updated_at）必須。他の人の保存と衝突したら 409。
- 変更はすべて監査に前後の値を残す（監査ログの閲覧は audit.view_auditlog の人だけ）。
- 帳票・案件で使われた項目は物理削除できない。無効化すると新しくは選べないが、過去の帳票・案件の内容は残る。
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.services import record, safe_changes
from apps.authentication.drf import BusinessScopedViewSetMixin

from .models import ServiceItem
from .serializers import FLOOR_PRICE_PERMISSION, ServiceItemSerializer
from .voucher_calculations import decimal_to_number
from .voucher_infra import DocumentConflict, same_version

AUDIT_MODULE = 'accounting'
AUDITED_FIELDS = (
    'category', 'name', 'default_price', 'price_type', 'floor_price', 'professional_type', 'tax_category', 'unit',
    'is_active', 'note', 'sort_order', 'price_status',
)
# これらが変わったら確定済みの価格は暫定に戻す（確定は「価格を確定」操作でやり直す）
PRICE_FIELDS = ('default_price', 'price_type', 'floor_price', 'tax_category', 'unit')


def _audit_values(item):
    values = {}
    for name in AUDITED_FIELDS:
        value = getattr(item, name)
        values[name] = decimal_to_number(value) if hasattr(value, 'as_tuple') else value
    return values


class ServiceItemViewSet(BusinessScopedViewSetMixin, ModelViewSet):
    access_resource = 'service_item'
    queryset = ServiceItem.objects.all()
    serializer_class = ServiceItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        active = str(params.get('active', params.get('is_active', ''))).lower()
        if active in ('1', 'true'):
            queryset = queryset.filter(is_active=True)
        elif active in ('0', 'false'):
            queryset = queryset.filter(is_active=False)
        if params.get('category'):
            queryset = queryset.filter(category=params['category'])
        keyword = (params.get('search') or params.get('keyword') or '').strip()
        if keyword:
            # 底価・社内メモは検索対象にしない（検索結果から金額を推測させない）
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(category__icontains=keyword))
        return queryset.order_by('sort_order', 'id')

    def perform_create(self, serializer):
        user = self.request.user
        instance = serializer.save(created_by=user, updated_by=user)
        record(module=AUDIT_MODULE, action='service_item_created', request=self.request, obj=instance,
               object_repr=f'サービス項目 {instance.name}', changes=safe_changes({}, _audit_values(instance)))

    def perform_update(self, serializer):
        version = self.request.data.get('version')
        if not version:
            raise ValidationError({'version': '画面で表示していた版（version）を送ってください。画面を更新してから保存してください。'})
        with transaction.atomic():
            locked = ServiceItem.objects.select_for_update().get(pk=serializer.instance.pk)  # access-reviewed: 変更権限を確認済みの同じ項目をロックする
            if not same_version(locked, version):
                raise DocumentConflict('このサービス項目は他の人が先に保存しました。入力内容は保存していません。'
                                       '画面を更新して最新の内容を確認してください。', code='version_conflict')
            before = _audit_values(locked)
            serializer.instance = locked
            extra = {}
            if locked.price_status == ServiceItem.PRICE_CONFIRMED and any(
                    name in serializer.validated_data and serializer.validated_data[name] != getattr(locked, name)
                    for name in PRICE_FIELDS):
                extra = {'price_status': ServiceItem.PRICE_PROVISIONAL, 'price_confirmed_at': None,
                         'price_confirmed_by': None}
            instance = serializer.save(updated_by=self.request.user, **extra)
            after = _audit_values(instance)
            changes = safe_changes(before, after)
            if changes:
                action = 'service_item_updated'
                if before['is_active'] != after['is_active']:
                    action = 'service_item_activated' if after['is_active'] else 'service_item_deactivated'
                record(module=AUDIT_MODULE, action=action, request=self.request, obj=instance,
                       object_repr=f'サービス項目 {instance.name}', changes=changes)

    @action(detail=True, methods=['post'], url_path='confirm-price')
    def confirm_price(self, request, pk=None):
        """暫定価格を確定する（P6）。サービス項目の管理権限と委託底価の権限の両方が必要。

        version（画面で見ていた updated_at）必須。他の操作と衝突したら 409。確定者・日時と監査を残す。
        """
        item = self.get_object()
        policy = self.business_policy
        if not policy.has(FLOOR_PRICE_PERMISSION):
            record(module=AUDIT_MODULE, action='service_item_price_confirm', request=request, obj=item, result='denied',
                   reason='missing floor price permission', object_repr=f'サービス項目 {item.name}')
            raise PermissionDenied('価格を確定するには委託底価の権限が必要です。')
        version = request.data.get('version')
        if not version:
            raise ValidationError({'version': '画面で表示していた版（version）を送ってください。'})
        with transaction.atomic():
            locked = ServiceItem.objects.select_for_update().get(pk=item.pk)  # access-reviewed: 権限確認済みの同じ項目をロックする
            if not same_version(locked, version):
                raise DocumentConflict('このサービス項目は他の人が先に変更しました。画面を更新してから確定してください。',
                                       code='version_conflict')
            if locked.price_status == ServiceItem.PRICE_CONFIRMED:
                raise ValidationError({'detail': 'この価格は既に確定しています。'})
            if locked.default_price is None:
                raise ValidationError({'default_price': '対客標準価格が未設定のため確定できません。'})
            before = _audit_values(locked)
            locked.price_status = ServiceItem.PRICE_CONFIRMED
            locked.price_confirmed_at = timezone.now()
            locked.price_confirmed_by = request.user
            locked.updated_by = request.user
            locked.save()
        record(module=AUDIT_MODULE, action='service_item_price_confirmed', request=request, obj=locked,
               object_repr=f'サービス項目 {locked.name}', changes=safe_changes(before, _audit_values(locked)),
               via_permission=FLOOR_PRICE_PERMISSION)
        return Response(self.get_serializer(locked).data)

    def perform_destroy(self, instance):
        if instance.first_used_at is not None:
            raise ValidationError({'detail': 'このサービス項目は帳票・案件で使われているため削除できません。無効にしてください。'})
        record(module=AUDIT_MODULE, action='service_item_deleted', request=self.request, obj=instance,
               object_repr=f'サービス項目 {instance.name}', changes=safe_changes(_audit_values(instance), {}))
        instance.delete()
