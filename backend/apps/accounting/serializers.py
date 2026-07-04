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
        read_only_fields = ('voucher_number', 'total_amount', 'created_by', 'created_at', 'updated_at')


class VoucherItemTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherItemTemplate
        fields = '__all__'
