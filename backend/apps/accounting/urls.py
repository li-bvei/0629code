from django.urls import path
from rest_framework.routers import DefaultRouter

from .visa_form_fields import visa_form_field_mapping, visa_form_fields, visa_form_fields_preview
from .visa_position_debug import visa_position_config, visa_position_preview
from .seifu_notice_pdf import seifu_notice_generate, seifu_notice_preview, seifu_notice_template
from .views import (
    AccountingProjectExpenseViewSet,
    AccountingProjectIncomeViewSet,
    AccountingProjectViewSet,
    AccountingVoucherViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    IncomeSourceViewSet,
    SeifuNoticePdfRecordViewSet,
    VehicleUsageViewSet,
    VisaGuarantorTemplateViewSet,
    VisaReturnApplicationViewSet,
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
router.register('visa-return-applications', VisaReturnApplicationViewSet, basename='visa-return-application')
router.register('visa-guarantor-templates', VisaGuarantorTemplateViewSet, basename='visa-guarantor-template')
router.register('seifu-notice-records', SeifuNoticePdfRecordViewSet, basename='seifu-notice-record')

urlpatterns = [
    path('dashboard/', dashboard, name='accounting-dashboard'),
    path('visa-form-fields/', visa_form_fields, name='visa-form-fields'),
    path('visa-form-fields/preview/', visa_form_fields_preview, name='visa-form-fields-preview'),
    path('visa-form-field-mapping/', visa_form_field_mapping, name='visa-form-field-mapping'),
    path('visa-position-debug/config/', visa_position_config, name='visa-position-debug-config'),
    path('visa-position-debug/preview/', visa_position_preview, name='visa-position-debug-preview'),
    path('seifu-notice-pdf/template/', seifu_notice_template, name='seifu-notice-template'),
    path('seifu-notice-pdf/preview/', seifu_notice_preview, name='seifu-notice-preview'),
    path('seifu-notice-pdf/generate/', seifu_notice_generate, name='seifu-notice-generate'),
    *router.urls,
]
