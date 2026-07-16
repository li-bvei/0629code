<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { createCase, deleteCase, listCases, updateCase } from '../api/cases'
import { listCompanies } from '../api/companies'
import { listCustomers } from '../api/customers'
import { listEmployees } from '../api/employees'
import { caseTypeOptions } from '../constants/options'
import type { Case, CasePayload, Company, Customer, Employee } from '../types/api'
import {
  caseRegistrationStatusOptions,
  getCaseDisplayStatus,
  getCaseDisplayStatusTagType,
  getCaseRegistrationStatusLabel,
  getCaseRegistrationStatusTagType,
} from '../utils/caseStatus'
import { formatDate, formatDateTime } from '../utils/date'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const cases = ref<Case[]>([])
const customers = ref<Customer[]>([])
const companies = ref<Company[]>([])
const employees = ref<Employee[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const dialogVisible = ref(false)
const editingCaseId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const filters = ref({
  registration_status: 'active',
})
const caseForm = ref<CasePayload>({
  case_number: '',
  case_type: '',
  customer: null,
  company: null,
  responsible_employee: null,
  accepted_at: null,
  applied_at: null,
  result_notified_at: null,
  completed_at: null,
})

const rules: FormRules<CasePayload> = {
  case_type: [{ required: true, message: '案件種別を選択してください。', trigger: 'change' }],
  customer: [{ required: true, message: '顧客を選択してください。', trigger: 'change' }],
}

const fetchCases = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const params = { page } as { page: number; registration_status?: string }
    if (['active', 'inactive', 'archived'].includes(filters.value.registration_status)) {
      params.registration_status = filters.value.registration_status
    }
    const data = await listCases(params)
    cases.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = 'データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const fetchSelectOptions = async () => {
  try {
    const [customerData, companyData, employeeData] = await Promise.all([
      listCustomers(),
      listCompanies(),
      listEmployees({ is_active: true }),
    ])
    customers.value = customerData.results
    companies.value = companyData.results
    employees.value = employeeData.results
  } catch {
    ElMessage.error('選択肢の取得に失敗しました。')
  }
}

onMounted(() => {
  fetchCases()
  fetchSelectOptions()
})

