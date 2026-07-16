<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { createCase, listCaseApplicationCategories, listCases, listCaseTypeMasters } from '../api/cases'
import { getCompany } from '../api/companies'
import { listCustomers } from '../api/customers'
import { listEmployees } from '../api/employees'
import {
  createCompanyStaff,
  deleteCompanyStaff,
  listCompanyStaff,
  updateCompanyStaff,
} from '../api/companyStaff'
import { residenceStatusOptions } from '../constants/options'
import type { Case, CaseApplicationCategory, CasePayload, CaseTypeMaster, Company, CompanyStaff, CompanyStaffPayload, Customer, Employee } from '../types/api'
import { formatDate, formatDateTime } from '../utils/date'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const company = ref<Company | null>(null)
const staffMembers = ref<CompanyStaff[]>([])
const relatedCases = ref<Case[]>([])
const staffSubmitting = ref(false)
const staffDialogVisible = ref(false)
const editingStaffId = ref<number | null>(null)
const staffFormRef = ref<FormInstance>()
const caseDialogVisible = ref(false)
const caseSubmitting = ref(false)
const caseFormRef = ref<FormInstance>()
const customers = ref<Customer[]>([])
const employees = ref<Employee[]>([])
const caseTypes = ref<CaseTypeMaster[]>([])
const applicationCategories = ref<CaseApplicationCategory[]>([])
const caseForm = ref<CasePayload>({
  case_type_master: null,
  application_category: null,
  customer: null,
  company: null,
  responsible_employee: null,
})

const companyId = computed(() => Number(route.params.id))

const genderOptions = ['男性', '女性', 'その他']

const staffForm = ref<CompanyStaffPayload>({
  company: 0,
  name: '',
  name_kana: '',
  position: '',
  birth_date: null,
  gender: '',
  nationality: '',
  residence_status: '',
  residence_card_no: '',
  residence_expiry: null,
  passport_no: '',
  passport_expiry: null,
  phone: '',
  email: '',
  postal_code: '',
  address: '',
  my_number: '',
  employment_start_date: null,
  employment_end_date: null,
  note: '',
})

const staffRules: FormRules<CompanyStaffPayload> = {
  name: [{ required: true, message: '氏名を入力してください。', trigger: 'blur' }],
}

const caseRules: FormRules<CasePayload> = {
  case_type_master: [{ required: true, message: '案件種別を選択してください。', trigger: 'change' }],
  application_category: [{ required: true, message: '申請区分を選択してください。', trigger: 'change' }],
  customer: [{ required: true, message: '顧客を選択してください。', trigger: 'change' }],
}

const displayValue = (value?: string | null) => value || '-'
const formatFiscalMonth = (value?: string | null) => (value ? `${value}月` : '-')
const getRepresentativeName = (companyData: Company) => (
  companyData.representative_customer_name || companyData.representative_name
)

const fetchCompanyDetail = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [companyData, staffData, caseData] = await Promise.all([
      getCompany(companyId.value),
      listCompanyStaff({ company: companyId.value }),
      listCases({ company: companyId.value }),
    ])
    company.value = companyData
    staffMembers.value = staffData.results
    relatedCases.value = caseData.results
  } catch {
    errorMessage.value = '会社詳細の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const fetchStaffMembers = async () => {
  const data = await listCompanyStaff({ company: companyId.value })
  staffMembers.value = data.results
}

const fetchCaseOptions = async () => {
  const [customerData, employeeData, caseTypeData, applicationCategoryData] = await Promise.all([
    listCustomers(),
    listEmployees({ is_active: true }),
    listCaseTypeMasters({ is_active: true, ordering: 'sort_order' }),
    listCaseApplicationCategories({ is_active: true, ordering: 'sort_order' }),
  ])
  customers.value = customerData.results
  employees.value = employeeData.results
  caseTypes.value = caseTypeData.results
  applicationCategories.value = applicationCategoryData.results
}

const openCreateCaseDialog = async () => {
  if (!customers.value.length || !caseTypes.value.length || !applicationCategories.value.length) {
    await fetchCaseOptions()
  }
  caseForm.value = {
    case_type_master: null,
    application_category: null,
    customer: null,
    company: companyId.value,
    responsible_employee: null,
  }
  caseFormRef.value?.clearValidate()
  caseDialogVisible.value = true
}

