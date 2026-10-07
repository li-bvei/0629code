import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '../layouts/AdminLayout.vue'
const AccountingDashboardPage = () => import('../pages/accounting/AccountingDashboardPage.vue')
const AccountingProjectDetailPage = () => import('../pages/accounting/AccountingProjectDetailPage.vue')
const AccountingProjectFormPage = () => import('../pages/accounting/AccountingProjectFormPage.vue')
const AccountingProjectListPage = () => import('../pages/accounting/AccountingProjectListPage.vue')
const AccountingVouchersPage = () => import('../pages/AccountingVouchersPage.vue')
const ExpenseCategoryFormPage = () => import('../pages/accounting/ExpenseCategoryFormPage.vue')
const ExpenseCategoryListPage = () => import('../pages/accounting/ExpenseCategoryListPage.vue')
const ExpenseFormPage = () => import('../pages/accounting/ExpenseFormPage.vue')
const ExpenseListPage = () => import('../pages/accounting/ExpenseListPage.vue')
const IncomeSourceFormPage = () => import('../pages/accounting/IncomeSourceFormPage.vue')
const IncomeSourceListPage = () => import('../pages/accounting/IncomeSourceListPage.vue')
const VehicleUsageFormPage = () => import('../pages/accounting/VehicleUsageFormPage.vue')
const VehicleUsageListPage = () => import('../pages/accounting/VehicleUsageListPage.vue')
const CaseDetailPage = () => import('../pages/CaseDetailPage.vue')
const CaseChecklistTemplatesPage = () => import('../pages/CaseChecklistTemplatesPage.vue')
const CasesPage = () => import('../pages/CasesPage.vue')
const CompanyDetailPage = () => import('../pages/CompanyDetailPage.vue')
const CompaniesPage = () => import('../pages/CompaniesPage.vue')
const CustomerDetailPage = () => import('../pages/CustomerDetailPage.vue')
const CustomersPage = () => import('../pages/CustomersPage.vue')
const DashboardPage = () => import('../pages/DashboardPage.vue')
const DocumentsPage = () => import('../pages/DocumentsPage.vue')
const EmployeesPage = () => import('../pages/EmployeesPage.vue')
import LoginPage from '../pages/LoginPage.vue'
const PlaceholderPage = () => import('../pages/PlaceholderPage.vue')
const ReceptionNewPage = () => import('../pages/ReceptionNewPage.vue')
const RemindersPage = () => import('../pages/RemindersPage.vue')
const SeifuNoticePdfTextPage = () => import('../pages/SeifuNoticePdfTextPage.vue')
const SettingsPage = () => import('../pages/SettingsPage.vue')
const TasksPage = () => import('../pages/TasksPage.vue')
const TaxRenewalVouchersPage = () => import('../pages/TaxRenewalVouchersPage.vue')
const TimelinesPage = () => import('../pages/TimelinesPage.vue')
const VisaReturnApplicationsPage = () => import('../pages/VisaReturnApplicationsPage.vue')
const VoucherPlaceholderPage = () => import('../pages/VoucherPlaceholderPage.vue')
const ContractsPage = () => import('../pages/vouchers/ContractsPage.vue')
const RealEstateDetailPage = () => import('../pages/real-estate/RealEstateDetailPage.vue')
const RealEstateImportPage = () => import('../pages/real-estate/RealEstateImportPage.vue')
const RealEstateListPage = () => import('../pages/real-estate/RealEstateListPage.vue')
const EstimatesPage = () => import('../pages/vouchers/EstimatesPage.vue')
const ServiceItemsPage = () => import('../pages/vouchers/ServiceItemsPage.vue')
const DailyPlanPage = () => import('../pages/DailyPlanPage.vue')
const DailyReportsPage = () => import('../pages/DailyReportsPage.vue')
import { landingPath, requiredPermissionFor } from '../utils/access'
import { useAuthStore } from '../stores/auth'
import { handleChunkLoadError } from './chunkError'

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
          // 旧「今日の作業台」は毎日の計画に統合（P3）。古いブックマークは毎日の計画へ
          path: 'workbench',
          redirect: '/daily-plan',
        },
        {
          path: 'daily-plan',
          name: 'daily-plan',
          component: DailyPlanPage,
        },
        {
          path: 'daily-reports',
          name: 'daily-reports',
          component: DailyReportsPage,
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
          path: 'case-checklists',
          name: 'case-checklists',
          component: CaseChecklistTemplatesPage,
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
          component: EstimatesPage,
        },
        {
          path: 'vouchers/contracts',
          name: 'voucher-contracts',
          component: ContractsPage,
        },
        {
          path: 'vouchers/service-items',
          name: 'voucher-service-items',
          component: ServiceItemsPage,
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
          path: 'real-estate',
          name: 'real-estate',
          component: RealEstateListPage,
        },
        {
          path: 'real-estate/import',
          name: 'real-estate-import',
          component: RealEstateImportPage,
        },
        {
          path: 'real-estate/:id(\\d+)',
          name: 'real-estate-detail',
          component: RealEstateDetailPage,
        },
        {
          path: 'settings',
          name: 'settings',
          component: SettingsPage,
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

  // 業務権限の無い画面へは入れない（表示上の制御。API 側でも必ず拒否される）。
  const required = requiredPermissionFor(to.path)
  if (required && !auth.can(required)) {
    const landing = landingPath(auth.can)
    return landing === to.path ? true : { path: landing }
  }

  return true
})

// 分割した画面の読み込みに失敗した場合（再デプロイ後の古いファイル参照・通信断など）に明確に知らせる。
// 認証状態・権限判定は beforeEach のまま変えない。
router.onError((error, to) => handleChunkLoadError(error, to?.fullPath))

export default router
