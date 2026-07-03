from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    IncomeSourceViewSet,
    VehicleUsageViewSet,
    dashboard,
)

router = DefaultRouter()
router.register('expenses', ExpenseViewSet, basename='accounting-expense')
router.register('expense-categories', ExpenseCategoryViewSet, basename='accounting-expense-category')
router.register('income-sources', IncomeSourceViewSet, basename='accounting-income-source')
router.register('vehicle-usages', VehicleUsageViewSet, basename='accounting-vehicle-usage')

urlpatterns = [
    path('dashboard/', dashboard, name='accounting-dashboard'),
    *router.urls,
]
