from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import (
    AccountingProject,
    AccountingProjectExpense,
    AccountingProjectIncome,
    AccountingVoucher,
    Contract,
    Estimate,
    Expense,
    ExpenseCategory,
    ExpenseCategorySuggestionRule,
    IncomeSource,
    SeifuNoticePdfGeneration,
    SeifuNoticePdfRecord,
    ServiceItem,
    TaxRenewalAgentTemplate,
    TaxRenewalVoucherRecord,
    VehicleUsage,
    VisaGuarantorTemplate,
    VisaReturnApplication,
    VisaReturnPdfGeneration,
    VoucherItemTemplate,
    VoucherStatusHistory,
)
from .seifu_notice_pdf import (
    TEMPLATE_KEY,
    TEMPLATE_NAME,
    SeifuPdfError,
    check_layout,
    derive_notice_number,
    normalize_issue_date,
    normalize_permit_number,
    normalize_recipient_name,
)
from .service_lines import ServiceLineError, apply_service_lines, mark_used, strip_service_keys
from .tax_renewal_templates import get_tax_renewal_templates
from .voucher_calculations import VoucherCalculationError, calculate_voucher_amounts, decimal_to_number
from .voucher_infra import (
    CONTRACT_WORKFLOW,
    ESTIMATE_WORKFLOW,
    INVOICE_WORKFLOW,
    RECEIPT_WORKFLOW,
    reject_locked_changes,
)

INVOICE_WORKFLOW_DRAFT = AccountingVoucher.INVOICE_STATUS_DRAFT
RECEIPT_WORKFLOW_DRAFT = AccountingVoucher.RECEIPT_STATUS_DRAFT

FLOOR_PRICE_PERMISSION = 'accounting.view_service_floor_price'


def can_view_floor_price(context):
    """委託底価を見られるか（BusinessAccessPolicy の明示権限のみ。is_superuser では判定しない）。"""
    policy = (context or {}).get('policy')
    return policy is not None and policy.has(FLOOR_PRICE_PERMISSION)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'


