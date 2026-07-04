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
    VehicleUsage,
    VisaReturnApplication,
    VoucherItemTemplate,
)


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