const submitCase = async () => {
  if (!caseFormRef.value) return
  const valid = await caseFormRef.value.validate().catch(() => false)
  if (!valid) return
  caseSubmitting.value = true
  try {
    await createCase({
      ...caseForm.value,
      company: companyId.value,
      responsible_employee: caseForm.value.responsible_employee || null,
    })
    ElMessage.success('案件を追加しました。')
    caseDialogVisible.value = false
    await fetchCompanyDetail()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '案件の追加に失敗しました。')
  } finally {
    caseSubmitting.value = false
  }
}

const resetStaffForm = () => {
  editingStaffId.value = null
  staffForm.value = {
    company: companyId.value,
    name: '',
    name_kana: '',
    position: '',
    birth_date: null,
    gender: '',
    nationality: '',
    residence_status: '',
    residence_card_no: '',
    residence_expiry: null,
    passport_no: '',
    passport_expiry: null,
    phone: '',
    email: '',
    postal_code: '',
    address: '',
    my_number: '',
    employment_start_date: null,
    employment_end_date: null,
    note: '',
  }
  staffFormRef.value?.clearValidate()
}

const openCreateStaffDialog = () => {
  resetStaffForm()
  staffDialogVisible.value = true
}

const openEditStaffDialog = (staff: CompanyStaff) => {
  editingStaffId.value = staff.id
  staffForm.value = {
    company: companyId.value,
    name: staff.name,
    name_kana: staff.name_kana,
    position: staff.position,
    birth_date: staff.birth_date,
    gender: staff.gender,
    nationality: staff.nationality,
    residence_status: staff.residence_status,
    residence_card_no: staff.residence_card_no,
    residence_expiry: staff.residence_expiry,
    passport_no: staff.passport_no,
    passport_expiry: staff.passport_expiry,
    phone: staff.phone,
    email: staff.email,
    postal_code: staff.postal_code,
    address: staff.address,
    my_number: staff.my_number,
    employment_start_date: staff.employment_start_date,
    employment_end_date: staff.employment_end_date,
    note: staff.note,
  }
  staffFormRef.value?.clearValidate()
  staffDialogVisible.value = true
}

const submitStaff = async () => {
  if (!staffFormRef.value) return

  const valid = await staffFormRef.value.validate().catch(() => false)
  if (!valid) return

  staffSubmitting.value = true
  try {
    const payload = {
      ...staffForm.value,
      company: companyId.value,
    }
    if (editingStaffId.value) {
      await updateCompanyStaff(editingStaffId.value, payload)
      ElMessage.success('従業員情報を更新しました。')
    } else {
      await createCompanyStaff(payload)
      ElMessage.success('従業員を追加しました。')
    }
    staffDialogVisible.value = false
    await fetchStaffMembers()
  } catch {
    ElMessage.error(editingStaffId.value ? '従業員情報の更新に失敗しました。' : '従業員の追加に失敗しました。')
  } finally {
    staffSubmitting.value = false
  }
}

