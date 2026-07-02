import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from '../layouts/AdminLayout.vue'
import CaseDetailPage from '../pages/CaseDetailPage.vue'
import CasesPage from '../pages/CasesPage.vue'
import CompanyDetailPage from '../pages/CompanyDetailPage.vue'
import CompaniesPage from '../pages/CompaniesPage.vue'
import CustomerDetailPage from '../pages/CustomerDetailPage.vue'
import CustomersPage from '../pages/CustomersPage.vue'
import DashboardPage from '../pages/DashboardPage.vue'
import DocumentsPage from '../pages/DocumentsPage.vue'
import PlaceholderPage from '../pages/PlaceholderPage.vue'
import ReceptionNewPage from '../pages/ReceptionNewPage.vue'
import RemindersPage from '../pages/RemindersPage.vue'
import TasksPage from '../pages/TasksPage.vue'
import TimelinesPage from '../pages/TimelinesPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
          component: PlaceholderPage,
          props: { title: '会計管理' },
        },
        {
          path: 'reports',
          name: 'reports',
          component: PlaceholderPage,
          props: { title: '帳票管理' },
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

export default router
