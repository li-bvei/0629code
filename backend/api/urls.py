from rest_framework.routers import DefaultRouter
from django.urls import include, path

from apps.cases.views import (
    AcquisitionPlacePresetViewSet,
    CaseApplicationCategoryViewSet,
    CaseChecklistItemViewSet,
    CaseChecklistTemplateItemViewSet,
    CaseChecklistTemplateViewSet,
    CaseStatusSettingViewSet,
    CaseTypeMasterViewSet,
    CaseViewSet,
    ResponsiblePartyPresetViewSet,
    case_checklist_deletion_history,
    seed_case_checklist_demo_view,
)
from apps.companies.views import CompanyStaffViewSet, CompanyViewSet
from apps.customers.views import CustomerViewSet, FamilyMemberViewSet
from apps.documents.views import DocumentViewSet
from apps.employees.views import EmployeeViewSet
from apps.reminders.views import ReminderViewSet
from apps.tasks.views import TaskViewSet
from apps.timelines.views import TimelineViewSet
from .views import DashboardDeadlinesView, ReceptionCreateView

router = DefaultRouter()
router.register('customers', CustomerViewSet, basename='customer')
router.register('family-members', FamilyMemberViewSet, basename='family-member')
router.register('companies', CompanyViewSet, basename='company')
router.register('company-staff', CompanyStaffViewSet, basename='company-staff')
router.register('employees', EmployeeViewSet, basename='employee')
router.register('cases', CaseViewSet, basename='case')
router.register('case-type-masters', CaseTypeMasterViewSet, basename='case-type-master')
router.register('case-application-categories', CaseApplicationCategoryViewSet, basename='case-application-category')
router.register('case-status-settings', CaseStatusSettingViewSet, basename='case-status-setting')
router.register('case-acquisition-place-presets', AcquisitionPlacePresetViewSet, basename='case-acquisition-place-preset')
router.register('case-responsible-party-presets', ResponsiblePartyPresetViewSet, basename='case-responsible-party-preset')
router.register('case-checklist-templates', CaseChecklistTemplateViewSet, basename='case-checklist-template')
router.register('case-checklist-template-items', CaseChecklistTemplateItemViewSet, basename='case-checklist-template-item')
router.register('case-checklist-items', CaseChecklistItemViewSet, basename='case-checklist-item')
router.register('tasks', TaskViewSet, basename='task')
router.register('reminders', ReminderViewSet, basename='reminder')
router.register('timelines', TimelineViewSet, basename='timeline')
router.register('documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('auth/', include('apps.authentication.urls')),
    *router.urls,
    path('accounting/', include('apps.accounting.urls')),
    path('case-checklist-deletion-history/', case_checklist_deletion_history, name='case-checklist-deletion-history'),
    path('case-checklist-demo/seed/', seed_case_checklist_demo_view, name='case-checklist-demo-seed'),
    path('dashboard/deadlines/', DashboardDeadlinesView.as_view(), name='dashboard-deadlines'),
    path('receptions/', ReceptionCreateView.as_view(), name='reception-create'),
]