const confirmDeleteStaff = async (staff: CompanyStaff) => {
  try {
    await ElMessageBox.confirm(
      `「${staff.name}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteCompanyStaff(staff.id)
    ElMessage.success('従業員を削除しました。')
    await fetchStaffMembers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('従業員の削除に失敗しました。')
    }
  }
}

onMounted(() => {
  fetchCompanyDetail()
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>会社詳細</h1>
      <el-button @click="router.push('/companies')">一覧へ戻る</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <div v-loading="loading" class="detail-grid">
      <el-card shadow="never">
        <template #header>会社基本情報</template>
        <el-descriptions v-if="company" :column="2" border>
          <el-descriptions-item label="会社名フリガナ" :span="2">{{ displayValue(company.name_kana) }}</el-descriptions-item>
          <el-descriptions-item label="会社名" :span="2">{{ displayValue(company.name) }}</el-descriptions-item>
          <el-descriptions-item label="代表者フリガナ" :span="2">{{ displayValue(company.representative_name_kana) }}</el-descriptions-item>
          <el-descriptions-item label="代表者氏名" :span="2">
            <router-link
              v-if="company.representative_customer"
              class="text-link"
              :to="`/customers/${company.representative_customer}`"
            >
              {{ displayValue(getRepresentativeName(company)) }}
            </router-link>
            <span v-else>{{ displayValue(getRepresentativeName(company)) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="法人番号">{{ displayValue(company.corporate_number) }}</el-descriptions-item>
          <el-descriptions-item label="会社法人等番号">{{ displayValue(company.corporate_registration_number) }}</el-descriptions-item>
          <el-descriptions-item label="メール">{{ displayValue(company.email) }}</el-descriptions-item>
          <el-descriptions-item label="電話番号">{{ displayValue(company.phone) }}</el-descriptions-item>
          <el-descriptions-item label="郵便番号" :span="2">{{ displayValue(company.postal_code) }}</el-descriptions-item>
          <el-descriptions-item label="住所" :span="2">{{ displayValue(company.address) }}</el-descriptions-item>
          <el-descriptions-item label="決算月">{{ formatFiscalMonth(company.fiscal_month) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>銀行情報</template>
        <el-descriptions v-if="company" :column="2" border>
          <el-descriptions-item label="銀行名">{{ displayValue(company.bank_name) }}</el-descriptions-item>
          <el-descriptions-item label="支店名">{{ displayValue(company.bank_branch) }}</el-descriptions-item>
          <el-descriptions-item label="預金種別">{{ displayValue(company.bank_account_type) }}</el-descriptions-item>
          <el-descriptions-item label="口座番号">{{ displayValue(company.bank_account_number) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>従業員情報</span>
            <el-button type="primary" @click="openCreateStaffDialog">従業員追加</el-button>
          </div>
        </template>
        <div v-if="staffMembers.length" class="staff-member-list">
          <div v-for="staff in staffMembers" :key="staff.id" class="staff-member-block">
            <div class="staff-member-header">
              <strong>{{ displayValue(staff.name) }}</strong>
              <el-dropdown trigger="click">
                <el-button text type="primary" class="table-action-trigger">
                  操作
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="openEditStaffDialog(staff)">編集</el-dropdown-item>
                    <el-dropdown-item divided class="danger-item" @click="confirmDeleteStaff(staff)">削除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="フリガナ" :span="2">{{ displayValue(staff.name_kana) }}</el-descriptions-item>
              <el-descriptions-item label="氏名" :span="2">{{ displayValue(staff.name) }}</el-descriptions-item>
              <el-descriptions-item label="役職">{{ displayValue(staff.position) }}</el-descriptions-item>
              <el-descriptions-item label="生年月日">{{ formatDate(staff.birth_date) }}</el-descriptions-item>
              <el-descriptions-item label="性別">{{ displayValue(staff.gender) }}</el-descriptions-item>
              <el-descriptions-item label="国籍">{{ displayValue(staff.nationality) }}</el-descriptions-item>
              <el-descriptions-item label="電話番号">{{ displayValue(staff.phone) }}</el-descriptions-item>
              <el-descriptions-item label="メール">{{ displayValue(staff.email) }}</el-descriptions-item>
              <el-descriptions-item label="郵便番号" :span="2">{{ displayValue(staff.postal_code) }}</el-descriptions-item>
              <el-descriptions-item label="住所" :span="2">{{ displayValue(staff.address) }}</el-descriptions-item>
              <el-descriptions-item label="在留資格" :span="2">{{ displayValue(staff.residence_status) }}</el-descriptions-item>
              <el-descriptions-item label="在留カード番号">{{ displayValue(staff.residence_card_no) }}</el-descriptions-item>
              <el-descriptions-item label="在留期限">{{ formatDate(staff.residence_expiry) }}</el-descriptions-item>
              <el-descriptions-item label="パスポート番号">{{ displayValue(staff.passport_no) }}</el-descriptions-item>
              <el-descriptions-item label="パスポート期限">{{ formatDate(staff.passport_expiry) }}</el-descriptions-item>
              <el-descriptions-item label="入社日">{{ formatDate(staff.employment_start_date) }}</el-descriptions-item>
              <el-descriptions-item label="退社日">{{ formatDate(staff.employment_end_date) }}</el-descriptions-item>
              <el-descriptions-item label="マイナンバー">{{ displayValue(staff.my_number) }}</el-descriptions-item>
              <el-descriptions-item label="備考" :span="2">{{ displayValue(staff.note) }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
        <p v-if="!staffMembers.length" class="empty-text">従業員情報はありません</p>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>関連案件</span>
            <el-button type="primary" @click="openCreateCaseDialog">案件を追加</el-button>
          </div>
        </template>
        <el-table :data="relatedCases" stripe>
          <el-table-column label="案件番号" min-width="150">
            <template #default="{ row }">
              <router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link>
            </template>
          </el-table-column>
          <el-table-column prop="case_type" label="案件種別" min-width="150" />
          <el-table-column prop="status" label="ステータス" width="130" />
          <el-table-column prop="customer_name" label="顧客名" min-width="150" />
          <el-table-column prop="responsible_employee_name" label="担当者" min-width="140">
            <template #default="{ row }">{{ displayValue(row.responsible_employee_name) }}</template>
          </el-table-column>
          <el-table-column label="受任日" width="130">
            <template #default="{ row }">{{ formatDate(row.accepted_at) }}</template>
          </el-table-column>
          <el-table-column label="更新日時" min-width="160">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
        </el-table>
        <p v-if="!relatedCases.length" class="empty-text">該当データなし</p>
      </el-card>
    </div>

    <el-dialog
      v-model="staffDialogVisible"
      :title="editingStaffId ? '従業員編集' : '従業員追加'"
      width="720px"
      @closed="resetStaffForm"
    >
      <el-form ref="staffFormRef" :model="staffForm" :rules="staffRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="フリガナ" prop="name_kana" class="form-grid-start">
            <el-input v-model="staffForm.name_kana" />
          </el-form-item>
          <el-form-item label="氏名" prop="name" class="form-grid-start">
            <el-input v-model="staffForm.name" />
          </el-form-item>
          <el-form-item label="役職" prop="position">
            <el-input v-model="staffForm.position" />
          </el-form-item>
          <el-form-item label="生年月日" prop="birth_date">
            <el-date-picker v-model="staffForm.birth_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="性別" prop="gender">
            <el-select v-model="staffForm.gender" clearable placeholder="選択してください" class="form-control">
              <el-option v-for="gender in genderOptions" :key="gender" :label="gender" :value="gender" />
            </el-select>
          </el-form-item>
          <el-form-item label="国籍" prop="nationality">
            <el-input v-model="staffForm.nationality" />
          </el-form-item>
          <el-form-item label="在留資格" prop="residence_status">
            <el-select
              v-model="staffForm.residence_status"
              clearable
              filterable
              allow-create
              default-first-option
              placeholder="選択してください"
              class="form-control"
            >
              <el-option v-for="status in residenceStatusOptions" :key="status" :label="status" :value="status" />
            </el-select>
          </el-form-item>
          <el-form-item label="在留カード番号" prop="residence_card_no">
            <el-input v-model="staffForm.residence_card_no" />
          </el-form-item>
          <el-form-item label="在留期限" prop="residence_expiry">
            <el-date-picker v-model="staffForm.residence_expiry" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="パスポート番号" prop="passport_no">
            <el-input v-model="staffForm.passport_no" />
          </el-form-item>
          <el-form-item label="パスポート期限" prop="passport_expiry">
            <el-date-picker v-model="staffForm.passport_expiry" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="電話番号" prop="phone">
            <el-input v-model="staffForm.phone" />
          </el-form-item>
          <el-form-item label="メール" prop="email">
            <el-input v-model="staffForm.email" />
          </el-form-item>
          <el-form-item label="郵便番号" prop="postal_code" class="form-grid-start">
            <el-input v-model="staffForm.postal_code" />
          </el-form-item>
          <el-form-item label="住所" prop="address" class="form-grid-full">
            <el-input v-model="staffForm.address" />
          </el-form-item>
          <el-form-item label="マイナンバー" prop="my_number">
            <el-input v-model="staffForm.my_number" />
          </el-form-item>
          <el-form-item label="入社日" prop="employment_start_date">
            <el-date-picker v-model="staffForm.employment_start_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="退社日" prop="employment_end_date">
            <el-date-picker v-model="staffForm.employment_end_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" />
          </el-form-item>
        </div>
        <el-form-item label="備考" prop="note">
          <el-input v-model="staffForm.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="staffDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="staffSubmitting" @click="submitStaff">
          {{ editingStaffId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="caseDialogVisible" title="案件追加" width="560px">
      <el-form ref="caseFormRef" :model="caseForm" :rules="caseRules" label-position="top">
        <el-form-item label="案件種別" prop="case_type_master">
          <el-select v-model="caseForm.case_type_master" filterable placeholder="選択してください" class="form-control">
            <el-option v-for="caseType in caseTypes" :key="caseType.id" :label="caseType.name" :value="caseType.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="申請区分" prop="application_category">
          <el-select v-model="caseForm.application_category" filterable placeholder="選択してください" class="form-control">
            <el-option v-for="category in applicationCategories" :key="category.id" :label="category.name" :value="category.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="顧客" prop="customer">
          <el-select v-model="caseForm.customer" filterable placeholder="選択してください" class="form-control">
            <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="担当者">
          <el-select v-model="caseForm.responsible_employee" clearable filterable placeholder="未指定" class="form-control">
            <el-option v-for="employee in employees" :key="employee.id" :label="employee.name" :value="employee.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="caseDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="caseSubmitting" @click="submitCase">追加</el-button>
      </template>
    </el-dialog>
  </section>
</template>