class ExpenseCategorySuggestionRuleSerializer(serializers.ModelSerializer):
    expense_category_name = serializers.CharField(source='expense_category.name', read_only=True)
    match_field_display = serializers.CharField(source='get_match_field_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    scope = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseCategorySuggestionRule
        fields = ('id', 'pattern', 'match_field', 'match_field_display', 'expense_category', 'expense_category_name',
                  'priority', 'is_active', 'source', 'source_display', 'scope', 'owner_name', 'created_at',
                  'updated_at')
        # 範囲（本人用／事務所共通）は API の入力では変えられない。共通への変更は promote だけ。
        read_only_fields = ('source', 'created_at', 'updated_at')

    def get_scope(self, obj):
        return 'office' if obj.owner_id is None else 'personal'

    def get_owner_name(self, obj):
        owner = obj.owner
        if owner is None:
            return ''
        employee = getattr(owner, 'employee', None) if hasattr(owner, 'employee') else None
        return employee.name if employee is not None else owner.get_username()

    def validate(self, attrs):
        from .category_suggestions import normalize_key

        pattern = attrs.get('pattern', getattr(self.instance, 'pattern', ''))
        match_field = attrs.get('match_field', getattr(self.instance, 'match_field', ExpenseCategorySuggestionRule.FIELD_PLACE))
        key = normalize_key(pattern)
        if not key:
            raise serializers.ValidationError({'pattern': '文字を入力してください。'})
        # 同じ範囲の中での重複を防ぐ（新規登録は常に事務所共通、変更は対象の規則の範囲のまま）
        owner_id = self.instance.owner_id if self.instance is not None else None
        duplicate = ExpenseCategorySuggestionRule.objects.filter(owner_id=owner_id, match_field=match_field,
                                                                 pattern_key=key)
        if self.instance is not None:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({'pattern': '同じ項目・同じ文字の規則が既にあります。'})
        return attrs


class ExpenseSerializer(serializers.ModelSerializer):
    # 「この場所とカテゴリの対応を記憶する」を利用者が明示的に選んだ場合だけ true（保存項目ではない）
    remember_place_category = serializers.BooleanField(write_only=True, required=False, default=False)
    owner_username = serializers.CharField(source='owner.username', read_only=True, default='')
    case_number = serializers.CharField(source='case.case_number', read_only=True, default='')
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    company_name = serializers.CharField(source='company.name', read_only=True, default='')
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = '__all__'
        # 所有者・作成者・更新者は後端が設定する。フロントからの指定は無視される。
        read_only_fields = ['owner', 'created_by', 'updated_by']

    def create(self, validated_data):
        remember = validated_data.pop('remember_place_category', False)
        instance = super().create(validated_data)
        instance._remember_place_category = remember
        return instance

    def update(self, instance, validated_data):
        remember = validated_data.pop('remember_place_category', False)
        instance = super().update(instance, validated_data)
        instance._remember_place_category = remember
        return instance

    def get_owner_name(self, obj):
        owner = obj.owner
        if owner is None:
            return ''
        employee = getattr(owner, 'employee', None) if hasattr(owner, 'employee') else None
        if employee is not None:
            return employee.name
        return f'{owner.last_name}{owner.first_name}' or owner.username


class IncomeSourceSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(source='case.case_number', read_only=True, default='')
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    company_name = serializers.CharField(source='company.name', read_only=True, default='')

    class Meta:
        model = IncomeSource
        fields = '__all__'


class VehicleUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleUsage
        fields = '__all__'


class AccountingProjectSerializer(serializers.ModelSerializer):
    income_total = serializers.SerializerMethodField()
    expense_total = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    income_count = serializers.SerializerMethodField()
    expense_count = serializers.SerializerMethodField()

    class Meta:
        model = AccountingProject
        fields = '__all__'

    def decimal_to_number(self, value):
        if value is None:
            return 0
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    def get_income_total(self, obj):
        if not obj.pk:
            return 0
        total = sum((income.amount for income in obj.project_incomes.all()), Decimal('0'))
        return self.decimal_to_number(total)

    def get_expense_total(self, obj):
        if not obj.pk:
            return 0
        total = sum((expense.amount for expense in obj.project_expenses.all()), Decimal('0'))
        return self.decimal_to_number(total)

    def get_balance(self, obj):
        return self.get_income_total(obj) - self.get_expense_total(obj)

    def get_income_count(self, obj):
        if not obj.pk:
            return 0
        return len(obj.project_incomes.all())

    def get_expense_count(self, obj):
        if not obj.pk:
            return 0
        return len(obj.project_expenses.all())


class AccountingProjectDetailSerializer(serializers.ModelSerializer):
    income_total = serializers.SerializerMethodField()
    expense_total = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    income_count = serializers.SerializerMethodField()
    expense_count = serializers.SerializerMethodField()

    class Meta:
        model = AccountingProject
        fields = '__all__'

    def decimal_to_number(self, value):
        if value is None:
            return 0
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    def get_income_total(self, obj):
        if not obj.pk:
            return 0
        return self.decimal_to_number(obj.project_incomes.aggregate(total=Sum('amount'))['total'])

    def get_expense_total(self, obj):
        if not obj.pk:
            return 0
        return self.decimal_to_number(obj.project_expenses.aggregate(total=Sum('amount'))['total'])

    def get_balance(self, obj):
        return self.get_income_total(obj) - self.get_expense_total(obj)

    def get_income_count(self, obj):
        if not obj.pk:
            return 0
        return obj.project_incomes.count()

    def get_expense_count(self, obj):
        if not obj.pk:
            return 0
        return obj.project_expenses.count()


class AccountingProjectIncomeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingProjectIncome
        fields = '__all__'


class AccountingProjectExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingProjectExpense
        fields = '__all__'


class BusinessDocumentSerializerMixin:
    """帳票共通：明細からの金額計算・発行後の内容ロック・表示用の補助項目（状態は各帳票の Workflow）。"""

    COMMON_READ_ONLY = (
        'amount', 'tax_amount', 'total_amount', 'status_changed_at', 'issued_snapshot',
        'created_by', 'updated_by', 'created_at', 'updated_at',
    )

    def get_workflow(self, instance=None, attrs=None):
        raise NotImplementedError

    def validate(self, attrs):
        attrs = super().validate(attrs)
        workflow = self.get_workflow(self.instance, attrs)
        reject_locked_changes(workflow, self.instance, attrs)
        if self.instance is not None and not workflow.is_editable(self.instance):
            for name in ('line_items', 'amount', 'tax_amount', 'total_amount'):
                attrs.pop(name, None)
            return attrs
        line_items = attrs.get('line_items')
        if line_items is None and self.instance is not None:
            line_items = self.instance.line_items
        try:
            normalized_items, summary = calculate_voucher_amounts(line_items or [])
        except VoucherCalculationError as exc:
            error = {'line_items': str(exc)}
            if exc.row:
                error['line_item_row'] = exc.row  # 1 始まり。画面はこの行にだけ誤りを表示する
            raise serializers.ValidationError(error)
        attrs['amount'] = summary['subtotal']
        attrs['tax_amount'] = summary['tax_total']
        attrs['total_amount'] = summary['total']
        if self.uses_service_items(attrs):
            # P4：line_key・サービス項目のスナップショット・委託底価は後端が作る（客户端の値は使わない）
            try:
                normalized_items, costs, self._newly_used_service_items = apply_service_lines(
                    normalized_items,
                    getattr(self.instance, 'line_items', None),
                    getattr(self.instance, 'internal_line_costs', None),
                )
            except ServiceLineError as exc:
                error = {'line_items': str(exc)}
                if exc.row:
                    error['line_item_row'] = exc.row
                raise serializers.ValidationError(error)
            attrs['internal_line_costs'] = costs
        else:
            normalized_items = strip_service_keys(normalized_items)
        attrs['line_items'] = normalized_items
        return attrs

    def uses_service_items(self, attrs):
        """サービス項目を明細で使える帳票か（P4 第 1 段階：見積書・請求書のみ）。"""
        return False

    def create(self, validated_data):
        instance = super().create(validated_data)
        mark_used(getattr(self, '_newly_used_service_items', None))
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        mark_used(getattr(self, '_newly_used_service_items', None))
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        _, summary = calculate_voucher_amounts(data.get('line_items') or [])
        data['tax_summary'] = {key: decimal_to_number(value) for key, value in summary.items()}
        workflow = self.get_workflow(instance)
        status = getattr(instance, workflow.status_field) or ''
        labels = dict(instance._meta.get_field(workflow.status_field).choices)
        data['document_kind'] = workflow.kind
        data['status_value'] = status
        data['status_display'] = labels.get(status, '状態未設定（旧データ）')
        data['is_editable'] = workflow.is_editable(instance)
        data['allowed_transitions'] = [
            {'value': target, 'label': labels.get(target, target)} for target in workflow.allowed_targets(status)
        ]
        data['case_number'] = instance.case.case_number if instance.case_id else ''
        data['customer_name'] = instance.customer.name if instance.customer_id else ''
        data['company_name'] = instance.company.name if instance.company_id else ''
        # 委託底価は底価権限者にだけ返す（それ以外の人には項目自体を出さない）
        if hasattr(instance, 'internal_line_costs') and can_view_floor_price(self.context):
            data['internal_line_costs'] = instance.internal_line_costs or []
        return data


class AccountingVoucherSerializer(BusinessDocumentSerializerMixin, serializers.ModelSerializer):
    voucher_type_display = serializers.CharField(source='get_voucher_type_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    source_estimate_number = serializers.CharField(source='source_estimate.estimate_number', read_only=True, default='')
    source_contract_number = serializers.CharField(source='source_contract.contract_number', read_only=True, default='')
    source_invoice_number = serializers.CharField(source='source_invoice.voucher_number', read_only=True, default='')

    class Meta:
        model = AccountingVoucher
        exclude = ('internal_line_costs',)  # 底価は to_representation で権限者にだけ付ける
        read_only_fields = (
            'voucher_number', 'invoice_status', 'receipt_status', 'paid_date',
        ) + BusinessDocumentSerializerMixin.COMMON_READ_ONLY

    def get_workflow(self, instance=None, attrs=None):
        voucher_type = (attrs or {}).get('voucher_type') or getattr(instance, 'voucher_type', None)
        return INVOICE_WORKFLOW if voucher_type == AccountingVoucher.VOUCHER_TYPE_INVOICE else RECEIPT_WORKFLOW

    def uses_service_items(self, attrs):
        voucher_type = attrs.get('voucher_type') or getattr(self.instance, 'voucher_type', None)
        return voucher_type == AccountingVoucher.VOUCHER_TYPE_INVOICE

    def validate(self, attrs):
        attrs = super().validate(attrs)
        voucher_type = attrs.get('voucher_type') or getattr(self.instance, 'voucher_type', None)
        source_invoice = attrs.get('source_invoice')
        if source_invoice is not None:
            if voucher_type != AccountingVoucher.VOUCHER_TYPE_RECEIPT:
                raise serializers.ValidationError({'source_invoice': '元の請求書は領収書にだけ指定できます。'})
            if source_invoice.voucher_type != AccountingVoucher.VOUCHER_TYPE_INVOICE:
                raise serializers.ValidationError({'source_invoice': '請求書を指定してください。'})
        if voucher_type == AccountingVoucher.VOUCHER_TYPE_RECEIPT:
            for name in ('source_estimate', 'source_contract'):
                if attrs.get(name) is not None:
                    raise serializers.ValidationError({name: '領収書には元の請求書だけを指定できます。'})
        return attrs

    def create(self, validated_data):
        # 新規作成は下書きから。状態の列は自分の種別の列だけを使う。
        if validated_data.get('voucher_type') == AccountingVoucher.VOUCHER_TYPE_INVOICE:
            validated_data['invoice_status'] = INVOICE_WORKFLOW_DRAFT
        else:
            validated_data['receipt_status'] = RECEIPT_WORKFLOW_DRAFT
        return super().create(validated_data)


class EstimateSerializer(BusinessDocumentSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Estimate
        exclude = ('internal_line_costs',)  # 底価は to_representation で権限者にだけ付ける
        read_only_fields = ('estimate_number', 'status') + BusinessDocumentSerializerMixin.COMMON_READ_ONLY

    def get_workflow(self, instance=None, attrs=None):
        return ESTIMATE_WORKFLOW

    def uses_service_items(self, attrs):
        return True


class ContractSerializer(BusinessDocumentSerializerMixin, serializers.ModelSerializer):
    source_estimate_number = serializers.CharField(source='source_estimate.estimate_number', read_only=True, default='')

    class Meta:
        model = Contract
        fields = '__all__'
        read_only_fields = ('contract_number', 'status', 'signed_date') + BusinessDocumentSerializerMixin.COMMON_READ_ONLY

    def get_workflow(self, instance=None, attrs=None):
        return CONTRACT_WORKFLOW

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and end < start:
            raise serializers.ValidationError({'end_date': '契約終了日は開始日以降にしてください。'})
        return attrs


class VoucherTransitionSerializer(serializers.Serializer):
    status = serializers.CharField()
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    date = serializers.DateField(required=False, allow_null=True)
    # 画面で見ていた現在の状態（任意）。現在と違えば 409（古い画面・二重操作の防止）
    expected_status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # P6：暫定価格のサービス項目を含む帳票を発行するときの明示的な確認
    confirm_provisional = serializers.BooleanField(required=False, default=False)


class VoucherStatusHistorySerializer(serializers.ModelSerializer):
    from_status_display = serializers.SerializerMethodField()
    to_status_display = serializers.SerializerMethodField()
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = VoucherStatusHistory
        fields = ('id', 'document_kind', 'voucher_number', 'from_status', 'from_status_display', 'to_status',
                  'to_status_display', 'version', 'reason', 'snapshot', 'changed_by_name', 'changed_at')

    def _label(self, obj, value):
        field = 'invoice_status' if obj.document_kind == 'invoice' else 'receipt_status'
        return dict(AccountingVoucher._meta.get_field(field).choices).get(value, '状態未設定（旧データ）')

    def get_from_status_display(self, obj):
        return self._label(obj, obj.from_status)

    def get_to_status_display(self, obj):
        return self._label(obj, obj.to_status)

    def get_changed_by_name(self, obj):
        user = obj.changed_by
        if user is None:
            return ''
        employee = getattr(user, 'employee', None) if hasattr(user, 'employee') else None
        return employee.name if employee is not None else user.get_username()


class VoucherItemTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherItemTemplate
        fields = '__all__'


class ServiceItemSerializer(serializers.ModelSerializer):
    """サービス項目（P4）。委託底価は底価権限者にだけ返し、それ以外の人からの変更は拒否する。"""

    professional_type_display = serializers.CharField(source='get_professional_type_display', read_only=True)
    tax_category_display = serializers.CharField(source='get_tax_category_display', read_only=True)
    price_type_display = serializers.CharField(source='get_price_type_display', read_only=True)
    price_status_display = serializers.CharField(source='get_price_status_display', read_only=True)
    price_confirmed_by_name = serializers.SerializerMethodField()
    is_used = serializers.SerializerMethodField()

    class Meta:
        model = ServiceItem
        fields = (
            'id', 'code', 'category', 'name', 'default_price', 'price_type', 'price_type_display', 'floor_price',
            'professional_type', 'professional_type_display', 'tax_category', 'tax_category_display', 'unit',
            'price_status', 'price_status_display', 'price_confirmed_at', 'price_confirmed_by_name',
            'is_active', 'note', 'sort_order', 'is_used', 'created_at', 'updated_at',
        )
        # 価格の状態は「価格を確定」操作（confirm-price）でだけ変わる。価格を変えると暫定に戻る（views 側）
        read_only_fields = ('code', 'price_status', 'price_confirmed_at', 'created_at', 'updated_at')

    def get_price_confirmed_by_name(self, obj):
        user = obj.price_confirmed_by
        if user is None:
            return ''
        employee = getattr(user, 'employee', None) if hasattr(user, 'employee') else None
        return employee.name if employee else user.get_username()

    def get_is_used(self, obj):
        return obj.first_used_at is not None

    def validate_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('項目名を入力してください。')
        return value

    def validate(self, attrs):
        if 'floor_price' in self.initial_data and not can_view_floor_price(self.context):
            raise serializers.ValidationError({'floor_price': '委託底価を変更する権限がありません。'})
        for name in ('default_price', 'floor_price'):
            value = attrs.get(name)
            if value is not None and value < 0:
                raise serializers.ValidationError({name: '金額は 0 以上で入力してください。'})
        category = (attrs.get('category', getattr(self.instance, 'category', '')) or '').strip()
        name = attrs.get('name', getattr(self.instance, 'name', ''))
        duplicate = ServiceItem.objects.filter(category=category, name=name)
        if self.instance is not None:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({'name': '同じ分類に同じ名前の項目があります。'})
        attrs['category'] = category
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not can_view_floor_price(self.context):
            data.pop('floor_price', None)
        return data


GUARANTOR_TEMPLATE_SNAPSHOT_FIELDS = (
    'guarantor_name', 'guarantor_name_en', 'guarantor_phone', 'guarantor_address', 'guarantor_address_en',
    'guarantor_birth_date', 'guarantor_nationality', 'guarantor_visa_status', 'guarantor_occupation',
    'guarantor_relationship', 'guarantor_company_name',
)


def guarantor_template_snapshot(template):
    """担保人テンプレートの内容を、選択した時点のスナップショットにする（後端が DB から作る）。"""
    data = {name: getattr(template, name) for name in GUARANTOR_TEMPLATE_SNAPSHOT_FIELDS}
    data['guarantor_birth_date'] = template.guarantor_birth_date.isoformat() if template.guarantor_birth_date else ''
    data.update({
        'guarantor_template_id': str(template.pk), 'template_name': template.name,
        'template_version': template.updated_at.isoformat() if template.updated_at else '',
    })
    return {key: ('' if value is None else value) for key, value in data.items()}


class VisaReturnApplicationSerializer(serializers.ModelSerializer):
    guarantor_template_name = serializers.CharField(source='guarantor_template.name', read_only=True, default='')

    class Meta:
        model = VisaReturnApplication
        fields = '__all__'
        # guarantor_snapshot は後端だけが作る（画面・API から送られた値は受け付けない）
        read_only_fields = ('created_by', 'created_at', 'updated_at', 'guarantor_snapshot')

    def validate_guarantor_template(self, template):
        current = getattr(self.instance, 'guarantor_template_id', None)
        if template is not None and not template.is_active and template.pk != current:
            raise serializers.ValidationError('停止中の担保人テンプレートは選択できません。')
        return template

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # guarantor_snapshot は読み取り専用で、ここで後端が決める（どの項目をどう送っても迂回できない）。
        #  - テンプレートを選んだ（変えた）、または保存済みの快照が別のテンプレートのもの：DB のテンプレートから作り直す。
        #  - 同じテンプレートのまま：保存済みを保つ。
        #  - テンプレートを外した：空にする（画面の担保人欄は手入力として列・form_data に残る）。
        #  - テンプレートなし（旧データ）：保存済みのまま変えない。
        # 手入力の担保人は guarantor_* 列と form_data に入り、スナップショットより優先される（resolve_guarantor）。
        instance = self.instance
        stored = instance.guarantor_snapshot if instance is not None and isinstance(instance.guarantor_snapshot, dict) else {}
        template = attrs['guarantor_template'] if 'guarantor_template' in attrs else getattr(instance, 'guarantor_template', None)
        if template is not None:
            changed = template.pk != getattr(instance, 'guarantor_template_id', None)
            if changed or str(stored.get('guarantor_template_id') or '') != str(template.pk):
                attrs['guarantor_snapshot'] = guarantor_template_snapshot(template)
        elif 'guarantor_template' in attrs and getattr(instance, 'guarantor_template_id', None):
            attrs['guarantor_snapshot'] = {}
        return attrs


class VisaReturnPdfGenerationSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    guarantor_template_name = serializers.CharField(source='guarantor_template.name', read_only=True, default='')
    created_by_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = VisaReturnPdfGeneration
        fields = ('id', 'application', 'status', 'status_display', 'method', 'method_display', 'template_name',
                  'template_version', 'guarantor_template', 'guarantor_template_name', 'guarantor_template_version',
                  'file_sha256', 'file_size', 'error_code', 'error_message', 'details', 'created_by_name',
                  'created_at', 'download_url')

    def get_created_by_name(self, obj):
        user = obj.created_by
        if user is None:
            return ''
        employee = getattr(user, 'employee', None) if hasattr(user, 'employee') else None
        return employee.name if employee is not None else user.get_username()

    def get_download_url(self, obj):
        # 成功してファイルが実在する記録だけにダウンロード先を返す
        if obj.status != obj.STATUS_SUCCESS or not obj.file or not obj.file.storage.exists(obj.file.name):
            return None
        return f'/accounting/visa-return-applications/{obj.application_id}/pdf-generations/{obj.pk}/download/'


class VisaGuarantorTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaGuarantorTemplate
        fields = '__all__'


class SeifuNoticePdfGenerationSerializer(serializers.ModelSerializer):
    """生成記録（成功のみ）。ダウンロードは download/ から（ファイルの実在を確認する）。"""

    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')

    class Meta:
        model = SeifuNoticePdfGeneration
        fields = ('id', 'record', 'status', 'recipient_name', 'permit_number', 'notice_number', 'issue_date',
                  'template_key', 'template_version', 'font_version', 'method', 'file_sha256', 'file_size',
                  'created_by', 'created_by_username', 'created_at')
        read_only_fields = fields


class SeifuNoticePdfRecordSerializer(serializers.ModelSerializer):
    """P5：入力は宛名・許可番号・通知日だけ。通知書番号・テンプレート・座標・字体は後端が決める。

    旧データの text_items（任意文字）は読み取り専用で残し、更新でも消さない（旧記録の内容を保つため）。
    """

    text_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    notice_number = serializers.SerializerMethodField()
    template_name = serializers.SerializerMethodField()
    text_items = serializers.JSONField(read_only=True)
    is_legacy = serializers.SerializerMethodField()
    latest_generation = serializers.SerializerMethodField()
    generation_count = serializers.SerializerMethodField()

    class Meta:
        model = SeifuNoticePdfRecord
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at', 'text_items')

    def get_text_count(self, obj):
        return sum(bool(value) for value in (obj.recipient_name, obj.permit_number, obj.issue_date))

    def get_notice_number(self, obj):
        return derive_notice_number(obj.permit_number)

    def get_template_name(self, obj):
        return TEMPLATE_NAME if (obj.template_key or TEMPLATE_KEY) == TEMPLATE_KEY else obj.template_key

    def get_is_legacy(self, obj):
        # P5 以前の任意文字の記録（固定 3 項目が無い）。編集して 3 項目を入れると生成できる
        return not (obj.recipient_name and obj.permit_number and obj.issue_date)

    def _generations(self, obj):
        cache = getattr(obj, '_generation_cache', None)
        if cache is None:
            cache = list(obj.generations.order_by('-created_at', '-id')[:1])
            obj._generation_cache = cache
        return cache

    def get_latest_generation(self, obj):
        rows = self._generations(obj)
        return SeifuNoticePdfGenerationSerializer(rows[0]).data if rows else None

    def get_generation_count(self, obj):
        return obj.generations.count()

    def validate_title(self, value):
        if not str(value or '').strip():
            raise serializers.ValidationError('记录名称不能为空。')
        return str(value).strip()

    @staticmethod
    def _run(normalizer, value):
        try:
            return normalizer(value)
        except SeifuPdfError as exc:
            raise serializers.ValidationError(exc.message) from exc

    def validate_recipient_name(self, value):
        return self._run(normalize_recipient_name, value)

    def validate_permit_number(self, value):
        return self._run(normalize_permit_number, value)

    def validate_issue_date(self, value):
        return self._run(normalize_issue_date, value)

    def validate_template_key(self, value):
        value = value or TEMPLATE_KEY
        if value != TEMPLATE_KEY:
            raise serializers.ValidationError('現在利用できるテンプレートではありません。')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        unknown = sorted(set(getattr(self, 'initial_data', {}) or {}) & {
            'notice_number', 'text_items', 'x', 'y', 'font', 'font_size', 'font_family', 'items', 'coordinates',
            'background', 'template_version', 'course_years', 'enrollment_period'})
        if unknown:
            # 派生値・座標・字体などは客户端から指定できない（黙って無視せず、誤用として知らせる）
            raise serializers.ValidationError({name: 'この項目は指定できません（サーバーが決めます）。' for name in unknown})
        if self.instance is None:
            attrs.setdefault('template_key', TEMPLATE_KEY)
            required = {
                'recipient_name': '宛名を入力してください。',
                'permit_number': '許可番号を入力してください。',
                'issue_date': '通知日を入力してください。',
            }
            for field, message in required.items():
                if not attrs.get(field):
                    raise serializers.ValidationError({field: message})
        name = attrs.get('recipient_name', getattr(self.instance, 'recipient_name', None))
        permit = attrs.get('permit_number', getattr(self.instance, 'permit_number', None))
        if name and permit:
            # 保存の時点で字形・版面に収まるかを確認する（字体が未設定なら生成時に字体エラーとして止める）
            try:
                check_layout(name, permit)
            except SeifuPdfError as exc:
                if exc.code not in ('font_missing', 'font_broken', 'font_mismatch'):
                    raise serializers.ValidationError({exc.field or 'recipient_name': exc.message}) from exc
        return attrs


class TaxRenewalVoucherRecordSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    case_number = serializers.CharField(source='case.case_number', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    selected_template_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = TaxRenewalVoucherRecord
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def get_selected_template_count(self, obj):
        if not isinstance(obj.selected_templates, list):
            return 0
        return len(obj.selected_templates)

    def validate_title(self, value):
        if not str(value or '').strip():
            raise serializers.ValidationError('记录名称不能为空。')
        return str(value).strip()

    def validate_selected_templates(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('selected_templates 必须是 list。')
        valid_keys = {template['key'] for template in get_tax_renewal_templates()}
        invalid_keys = [key for key in value if key not in valid_keys]
        if invalid_keys:
            raise serializers.ValidationError(f'未知模板：{", ".join(map(str, invalid_keys))}')
        return list(dict.fromkeys(value))

    def validate_form_data(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('form_data 必须是 object。')
        dependents = value.get('dependents')
        if dependents is not None and not isinstance(dependents, list):
            raise serializers.ValidationError('dependents 必须是数组。')
        return value

    def validate_generated_files(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('generated_files 必须是 list。')
        return value

    def validate(self, attrs):
        category = attrs.get('category') or getattr(self.instance, 'category', TaxRenewalVoucherRecord.CATEGORY_RENEWAL)
        has_employees = attrs.get('has_employees')
        if has_employees is None:
            has_employees = getattr(self.instance, 'has_employees', False)
        has_dependents = attrs.get('has_dependents')
        if has_dependents is None:
            has_dependents = getattr(self.instance, 'has_dependents', False)
        selected_templates = attrs.get('selected_templates')
        if selected_templates is None and self.instance is not None:
            selected_templates = self.instance.selected_templates
        selected_templates = selected_templates or []

        templates = {template['key']: template for template in get_tax_renewal_templates()}
        for key in selected_templates:
            template = templates.get(key)
            if not template:
                continue
            if template['category'] != category:
                raise serializers.ValidationError({'selected_templates': '选择的模板不属于当前分类。'})
            if not template['file_exists']:
                raise serializers.ValidationError({'selected_templates': f'{template["name"]} 模板文件不存在。'})
            if template['condition'] == 'has_employees' and not has_employees:
                raise serializers.ValidationError({'selected_templates': f'{template["name"]} 只有公司有雇员时才可选择。'})
            if template['condition'] == 'has_dependents' and not has_dependents:
                raise serializers.ValidationError({'selected_templates': f'{template["name"]} 只有有抚养人时才可选择。'})

        return attrs


class TaxRenewalAgentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRenewalAgentTemplate
        fields = '__all__'

    def validate_name(self, value):
        if not str(value or '').strip():
            raise serializers.ValidationError('模板名称不能为空。')
        return str(value).strip()

    def validate_agent_name(self, value):
        if not str(value or '').strip():
            raise serializers.ValidationError('代理人姓名不能为空。')
        return str(value).strip()
