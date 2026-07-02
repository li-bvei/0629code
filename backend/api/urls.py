from rest_framework.routers import DefaultRouter
from django.urls import path

from apps.cases.views import CaseViewSet
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
router.register('tasks', TaskViewSet, basename='task')
router.register('reminders', ReminderViewSet, basename='reminder')
router.register('timelines', TimelineViewSet, basename='timeline')
router.register('documents', DocumentViewSet, basename='document')

urlpatterns = [
    *router.urls,
    path('dashboard/deadlines/', DashboardDeadlinesView.as_view(), name='dashboard-deadlines'),
    path('receptions/', ReceptionCreateView.as_view(), name='reception-create'),
]
