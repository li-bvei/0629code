import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '../layouts/AdminLayout.vue'
import AccountingDashboardPage from '../pages/accounting/AccountingDashboardPage.vue'
import AccountingProjectDetailPage from '../pages/accounting/AccountingProjectDetailPage.vue'
import AccountingProjectFormPage from '../pages/accounting/AccountingProjectFormPage.vue'
import AccountingProjectListPage from '../pages/accounting/AccountingProjectListPage.vue'
import AccountingVouchersPage from '../pages/AccountingVouchersPage.vue'
import ExpenseCategoryFormPage from '../pages/accounting/ExpenseCategoryFormPage.vue'
import ExpenseCategoryListPage from '../pages/accounting/ExpenseCategoryListPage.vue'
import ExpenseFormPage from '../pages/accounting/ExpenseFormPage.vue'
import ExpenseListPage from '../pages/accounting/ExpenseListPage.vue'
import IncomeSourceFormPage from '../pages/accounting/IncomeSourceFormPage.vue'
import IncomeSourceListPage from '../pages/accounting/IncomeSourceListPage.vue'
import VehicleUsageFormPage from '../pages/accounting/VehicleUsageFormPage.vue'
import VehicleUsageListPage from '../pages/accounting/VehicleUsageListPage.vue'
import CaseDetailPage from '../pages/CaseDetailPage.vue'
import CasesPage from '../pages/CasesPage.vue'
import CompanyDetailPage from '../pages/CompanyDetailPage.vue'
import CompaniesPage from '../pages/CompaniesPage.vue'
import CustomerDetailPage from '../pages/CustomerDetailPage.vue'
import CustomersPage from '../pages/CustomersPage.vue'
import DashboardPage from '../pages/DashboardPage.vue'
import DocumentsPage from '../pages/DocumentsPage.vue'
import EmployeesPage from '../pages/EmployeesPage.vue'
import LoginPage from '../pages/LoginPage.vue'
import PlaceholderPage from '../pages/PlaceholderPage.vue'
import ReceptionNewPage from '../pages/ReceptionNewPage.vue'
import RemindersPage from '../pages/RemindersPage.vue'
import SeifuNoticePdfTextPage from '../pages/SeifuNoticePdfTextPage.vue'
import TasksPage from '../pages/TasksPage.vue'
import TaxRenewalVouchersPage from '../pages/TaxRenewalVouchersPage.vue'
import TimelinesPage from '../pages/TimelinesPage.vue'
import VisaReturnApplicationsPage from '../pages/VisaReturnApplicationsPage.vue'
import VoucherPlaceholderPage from '../pages/VoucherPlaceholderPage.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
      meta: { public: true },
    },
    {
      path: '/',
      component: AdminLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: DashboardPage,
        },
        {
          path: 'reception/new',
          name: 'reception-new',
          component: ReceptionNewPage,
        },
        {
          path: 'cases',
          name: 'cases',
          component: CasesPage,
        },
        {
          path: 'cases/:id',
          name: 'case-detail',
          component: CaseDetailPage,
        },
        {
          path: 'customers',
          name: 'customers',
          component: CustomersPage,
        },
        {
          path: 'customers/:id',
          name: 'customer-detail',
          component: CustomerDetailPage,
        },
        {
          path: 'companies',
          name: 'companies',
          component: CompaniesPage,
        },
        {
          path: 'companies/:id',
          name: 'company-detail',
          component: CompanyDetailPage,
        },
        {
          path: 'employees',
          name: 'employees',
          component: EmployeesPage,
        },
        {
          path: 'tasks',
          name: 'tasks',
          component: TasksPage,
        },
        {
          path: 'reminders',
          name: 'reminders',
          component: RemindersPage,
        },
        {
          path: 'timelines',
          name: 'timelines',
          component: TimelinesPage,
        },
        {
          path: 'documents',
          name: 'documents',
          component: DocumentsPage,
        },
        {
          path: 'accounting',
          name: 'accounting',
          component: AccountingDashboardPage,
        },
        {
          path: 'accounting/expenses',
          name: 'accounting-expenses',
          component: ExpenseListPage,
        },
        {
          path: 'accounting/expenses/create',
          name: 'accounting-expense-create',
          component: ExpenseFormPage,
        },
        {
          path: 'accounting/expenses/:id/edit',
          name: 'accounting-expense-edit',
          component: ExpenseFormPage,
        },
        {
          path: 'accounting/expense-categories',
          name: 'accounting-expense-categories',
          component: ExpenseCategoryListPage,
        },
        {
          path: 'accounting/expense-categories/create',
          name: 'accounting-expense-category-create',
          component: ExpenseCategoryFormPage,
        },
        {
          path: 'accounting/expense-categories/:id/edit',
          name: 'accounting-expense-category-edit',
          component: ExpenseCategoryFormPage,
        },
        {
          path: 'accounting/income-sources',
          name: 'accounting-income-sources',
          component: IncomeSourceListPage,
        },
        {
          path: 'accounting/income-sources/create',
          name: 'accounting-income-source-create',
          component: IncomeSourceFormPage,
        },
        {
          path: 'accounting/income-sources/:id/edit',
          name: 'accounting-income-source-edit',
          component: IncomeSourceFormPage,
        },
        {
          path: 'accounting/vehicle-usages',
          name: 'accounting-vehicle-usages',
          component: VehicleUsageListPage,
        },
        {
          path: 'accounting/vehicle-usages/create',
          name: 'accounting-vehicle-usage-create',
          component: VehicleUsageFormPage,
        },
        {
          path: 'accounting/vehicle-usages/:id/edit',
          name: 'accounting-vehicle-usage-edit',
          component: VehicleUsageFormPage,
        },
        {
          path: 'accounting/projects',
          name: 'accounting-projects',
          component: AccountingProjectListPage,
        },
        {
          path: 'accounting/projects/new',
          name: 'accounting-project-new',
          component: AccountingProjectFormPage,
        },
        {
          path: 'accounting/projects/:id',
          name: 'accounting-project-detail',
          component: AccountingProjectDetailPage,
        },
        {
          path: 'accounting/projects/:id/edit',
          name: 'accounting-project-edit',
          component: AccountingProjectFormPage,
        },
        {
          path: 'reports',
          name: 'reports',
          component: PlaceholderPage,
          props: { title: '帳票管理' },
        },
        {
          path: 'vouchers',
          redirect: '/vouchers/invoices',
        },
        {
          path: 'vouchers/invoices',
          name: 'voucher-invoices',
          component: AccountingVouchersPage,
        },
        {
          path: 'vouchers/visa-return',
          name: 'voucher-visa-return',
          component: VisaReturnApplicationsPage,
        },
        {
          path: 'vouchers/tax-renewal',
          name: 'voucher-tax-renewal',
          component: TaxRenewalVouchersPage,
        },
        {
          path: 'vouchers/seifu-notice',
          name: 'voucher-seifu-notice',
          component: SeifuNoticePdfTextPage,
        },
        {
          path: 'vouchers/estimates',
          name: 'voucher-estimates',
          component: VoucherPlaceholderPage,
          props: { title: '見積書' },
        },
        {
          path: 'vouchers/contracts',
          name: 'voucher-contracts',
          component: VoucherPlaceholderPage,
          props: { title: '契約書' },
        },
        {
          path: 'vouchers/certificates',
          name: 'voucher-certificates',
          component: VoucherPlaceholderPage,
          props: { title: '証明書' },
        },
        {
          path: 'vouchers/others',
          name: 'voucher-others',
          component: VoucherPlaceholderPage,
          props: { title: 'その他帳票' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: PlaceholderPage,
          props: { title: '設定' },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.path.startsWith('/admin')) {
    return true
  }

  if (!auth.user && !auth.loading) {
    await auth.fetchMe().catch(() => null)
  }

  if (to.meta.public) {
    if (to.path === '/login' && auth.isAuthenticated) {
      return { path: '/dashboard' }
    }

    return true
  }

  if (!auth.isAuthenticated) {
    return {
      path: '/login',
      query: { redirect: to.fullPath },
    }
  }

  return true
})

export default router