const resetForm = () => {
  editingCaseId.value = null
  caseForm.value = {
    case_number: '',
    case_type: '',
    customer: null,
    company: null,
    responsible_employee: null,
    accepted_at: null,
    applied_at: null,
    result_notified_at: null,
    completed_at: null,
  }
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (caseItem: Case) => {
  editingCaseId.value = caseItem.id
  caseForm.value = {
    case_number: caseItem.case_number,
    case_type: caseItem.case_type,
    customer: caseItem.customer,
    company: caseItem.company,
    responsible_employee: caseItem.responsible_employee,
    accepted_at: caseItem.accepted_at,
    applied_at: caseItem.applied_at,
    result_notified_at: caseItem.result_notified_at,
    completed_at: caseItem.completed_at,
  }
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

const submitCase = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload: CasePayload = {
      case_type: caseForm.value.case_type,
      customer: caseForm.value.customer,
      company: caseForm.value.company || null,
      responsible_employee: caseForm.value.responsible_employee || null,
      accepted_at: caseForm.value.accepted_at || null,
      applied_at: caseForm.value.applied_at || null,
      result_notified_at: caseForm.value.result_notified_at || null,
      completed_at: caseForm.value.completed_at || null,
    }
    if (editingCaseId.value) {
      await updateCase(editingCaseId.value, payload)
      ElMessage.success('案件を更新しました。')
    } else {
      await createCase(payload)
      ElMessage.success('案件を作成しました。')
    }
    dialogVisible.value = false
    await fetchCases(editingCaseId.value ? currentPage.value : 1)
  } catch {
    ElMessage.error(editingCaseId.value ? '案件の更新に失敗しました。' : '案件の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const confirmDeleteCase = async (caseItem: Case) => {
  try {
    await ElMessageBox.confirm(
      `「${caseItem.case_number}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteCase(caseItem.id)
    ElMessage.success('案件を削除しました。')
    await fetchCases(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('案件の削除に失敗しました。')
    }
  }
}
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>案件一覧</h1>
      <el-button type="primary" @click="openCreateDialog">新規案件</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never">
      <div class="case-list-filter-row">
        <el-select v-model="filters.registration_status" class="case-registration-filter" @change="fetchCases(1)">
          <el-option label="すべて" value="" />
          <el-option
            v-for="option in caseRegistrationStatusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </div>
      <el-table v-loading="loading" :data="cases" stripe>
        <el-table-column label="案件番号" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <button class="entity-link" type="button" :title="row.case_number" @click="router.push(`/cases/${row.id}`)">
              {{ row.case_number }}
            </button>
          </template>
        </el-table-column>
        <el-table-column prop="case_type" label="案件種別" min-width="150" />
        <el-table-column label="現在の進捗" width="140">
          <template #default="{ row }">
            <el-tag :type="getCaseDisplayStatusTagType(row.status)">
              {{ getCaseDisplayStatus(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="登録状態" width="110">
          <template #default="{ row }">
            <el-tag :type="getCaseRegistrationStatusTagType(row.registration_status)" effect="plain">
              {{ getCaseRegistrationStatusLabel(row.registration_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="顧客名" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <button
              v-if="row.customer"
              class="entity-link"
              type="button"
              :title="row.customer_name"
              @click="router.push(`/customers/${row.customer}`)"
            >
              {{ row.customer_name }}
            </button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="company_name" label="会社名" min-width="180">
          <template #default="{ row }">
            <button
              v-if="row.company"
              class="entity-link"
              type="button"
              :title="row.company_name"
              @click="router.push(`/companies/${row.company}`)"
            >
              {{ row.company_name || '-' }}
            </button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="responsible_employee_name" label="担当者" min-width="140">
          <template #default="{ row }">{{ row.responsible_employee_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="タスク進捗" width="120">
          <template #default="{ row }">
            {{ row.task_completed_count || 0 }} / {{ row.task_total_count || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="次のタスク" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.next_task_title || '-' }}</span>
            <span v-if="row.next_task_responsible_employee_name" class="muted-inline">
              （{{ row.next_task_responsible_employee_name }}）
            </span>
          </template>
        </el-table-column>
        <el-table-column label="受理日" width="130">
          <template #default="{ row }">{{ formatDate(row.accepted_at) }}</template>
        </el-table-column>
        <el-table-column label="更新日時" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button text type="primary" class="table-action-trigger">
                操作
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="router.push(`/cases/${row.id}`)">詳細を見る</el-dropdown-item>
                  <el-dropdown-item @click="openEditDialog(row)">編集</el-dropdown-item>
                  <el-dropdown-item divided class="danger-item" @click="confirmDeleteCase(row)">削除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchCases"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingCaseId ? '案件編集' : '新規案件'"
      width="640px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="caseForm" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="案件番号" prop="case_number">
            <el-input :model-value="editingCaseId ? caseForm.case_number : '自動生成'" disabled />
          </el-form-item>
          <el-form-item label="案件種別" prop="case_type">
            <el-select
              v-model="caseForm.case_type"
              filterable
              allow-create
              default-first-option
              placeholder="選択してください"
              class="form-control"
            >
              <el-option
                v-for="caseType in caseTypeOptions"
                :key="caseType"
                :label="caseType"
                :value="caseType"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="顧客" prop="customer">
            <el-select v-model="caseForm.customer" filterable placeholder="選択してください" class="form-control">
              <el-option
                v-for="customer in customers"
                :key="customer.id"
                :label="customer.name"
                :value="customer.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="会社" prop="company">
            <el-select v-model="caseForm.company" clearable filterable placeholder="選択してください" class="form-control">
              <el-option
                v-for="company in companies"
                :key="company.id"
                :label="company.name"
                :value="company.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="担当者" prop="responsible_employee">
            <el-select
              v-model="caseForm.responsible_employee"
              clearable
              filterable
              placeholder="選択してください"
              class="form-control"
            >
              <el-option label="未設定" :value="null" />
              <el-option
                v-for="employee in employees"
                :key="employee.id"
                :label="employee.name"
                :value="employee.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="受任日" prop="accepted_at">
            <el-date-picker
              v-model="caseForm.accepted_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="申請日" prop="applied_at">
            <el-date-picker
              v-model="caseForm.applied_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="結果通知日" prop="result_notified_at">
            <el-date-picker
              v-model="caseForm.result_notified_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="完了日" prop="completed_at">
            <el-date-picker
              v-model="caseForm.completed_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCase">
          {{ editingCaseId ? '保存' : '作成' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.entity-link {
  display: inline-flex;
  max-width: 100%;
  padding: 2px 0;
  border: 0;
  background: transparent;
  color: var(--el-color-primary);
  cursor: pointer;
  font: inherit;
  text-align: left;
  text-decoration: none;
}

.entity-link:hover {
  color: var(--el-color-primary-light-3);
  text-decoration: underline;
}

.case-list-filter-row {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.case-registration-filter {
  width: 160px;
}
</style>
