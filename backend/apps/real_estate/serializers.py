from decimal import Decimal

from rest_framework import serializers

from apps.documents.upload_policy import file_metadata, validate_upload

from .history import user_display_name
from .ledger_service import reject_if_locked
from .models import (
    InternalProfitDistribution,
    LegalLedger,
    LegalLedgerCorrection,
    RealEstateAccountingLink,
    RealEstateFile,
    RealEstateTransaction,
    TransactionParty,
)

REQUIRED_FOR_SETTLEMENT = (
    ('transaction_date', '取引日'),
    ('responsible_name', '担当者'),
    ('management_company_name', '管理会社'),
    ('payment_status', '支払状態'),
)


def missing_items(tx):
    """一覧で「要補充」を示す項目（推測で埋めない）。"""
    return [label for field, label in REQUIRED_FOR_SETTLEMENT if not getattr(tx, field)]


class RealEstateTransactionSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    transfer_status_display = serializers.CharField(source='get_transfer_status_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    management_company_ref_name = serializers.CharField(source='management_company.name', read_only=True, default='')
    missing_items = serializers.SerializerMethodField()
    has_ledger = serializers.SerializerMethodField()
    ledger_locked = serializers.SerializerMethodField()

    class Meta:
        model = RealEstateTransaction
        fields = '__all__'
        read_only_fields = (
            'transaction_number', 'source_file', 'source_file_sha256', 'source_sheet', 'source_row',
            'source_reference', 'source_values', 'is_archived', 'archived_at', 'archived_by', 'archive_reason',
            'restored_at', 'restored_by', 'created_by', 'updated_by', 'created_at', 'updated_at',
        )

    def get_missing_items(self, obj):
        return missing_items(obj)

    def _ledger(self, obj):
        try:
            return obj.legal_ledger
        except LegalLedger.DoesNotExist:
            return None

    def get_has_ledger(self, obj):
        return self._ledger(obj) is not None

    def get_ledger_locked(self, obj):
        ledger = self._ledger(obj)
        return bool(ledger and ledger.is_locked)

    def validate(self, attrs):
        if self.instance is not None and self.instance.is_archived and attrs:
            raise serializers.ValidationError({'detail': 'アーカイブ済みの記録は編集できません。先に復元してください。'})
        for field in ('rent_or_price', 'brokerage_fee', 'advertising_fee', 'handling_fee'):
            value = attrs.get(field)
            if value is not None and value < 0:
                raise serializers.ValidationError({field: '金額は 0 以上で入力してください。'})
        return attrs


class TransactionPartySerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    company_name = serializers.CharField(source='company.name', read_only=True, default='')

    class Meta:
        model = TransactionParty
        fields = '__all__'

    def validate(self, attrs):
        tx = attrs.get('transaction') or getattr(self.instance, 'transaction', None)
        ledger = getattr(tx, 'legal_ledger', None) if tx is not None and hasattr(tx, 'legal_ledger') else None
        if ledger is not None and ledger.is_locked:
            raise serializers.ValidationError({'detail': '台帳がロックされているため、当事者は変更できません。'})
        return attrs


class LegalLedgerCorrectionSerializer(serializers.ModelSerializer):
    corrected_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LegalLedgerCorrection
        fields = ('id', 'version', 'changes', 'reason', 'corrected_by_name', 'corrected_at')

    def get_corrected_by_name(self, obj):
        return user_display_name(obj.corrected_by)


class LegalLedgerSerializer(serializers.ModelSerializer):
    transaction_form_display = serializers.CharField(source='get_transaction_form_display', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    transaction_number = serializers.CharField(source='transaction.transaction_number', read_only=True)
    parties = serializers.SerializerMethodField()
    retention_due = serializers.SerializerMethodField()

    class Meta:
        model = LegalLedger
        fields = '__all__'
        read_only_fields = (
            'transaction', 'fiscal_year', 'fiscal_year_end_month', 'fiscal_year_closed_at', 'retention_until', 'legal_hold',
            'legal_hold_reason', 'is_locked', 'locked_at', 'locked_by', 'locked_snapshot', 'version',
            'created_at', 'updated_at',
        )

    def get_parties(self, obj):
        return TransactionPartySerializer(obj.transaction.parties.all(), many=True).data

    def get_retention_due(self, obj):
        # 保存期限を過ぎても自動削除しない。到期復核の対象として示すだけ（legal hold 中は対象外）。
        from django.utils import timezone

        return bool(obj.retention_until and obj.retention_until < timezone.localdate() and not obj.legal_hold)

    def validate(self, attrs):
        if self.instance is not None:
            reject_if_locked(self.instance, attrs)
        return attrs


class LedgerCorrectionInputSerializer(serializers.Serializer):
    changes = serializers.DictField()
    reason = serializers.CharField(max_length=500)

    def validate_changes(self, value):
        # 型変換は台帳シリアライザの項目定義に任せる（未知の項目は ledger_service が拒否）
        field_serializer = LegalLedgerSerializer()
        cleaned = {}
        for name, raw in value.items():
            field = field_serializer.fields.get(name)
            if field is None or field.read_only:
                raise serializers.ValidationError({name: '更正できない項目です。'})
            cleaned[name] = field.run_validation(raw)
        return cleaned


class RealEstateFileSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    document_title = serializers.CharField(source='document.title', read_only=True, default='')
    file = serializers.FileField(write_only=True, required=False)
    has_file = serializers.SerializerMethodField()

    class Meta:
        model = RealEstateFile
        fields = ('id', 'transaction', 'kind', 'kind_display', 'title', 'file', 'file_name', 'file_size', 'mime_type',
                  'sha256', 'document', 'document_title', 'uploaded_by_name', 'created_at', 'has_file')
        read_only_fields = ('file_name', 'file_size', 'mime_type', 'sha256', 'created_at')

    def get_has_file(self, obj):
        return bool(obj.file)

    def get_uploaded_by_name(self, obj):
        return user_display_name(obj.uploaded_by)

    def validate_file(self, uploaded):
        problem = validate_upload(uploaded)
        if problem:
            raise serializers.ValidationError(problem)
        return uploaded

    def validate(self, attrs):
        if self.instance is None and not attrs.get('file') and not attrs.get('document'):
            raise serializers.ValidationError({'file': 'ファイルを選択するか、案件書類を参照してください。'})
        return attrs

    def create(self, validated_data):
        uploaded = validated_data.get('file')
        if uploaded:
            meta = file_metadata(uploaded)
            validated_data.update(file_name=meta['file_name'], file_size=meta['file_size'],
                                  mime_type=meta['content_type'], sha256=meta['sha256'])
        return super().create(validated_data)


class RealEstateAccountingLinkSerializer(serializers.ModelSerializer):
    income_summary = serializers.SerializerMethodField()
    voucher_summary = serializers.SerializerMethodField()

    class Meta:
        model = RealEstateAccountingLink
        fields = ('id', 'transaction', 'income_source', 'voucher', 'note', 'income_summary', 'voucher_summary',
                  'created_at')

    def _policy(self):
        return self.context.get('policy')

    def get_income_summary(self, obj):
        # 参照先の中身は会計の権限がある人にだけ見せる（会計データは複製しない）
        policy = self._policy()
        if not obj.income_source_id or policy is None or not policy.module_allowed('income', 'view'):
            return None
        i = obj.income_source
        return {'date': i.source_date, 'target': i.source_target, 'amount': int(i.amount)}

    def get_voucher_summary(self, obj):
        policy = self._policy()
        if not obj.voucher_id or policy is None or not policy.module_allowed('voucher', 'view'):
            return None
        v = obj.voucher
        return {'number': v.voucher_number, 'type': v.get_voucher_type_display(), 'total': int(v.total_amount)}

    def validate(self, attrs):
        if not attrs.get('income_source') and not attrs.get('voucher'):
            raise serializers.ValidationError({'detail': '収入または請求書・領収書を選択してください。'})
        return attrs


class InternalProfitDistributionSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    transaction_number = serializers.CharField(source='transaction.transaction_number', read_only=True)

    class Meta:
        model = InternalProfitDistribution
        fields = '__all__'
        read_only_fields = ('amount', 'status', 'settled_at', 'created_by', 'created_at', 'updated_at')

    def validate(self, attrs):
        if self.instance is not None and self.instance.status == InternalProfitDistribution.STATUS_SETTLED:
            allowed = {'note'}
            if set(attrs) - allowed:
                raise serializers.ValidationError({'detail': '結算済みの配分は備考以外変更できません（草稿に戻してから変更してください）。'})
            return attrs
        method = attrs.get('method', getattr(self.instance, 'method', InternalProfitDistribution.METHOD_RATIO))
        if method == InternalProfitDistribution.METHOD_RATIO:
            ratio = attrs.get('ratio_percent', getattr(self.instance, 'ratio_percent', None))
            if ratio is None or not (Decimal('0') <= ratio <= Decimal('100')):
                raise serializers.ValidationError({'ratio_percent': '比率は 0〜100 の範囲で入力してください。'})
        else:
            fixed = attrs.get('fixed_amount', getattr(self.instance, 'fixed_amount', None))
            if fixed is None or fixed < 0:
                raise serializers.ValidationError({'fixed_amount': '固定金額を入力してください。'})
        base = attrs.get('base_amount')
        if base is not None and base < 0:
            raise serializers.ValidationError({'base_amount': '基準額は 0 以上で入力してください。'})
        return attrs
