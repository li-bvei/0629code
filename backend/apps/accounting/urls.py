from django.urls import path
from rest_framework.routers import DefaultRouter

from .visa_form_fields import visa_form_field_mapping, visa_form_fields, visa_form_fields_preview
from .visa_position_debug import visa_position_config, visa_position_preview
from .seifu_notice_pdf import seifu_notice_generate, seifu_notice_preview, seifu_notice_template
from .zei_pdf_diagnostics import tax_renewal_pdf_diagnostics, tax_renewal_pdf_numbered_sample
from .zei_pdf_position_debug import (
    zei_pdf_position_mapping,
    zei_pdf_position_preview,
    zei_pdf_position_templates,
    zei_pdf_position_test_pdf,
)
from .views import (
    AccountingProjectExpenseViewSet,
    AccountingProjectIncomeViewSet,
    AccountingProjectViewSet,
    AccountingVoucherViewSet,
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    IncomeSourceViewSet,
    SeifuNoticePdfRecordViewSet,
    TaxRenewalAgentTemplateViewSet,
    TaxRenewalVoucherRecordViewSet,
    VehicleUsageViewSet,
    VisaGuarantorTemplateViewSet,
    VisaReturnApplicationViewSet,
    VoucherItemTemplateViewSet,
    dashboard,
    tax_renewal_templates,
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
router.register('tax-renewal-records', TaxRenewalVoucherRecordViewSet, basename='tax-renewal-record')
router.register('tax-renewal-agent-templates', TaxRenewalAgentTemplateViewSet, basename='tax-renewal-agent-template')

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
    path('tax-renewal-templates/', tax_renewal_templates, name='tax-renewal-templates'),
    path('tax-renewal-pdf-diagnostics/', tax_renewal_pdf_diagnostics, name='tax-renewal-pdf-diagnostics'),
    path(
        'tax-renewal-pdf-diagnostics/numbered_sample/',
        tax_renewal_pdf_numbered_sample,
        name='tax-renewal-pdf-numbered-sample',
    ),
    path('zei-pdf-position-debug/templates/', zei_pdf_position_templates, name='zei-pdf-position-debug-templates'),
    path('zei-pdf-position-debug/mapping/', zei_pdf_position_mapping, name='zei-pdf-position-debug-mapping'),
    path('zei-pdf-position-debug/preview/', zei_pdf_position_preview, name='zei-pdf-position-debug-preview'),
    path('zei-pdf-position-debug/test-pdf/', zei_pdf_position_test_pdf, name='zei-pdf-position-debug-test-pdf'),
    *router.urls,
]
