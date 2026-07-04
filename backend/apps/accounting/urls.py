from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccountingProjectExpenseViewSet,
    AccountingProjectIncomeViewSet,
    AccountingProjectViewSet,
    AccountingVoucherViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    IncomeSourceViewSet,
    VehicleUsageViewSet,
    VoucherItemTemplateViewSet,
    dashboard,
)

router = DefaultRouter()
router.register('expenses', ExpenseViewSet, basename='accounting-expense')
router.register('expense-categories', ExpenseCategoryViewSet, basename='accounting-expense-category')
router.register('income-sources', IncomeSourceViewSet, basename='accounting-income-source')
router.register('vehicle-usages', VehicleUsageViewSet, basename='accounting-vehicle-usage')
router.register('projects', AccountingProjectViewSet, basename='accounting-project')
router.register('project-incomes', AccountingProjectIncomeViewSet, basename='accounting-project-income')
router.register('project-expenses', AccountingProjectExpenseViewSet, basename='accounting-project-expense')
router.register('vouchers', AccountingVoucherViewSet, basename='accounting-voucher')
router.register('voucher-item-templates', VoucherItemTemplateViewSet, basename='accounting-voucher-item-template')

urlpatterns = [
    path('dashboard/', dashboard, name='accounting-dashboard'),
    *router.urls,
]
