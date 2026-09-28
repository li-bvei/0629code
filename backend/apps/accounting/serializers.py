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
    IncomeSource,
    SeifuNoticePdfRecord,
    TaxRenewalAgentTemplate,
    TaxRenewalVoucherRecord,
    VehicleUsage,
    VisaGuarantorTemplate,
    VisaReturnApplication,
    VoucherItemTemplate,
)
from .seifu_notice_pdf import template_doc, validate_items
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


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'


class ExpenseSerializer(serializers.ModelSerializer):
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
            raise serializers.ValidationError({'line_items': str(exc)})
        attrs['line_items'] = normalized_items
        attrs['amount'] = summary['subtotal']
        attrs['tax_amount'] = summary['tax_total']
        attrs['total_amount'] = summary['total']
        return attrs

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
        return data


class AccountingVoucherSerializer(BusinessDocumentSerializerMixin, serializers.ModelSerializer):
    voucher_type_display = serializers.CharField(source='get_voucher_type_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    source_estimate_number = serializers.CharField(source='source_estimate.estimate_number', read_only=True, default='')
    source_contract_number = serializers.CharField(source='source_contract.contract_number', read_only=True, default='')
    source_invoice_number = serializers.CharField(source='source_invoice.voucher_number', read_only=True, default='')

    class Meta:
        model = AccountingVoucher
        fields = '__all__'
        read_only_fields = (
            'voucher_number', 'invoice_status', 'receipt_status', 'paid_date',
        ) + BusinessDocumentSerializerMixin.COMMON_READ_ONLY

    def get_workflow(self, instance=None, attrs=None):
        voucher_type = (attrs or {}).get('voucher_type') or getattr(instance, 'voucher_type', None)
        return INVOICE_WORKFLOW if voucher_type == AccountingVoucher.VOUCHER_TYPE_INVOICE else RECEIPT_WORKFLOW

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
        fields = '__all__'
        read_only_fields = ('estimate_number', 'status') + BusinessDocumentSerializerMixin.COMMON_READ_ONLY

    def get_workflow(self, instance=None, attrs=None):
        return ESTIMATE_WORKFLOW


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


class VoucherItemTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherItemTemplate
        fields = '__all__'


class VisaReturnApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaReturnApplication
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at')


class VisaGuarantorTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisaGuarantorTemplate
        fields = '__all__'


class SeifuNoticePdfRecordSerializer(serializers.ModelSerializer):
    text_count = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = SeifuNoticePdfRecord
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at')

    def get_text_count(self, obj):
        if not isinstance(obj.text_items, list):
            return 0
        return len([item for item in obj.text_items if str(item.get('text') or '').strip()])

    def validate_title(self, value):
        if not str(value or '').strip():
            raise serializers.ValidationError('记录名称不能为空。')
        return str(value).strip()

    def validate_text_items(self, value):
        if value is None:
            value = []
        if not isinstance(value, list):
            raise serializers.ValidationError('text_items 必须是 list。')
        if not value:
            return []

        try:
            doc = template_doc()
        except FileNotFoundError as exc:
            raise serializers.ValidationError(str(exc))

        try:
            return validate_items(doc, value, allow_empty_text=True, require_non_empty=False)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        finally:
            doc.close()


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
