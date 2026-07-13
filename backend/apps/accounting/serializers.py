from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db.models import Sum
from rest_framework import serializers

from .models import (
    AccountingProject,
    AccountingProjectExpense,
    AccountingProjectIncome,
    AccountingVoucher,
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


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = '__all__'


class IncomeSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeSource
        fields = '__all__'


class VehicleUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleUsage
        fields = '__all__'


class AccountingProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingProject
        fields = '__all__'


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


class AccountingVoucherSerializer(serializers.ModelSerializer):
    voucher_type_display = serializers.CharField(source='get_voucher_type_display', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = AccountingVoucher
        fields = '__all__'
        read_only_fields = (
            'voucher_number',
            'amount',
            'tax_amount',
            'total_amount',
            'created_by',
            'created_at',
            'updated_at',
        )

    def calculate_amounts(self, line_items):
        normalized_items = []
        total_amount = Decimal('0')

        for item in line_items or []:
            if not isinstance(item, dict):
                continue
            try:
                quantity = Decimal(str(item.get('quantity') or 0))
                unit_price = Decimal(str(item.get('unit_price') or 0))
            except (InvalidOperation, ValueError):
                raise serializers.ValidationError({'line_items': '数量と単価は数字で入力してください。'})
            line_total = (quantity * unit_price).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            normalized_items.append({
                **item,
                'quantity': int(quantity) if quantity == quantity.to_integral_value() else float(quantity),
                'unit_price': int(unit_price) if unit_price == unit_price.to_integral_value() else float(unit_price),
                'line_total': int(line_total),
            })
            total_amount += line_total

        tax_excluded = (total_amount / Decimal('1.1')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        tax_amount = total_amount - tax_excluded
        return normalized_items, tax_excluded, tax_amount, total_amount

    def validate(self, attrs):
        line_items = attrs.get('line_items')
        if line_items is None and self.instance is not None:
            line_items = self.instance.line_items

        normalized_items, amount, tax_amount, total_amount = self.calculate_amounts(line_items or [])
        attrs['line_items'] = normalized_items
        attrs['amount'] = amount
        attrs['tax_amount'] = tax_amount
        attrs['total_amount'] = total_amount
        return attrs


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
