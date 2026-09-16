<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { createCase, listCaseApplicationCategories, listCases, listCaseTypeMasters } from '../api/cases'
import { getCompany, updateCompany } from '../api/companies'
import { listCustomers, listResidenceStatusMasters } from '../api/customers'
import { listEmployees } from '../api/employees'
import {
  createCompanyStaff,
  deleteCompanyStaff,
  listCompanyStaff,
  updateCompanyStaff,
} from '../api/companyStaff'
import RemoteCustomerSelect from '../components/RemoteCustomerSelect.vue'
import { bankAccountTypeOptions, fiscalMonthOptions } from '../constants/options'
import type { Case, CaseApplicationCategory, CasePayload, CaseTypeMaster, Company, CompanyStaff, CompanyStaffPayload, CreateCompanyPayload, CreateCustomerPayload, Customer, Employee, ResidenceStatusMaster } from '../types/api'
import { getCaseDisplayStatus, getCaseDisplayStatusTagType } from '../utils/caseStatus'
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
const residenceStatusOptions = ref<ResidenceStatusMaster[]>([])
const activeSection = ref<'overview' | 'staff' | 'cases'>('overview')
const companyDialogVisible = ref(false)
const companySubmitting = ref(false)
const companyFormRef = ref<FormInstance>()
const companyForm = ref<CreateCompanyPayload>({ name: '' })
const caseForm = ref<CasePayload>({
  case_type_master: null,
  application_category: null,
  customer: null,
  company: null,
  responsible_employee: null,
})

const companyId = computed(() => Number(route.params.id))

const genderOptions = [
  { label: '男性', value: 'male' },
  { label: '女性', value: 'female' },
  { label: 'その他', value: 'other' },
]

const sortedStaffMembers = computed(() => (
  [...staffMembers.value].sort((left, right) => {
    const leftRetired = left.employment_end_date ? 1 : 0
    const rightRetired = right.employment_end_date ? 1 : 0
    if (leftRetired !== rightRetired) return leftRetired - rightRetired
    return left.name.localeCompare(right.name, 'ja')
  })
))

const activeStaffMembers = computed(() => staffMembers.value.filter((staff) => !staff.employment_end_date))
const activeCases = computed(() => relatedCases.value.filter((caseItem) => (
  caseItem.registration_status === 'active'
  && !['rejected', 'withdrawn', 'completed'].includes(caseItem.status)
)))
const historicalCases = computed(() => relatedCases.value.filter((caseItem) => (
  !activeCases.value.some((activeCase) => activeCase.id === caseItem.id)
)))
const primaryCase = computed(() => activeCases.value[0] || relatedCases.value[0] || null)

interface StaffEditForm {
  company: number
  customer: number | null
  position: string
  employment_start_date: string | null
  employment_end_date: string | null
  note: string
  name: string
  name_kana: string
  birth_date: string | null
  gender: string
  nationality: string
  residence_status: string
  residence_card_no: string
  residence_expiry: string | null
  passport_no: string
  passport_expiry: string | null
  phone: string
  email: string
  postal_code: string
  address: string
  my_number: string
}

const staffForm = ref<StaffEditForm>({
  company: 0,
  customer: null,
  position: '',
  employment_start_date: null,
  employment_end_date: null,
  note: '',
  name: '',
  name_kana: '',
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
})

const staffRules: FormRules<StaffEditForm> = {
  name: [
    {
      validator: (_rule, value, callback) => {
        if (!staffForm.value.customer && !value) {
          callback(new Error('既存の顧客を選択するか、氏名を入力してください。'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
  birth_date: [
    {
      validator: (_rule, value, callback) => {
        if (!staffForm.value.customer && !value) {
          callback(new Error('新規に顧客として登録する場合は生年月日を入力してください。'))
          return
        }
        callback()
      },
      trigger: 'change',
    },
  ],
}

const caseRules: FormRules<CasePayload> = {
  case_type_master: [{ required: true, message: '案件種別を選択してください。', trigger: 'change' }],
  application_category: [{ required: true, message: '申請区分を選択してください。', trigger: 'change' }],
  customer: [{ required: true, message: '顧客を選択してください。', trigger: 'change' }],
}

const companyRules: FormRules<CreateCompanyPayload> = {
  name: [{ required: true, message: '会社名を入力してください。', trigger: 'blur' }],
}

const displayValue = (value?: string | null) => value || '-'
const formatFiscalMonth = (value?: string | null) => (value ? `${value}月` : '-')
const formatGender = (value?: string | null) => ({ male: '男性', female: '女性', other: 'その他' }[value || ''] || displayValue(value))
const getRepresentativeName = (companyData: Company) => (
  companyData.representative_customer_name || companyData.representative_name
)

const getCorporateRegistrationNumber = (corporateNumber?: string) => (
  corporateNumber && /^\d{13}$/.test(corporateNumber) ? corporateNumber.slice(1) : '自動生成'
)

const openCompanyEditDialog = () => {
  if (!company.value) return
  companyForm.value = {
    name: company.value.name,
    name_kana: company.value.name_kana,
    representative_customer: company.value.representative_customer,
    representative_name: company.value.representative_name,
    representative_name_kana: company.value.representative_name_kana,
    representative_postal_code: company.value.representative_postal_code,
    representative_address: company.value.representative_address,
    corporate_number: company.value.corporate_number,
    email: company.value.email,
    phone: company.value.phone,
    postal_code: company.value.postal_code,
    address: company.value.address,
    fiscal_month: company.value.fiscal_month,
    establishment_symbol: company.value.establishment_symbol,
    establishment_number: company.value.establishment_number,
    bank_name: company.value.bank_name,
    bank_branch: company.value.bank_branch,
    bank_account_type: company.value.bank_account_type,
    bank_account_number: company.value.bank_account_number,
  }
  companyFormRef.value?.clearValidate()
  companyDialogVisible.value = true
}

const submitCompany = async () => {
  if (!companyFormRef.value) return
  const valid = await companyFormRef.value.validate().catch(() => false)
  if (!valid) return
  companySubmitting.value = true
  try {
    await updateCompany(companyId.value, companyForm.value)
    ElMessage.success('会社情報を更新しました。')
    companyDialogVisible.value = false
    await fetchCompanyDetail()
  } catch {
    ElMessage.error('会社情報の更新に失敗しました。')
  } finally {
    companySubmitting.value = false
  }
}

const fetchCompanyDetail = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [companyData, staffData, caseData] = await Promise.all([
      getCompany(companyId.value),
      listCompanyStaff({ company: companyId.value }),
      listCases({ company: companyId.value, page_size: 200, ordering: '-updated_at' }),
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
    customer: null,
    position: '',
    employment_start_date: null,
    employment_end_date: null,
    note: '',
    name: '',
    name_kana: '',
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
  }
  staffFormRef.value?.clearValidate()
}

const openCreateStaffDialog = async () => {
  if (!customers.value.length) {
    await fetchCaseOptions()
  }
  resetStaffForm()
  staffDialogVisible.value = true
}

const openEditStaffDialog = (staff: CompanyStaff) => {
  editingStaffId.value = staff.id
  staffForm.value = {
    company: companyId.value,
    customer: staff.customer,
    position: staff.position,
    employment_start_date: staff.employment_start_date,
    employment_end_date: staff.employment_end_date,
    note: staff.note,
    name: '',
    name_kana: '',
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
    const payload: CompanyStaffPayload = {
      company: companyId.value,
      position: staffForm.value.position,
      employment_start_date: staffForm.value.employment_start_date,
      employment_end_date: staffForm.value.employment_end_date,
      note: staffForm.value.note,
    }
    if (staffForm.value.customer) {
      payload.customer = staffForm.value.customer
    } else {
      const newCustomer: CreateCustomerPayload = {
        name: staffForm.value.name,
        name_kana: staffForm.value.name_kana,
        birth_date: staffForm.value.birth_date || '',
        gender: staffForm.value.gender,
        nationality: staffForm.value.nationality,
        residence_status: staffForm.value.residence_status,
        residence_card_no: staffForm.value.residence_card_no,
        residence_expiry: staffForm.value.residence_expiry,
        passport_no: staffForm.value.passport_no,
        passport_expiry: staffForm.value.passport_expiry,
        phone: staffForm.value.phone,
        email: staffForm.value.email,
        postal_code: staffForm.value.postal_code,
        address: staffForm.value.address,
        my_number: staffForm.value.my_number,
      }
      payload.new_customer = newCustomer
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
  } catch (error: any) {
    const detail = error?.response?.data?.customer?.[0]
    ElMessage.error(detail || (editingStaffId.value ? '従業員情報の更新に失敗しました。' : '従業員の追加に失敗しました。'))
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

const fetchResidenceStatusOptions = async () => {
  const data = await listResidenceStatusMasters({ is_active: true, ordering: 'sort_order' })
  residenceStatusOptions.value = data.results
}

onMounted(() => {
  fetchCompanyDetail()
  fetchResidenceStatusOptions()
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row"><h1>会社詳細</h1><el-button @click="router.push('/companies')">一覧へ戻る</el-button></div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <div v-loading="loading" class="company-record-page">
      <el-card v-if="company" shadow="never" class="record-profile-header">
        <div class="record-header-main">
          <div class="record-avatar">{{ company.name.slice(0, 1) }}</div>
          <div class="record-identity"><p>{{ displayValue(company.name_kana) }}</p><h2>{{ company.name }}</h2><div class="record-tags"><el-tag effect="plain">会社 ID {{ company.id }}</el-tag><el-tag v-if="company.fiscal_month" type="info" effect="plain">決算 {{ formatFiscalMonth(company.fiscal_month) }}</el-tag></div></div>
          <div class="record-actions"><el-button @click="openCompanyEditDialog">会社情報を編集</el-button><el-button @click="openCreateStaffDialog">従業員追加</el-button><el-button type="primary" @click="openCreateCaseDialog">案件を追加</el-button></div>
        </div>
        <div class="record-contact-row"><span>代表者 {{ displayValue(getRepresentativeName(company)) }}</span><span>電話 {{ displayValue(company.phone) }}</span><span>メール {{ displayValue(company.email) }}</span><span>最終更新 {{ formatDateTime(company.updated_at) }}</span></div>
      </el-card>

      <div v-if="company" class="record-summary-grid">
        <button type="button" class="record-summary-tile" @click="activeSection = 'cases'"><strong>{{ activeCases.length }}</strong><span>進行中案件</span></button>
        <button type="button" class="record-summary-tile" @click="activeSection = 'cases'"><strong>{{ historicalCases.length }}</strong><span>履歴案件</span></button>
        <button type="button" class="record-summary-tile" @click="activeSection = 'staff'"><strong>{{ activeStaffMembers.length }}</strong><span>在職者</span></button>
        <button type="button" class="record-summary-tile" @click="activeSection = 'staff'"><strong>{{ staffMembers.length }}</strong><span>従業員履歴</span></button>
      </div>

      <div v-if="company" class="record-workspace">
        <el-card shadow="never" class="record-main-card">
          <el-tabs v-model="activeSection">
            <el-tab-pane label="概要" name="overview">
              <div class="company-overview-grid">
                <section class="record-info-panel"><h3>会社基本情報</h3><dl class="record-field-list"><div><dt>会社名</dt><dd>{{ company.name }}</dd></div><div><dt>フリガナ</dt><dd>{{ displayValue(company.name_kana) }}</dd></div><div><dt>法人番号</dt><dd>{{ displayValue(company.corporate_number) }}</dd></div><div><dt>会社法人等番号</dt><dd>{{ displayValue(company.corporate_registration_number) }}</dd></div><div><dt>決算月</dt><dd>{{ formatFiscalMonth(company.fiscal_month) }}</dd></div></dl></section>
                <section class="record-info-panel"><h3>連絡先・所在地</h3><dl class="record-field-list"><div><dt>電話番号</dt><dd>{{ displayValue(company.phone) }}</dd></div><div><dt>メール</dt><dd>{{ displayValue(company.email) }}</dd></div><div><dt>郵便番号</dt><dd>{{ displayValue(company.postal_code) }}</dd></div><div><dt>住所</dt><dd>{{ displayValue(company.address) }}</dd></div></dl></section>
                <section class="record-info-panel"><h3>代表者</h3><dl class="record-field-list"><div><dt>氏名</dt><dd><router-link v-if="company.representative_customer" class="text-link" :to="`/customers/${company.representative_customer}`">{{ displayValue(getRepresentativeName(company)) }}</router-link><span v-else>{{ displayValue(getRepresentativeName(company)) }}</span></dd></div><div><dt>フリガナ</dt><dd>{{ displayValue(company.representative_name_kana) }}</dd></div><div><dt>郵便番号</dt><dd>{{ displayValue(company.representative_postal_code) }}</dd></div><div><dt>住所</dt><dd>{{ displayValue(company.representative_address) }}</dd></div></dl></section>
                <section class="record-info-panel"><h3>社会保険・銀行</h3><dl class="record-field-list"><div><dt>事業所整理記号</dt><dd>{{ displayValue(company.establishment_symbol) }}</dd></div><div><dt>事業所番号</dt><dd>{{ displayValue(company.establishment_number) }}</dd></div><div><dt>銀行・支店</dt><dd>{{ [company.bank_name, company.bank_branch].filter(Boolean).join(' / ') || '-' }}</dd></div><div><dt>預金種別</dt><dd>{{ displayValue(company.bank_account_type) }}</dd></div><div><dt>口座番号</dt><dd>{{ displayValue(company.bank_account_number) }}</dd></div></dl></section>
              </div>
            </el-tab-pane>

            <el-tab-pane :label="`従業員 ${staffMembers.length}`" name="staff">
              <div class="record-section-heading"><div><h3>従業員情報</h3><p>人物情報を確認し、顧客主档へ移動できます。</p></div><el-button type="primary" @click="openCreateStaffDialog">従業員追加</el-button></div>
              <div v-if="staffMembers.length" class="staff-member-list">
                <article v-for="staff in sortedStaffMembers" :key="staff.id" class="staff-member-block" :class="{ 'is-retired': staff.employment_end_date }">
                  <div class="staff-member-header"><div class="staff-member-title"><strong>{{ displayValue(staff.name) }}</strong><el-tag v-if="staff.employment_end_date" size="small" type="info">退社済み</el-tag><el-tag v-else size="small" type="success">在職中</el-tag><span>{{ displayValue(staff.position) }}</span></div><el-dropdown trigger="click"><el-button text type="primary">操作 <el-icon><ArrowDown /></el-icon></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-if="staff.customer" @click="router.push(`/customers/${staff.customer}`)">顧客ページへ</el-dropdown-item><el-dropdown-item @click="openEditStaffDialog(staff)">編集</el-dropdown-item><el-dropdown-item divided class="danger-item" @click="confirmDeleteStaff(staff)">削除</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div>
                  <div class="staff-info-grid"><dl class="record-field-list"><div><dt>フリガナ</dt><dd>{{ displayValue(staff.name_kana) }}</dd></div><div><dt>生年月日</dt><dd>{{ formatDate(staff.birth_date) }}</dd></div><div><dt>性別・国籍</dt><dd>{{ formatGender(staff.gender) }} / {{ displayValue(staff.nationality) }}</dd></div><div><dt>連絡先</dt><dd>{{ [staff.phone, staff.email].filter(Boolean).join(' / ') || '-' }}</dd></div><div><dt>住所</dt><dd>〒{{ displayValue(staff.postal_code) }} {{ displayValue(staff.address) }}</dd></div></dl><dl class="record-field-list"><div><dt>在留資格</dt><dd>{{ displayValue(staff.residence_status) }}</dd></div><div><dt>在留カード番号</dt><dd>{{ displayValue(staff.residence_card_no) }}</dd></div><div><dt>在留期限</dt><dd>{{ formatDate(staff.residence_expiry) }}</dd></div><div><dt>パスポート番号</dt><dd>{{ displayValue(staff.passport_no) }}</dd></div><div><dt>パスポート期限</dt><dd>{{ formatDate(staff.passport_expiry) }}</dd></div><div><dt>在籍期間</dt><dd>{{ formatDate(staff.employment_start_date) }} ～ {{ formatDate(staff.employment_end_date) }}</dd></div></dl></div>
                </article>
              </div><p v-else class="empty-text">従業員情報はありません。</p>
            </el-tab-pane>

            <el-tab-pane :label="`案件 ${relatedCases.length}`" name="cases">
              <div class="record-section-heading"><div><h3>進行中案件</h3><p>現在対応が必要な案件を優先して表示します。</p></div><el-button type="primary" @click="openCreateCaseDialog">案件を追加</el-button></div>
              <el-table :data="activeCases" stripe><el-table-column label="案件番号" min-width="190"><template #default="{ row }"><router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link></template></el-table-column><el-table-column label="案件種別" min-width="150"><template #default="{ row }">{{ row.case_type_master_name || row.case_type }}</template></el-table-column><el-table-column label="進捗" width="150"><template #default="{ row }"><el-tag :type="getCaseDisplayStatusTagType(row.status)">{{ getCaseDisplayStatus(row.status) }}</el-tag></template></el-table-column><el-table-column prop="customer_name" label="顧客名" min-width="140" /><el-table-column prop="responsible_employee_name" label="担当者" min-width="120" /></el-table>
              <p v-if="!activeCases.length" class="empty-text">進行中の案件はありません。</p>
              <el-collapse v-if="historicalCases.length" class="company-history"><el-collapse-item :title="`履歴案件 ${historicalCases.length}件`" name="history"><el-table :data="historicalCases" stripe><el-table-column label="案件番号" min-width="190"><template #default="{ row }"><router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link></template></el-table-column><el-table-column label="案件種別" min-width="150"><template #default="{ row }">{{ row.case_type_master_name || row.case_type }}</template></el-table-column><el-table-column label="進捗" width="150"><template #default="{ row }"><el-tag :type="getCaseDisplayStatusTagType(row.status)" effect="plain">{{ getCaseDisplayStatus(row.status) }}</el-tag></template></el-table-column><el-table-column label="更新日時" min-width="160"><template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template></el-table-column></el-table></el-collapse-item></el-collapse>
            </el-tab-pane>
          </el-tabs>
        </el-card>

        <aside class="record-sidebar">
          <el-card shadow="never"><template #header>現在の対応</template><template v-if="primaryCase"><router-link class="text-link primary-case-link" :to="`/cases/${primaryCase.id}`">{{ primaryCase.case_number }}</router-link><el-tag :type="getCaseDisplayStatusTagType(primaryCase.status)">{{ getCaseDisplayStatus(primaryCase.status) }}</el-tag><dl class="record-field-list sidebar-list"><div><dt>顧客</dt><dd>{{ primaryCase.customer_name }}</dd></div><div><dt>担当者</dt><dd>{{ displayValue(primaryCase.responsible_employee_name) }}</dd></div><div><dt>次の対応</dt><dd>{{ displayValue(primaryCase.next_action) }}</dd></div><div><dt>期限</dt><dd>{{ formatDate(primaryCase.next_action_due_at) }}</dd></div></dl></template><p v-else class="empty-text">関連案件はありません。</p></el-card>
          <el-card shadow="never"><template #header>データ状態</template><ul class="company-data-status"><li><span>代表者</span><strong>{{ getRepresentativeName(company) ? '登録済み' : '未登録' }}</strong></li><li><span>連絡先</span><strong>{{ company.phone || company.email ? '登録済み' : '未登録' }}</strong></li><li><span>法人番号</span><strong>{{ company.corporate_number ? '登録済み' : '未登録' }}</strong></li><li><span>銀行情報</span><strong>{{ company.bank_account_number ? '登録済み' : '未登録' }}</strong></li></ul></el-card>
        </aside>
      </div>
    </div>

    <el-dialog v-model="companyDialogVisible" title="会社情報を編集" width="720px">
      <el-form ref="companyFormRef" :model="companyForm" :rules="companyRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="会社名フリガナ" prop="name_kana"><el-input v-model="companyForm.name_kana" /></el-form-item>
          <el-form-item label="会社名" prop="name"><el-input v-model="companyForm.name" /></el-form-item>
          <el-form-item label="代表者顧客" prop="representative_customer" class="form-grid-full"><RemoteCustomerSelect v-model="companyForm.representative_customer" placeholder="氏名・カナ・電話・案件番号で検索" /></el-form-item>
          <el-form-item label="代表者フリガナ" prop="representative_name_kana"><el-input v-model="companyForm.representative_name_kana" /></el-form-item>
          <el-form-item label="代表者氏名" prop="representative_name"><el-input v-model="companyForm.representative_name" /></el-form-item>
          <el-form-item label="代表者郵便番号" prop="representative_postal_code"><el-input v-model="companyForm.representative_postal_code" /></el-form-item>
          <el-form-item label="代表者住所" prop="representative_address" class="form-grid-full"><el-input v-model="companyForm.representative_address" /></el-form-item>
          <el-form-item label="法人番号" prop="corporate_number"><el-input v-model="companyForm.corporate_number" /></el-form-item>
          <el-form-item label="会社法人等番号"><el-input :model-value="getCorporateRegistrationNumber(companyForm.corporate_number)" disabled /></el-form-item>
          <el-form-item label="電話番号" prop="phone"><el-input v-model="companyForm.phone" /></el-form-item>
          <el-form-item label="メール" prop="email"><el-input v-model="companyForm.email" /></el-form-item>
          <el-form-item label="郵便番号" prop="postal_code"><el-input v-model="companyForm.postal_code" /></el-form-item>
          <el-form-item label="住所" prop="address" class="form-grid-full"><el-input v-model="companyForm.address" /></el-form-item>
          <el-form-item label="決算月" prop="fiscal_month"><el-select v-model="companyForm.fiscal_month" clearable class="form-control"><el-option v-for="month in fiscalMonthOptions" :key="month" :label="`${month}月`" :value="month" /></el-select></el-form-item>
          <el-form-item label="事業所整理記号" prop="establishment_symbol"><el-input v-model="companyForm.establishment_symbol" /></el-form-item>
          <el-form-item label="事業所番号" prop="establishment_number"><el-input v-model="companyForm.establishment_number" /></el-form-item>
        </div>
        <h3 class="dialog-section-title">銀行情報</h3>
        <div class="form-grid">
          <el-form-item label="銀行名" prop="bank_name"><el-input v-model="companyForm.bank_name" /></el-form-item>
          <el-form-item label="支店名" prop="bank_branch"><el-input v-model="companyForm.bank_branch" /></el-form-item>
          <el-form-item label="預金種別" prop="bank_account_type"><el-select v-model="companyForm.bank_account_type" clearable class="form-control"><el-option v-for="type in bankAccountTypeOptions" :key="type" :label="type" :value="type" /></el-select></el-form-item>
          <el-form-item label="口座番号" prop="bank_account_number"><el-input v-model="companyForm.bank_account_number" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="companyDialogVisible = false">キャンセル</el-button><el-button type="primary" :loading="companySubmitting" @click="submitCompany">保存</el-button></template>
    </el-dialog>

    <el-dialog
      v-model="staffDialogVisible"
      :title="editingStaffId ? '従業員編集' : '従業員追加'"
      width="720px"
      @closed="resetStaffForm"
    >
      <el-form ref="staffFormRef" :model="staffForm" :rules="staffRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="役職" prop="position">
            <el-input v-model="staffForm.position" />
          </el-form-item>
          <el-form-item label="既存の顧客から選択" class="form-grid-full">
            <el-select
              v-model="staffForm.customer"
              clearable
              filterable
              placeholder="既に顧客として登録済みの場合はここで選択（未選択なら下で新規登録）"
              class="form-control"
            >
              <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
            </el-select>
          </el-form-item>
        </div>

        <template v-if="!staffForm.customer">
          <p class="section-optional-note">既存の顧客に該当しない場合は、新しい人物として以下を入力してください。</p>
          <div class="form-grid">
            <el-form-item label="フリガナ" prop="name_kana" class="form-grid-start">
              <el-input v-model="staffForm.name_kana" />
            </el-form-item>
            <el-form-item label="氏名" prop="name" class="form-grid-start">
              <el-input v-model="staffForm.name" />
            </el-form-item>
            <el-form-item label="生年月日" prop="birth_date">
              <el-date-picker v-model="staffForm.birth_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" />
            </el-form-item>
            <el-form-item label="性別" prop="gender">
              <el-select v-model="staffForm.gender" clearable placeholder="選択してください" class="form-control">
                <el-option v-for="gender in genderOptions" :key="gender.value" :label="gender.label" :value="gender.value" />
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
                <el-option v-for="status in residenceStatusOptions" :key="status.id" :label="status.name" :value="status.name" />
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
          </div>
        </template>
        <p v-else class="section-optional-note">
          氏名・生年月日などの個人情報は選択した顧客の情報を使用します。変更する場合は
          <router-link class="text-link" :to="`/customers/${staffForm.customer}`">その顧客の詳細ページ</router-link>
          から編集してください。
        </p>

        <div class="form-grid">
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

<style scoped>
.company-record-page {
  display: grid;
  gap: 16px;
}

.record-profile-header,
.record-main-card {
  min-width: 0;
}

.record-header-main,
.record-contact-row,
.record-tags,
.record-actions,
.staff-member-header,
.staff-member-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.record-avatar {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(135deg, #409eff, #67c23a);
  font-size: 22px;
  font-weight: 700;
}

.record-identity {
  min-width: 0;
}

.record-identity p,
.record-identity h2 {
  margin: 0;
}

.record-identity p {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.record-identity h2 {
  margin: 3px 0 7px;
  font-size: 23px;
}

.record-actions {
  margin-left: auto;
}

.record-contact-row {
  margin-top: 15px;
  padding-top: 13px;
  border-top: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.record-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.record-summary-tile {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  min-height: 72px;
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  color: var(--el-text-color-primary);
  background: #fff;
  cursor: pointer;
}

.record-summary-tile:hover,
.record-summary-tile:focus-visible {
  border-color: var(--el-color-primary);
  outline: none;
}

.record-summary-tile strong {
  font-size: 25px;
}

.record-summary-tile span {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.record-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
  align-items: start;
}

.company-overview-grid,
.staff-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.record-info-panel,
.staff-member-block {
  padding: 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: #fff;
}

.record-info-panel h3,
.record-section-heading h3 {
  margin: 0;
  font-size: 16px;
}

.record-field-list {
  margin: 10px 0 0;
}

.record-field-list > div {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 10px;
  padding: 8px 0;
  border-top: 1px solid var(--el-border-color-extra-light);
}

.record-field-list dt {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.record-field-list dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.record-section-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.record-section-heading p {
  margin: 5px 0 0;
  color: var(--el-text-color-secondary);
}

.dialog-section-title {
  margin: 8px 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 15px;
}

.staff-member-list {
  display: grid;
  gap: 14px;
}

.staff-member-block.is-retired {
  opacity: 0.72;
}

.staff-member-header {
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.company-history {
  margin-top: 18px;
}

.record-sidebar {
  display: grid;
  gap: 16px;
  position: sticky;
  top: 82px;
}

.primary-case-link {
  display: block;
  margin-bottom: 10px;
  overflow-wrap: anywhere;
}

.sidebar-list > div {
  grid-template-columns: 72px minmax(0, 1fr);
}

.company-data-status {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.company-data-status li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--el-text-color-secondary);
}

.company-data-status strong {
  color: var(--el-text-color-primary);
}

@media (max-width: 1050px) {
  .record-workspace {
    grid-template-columns: 1fr;
  }

  .record-sidebar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    position: static;
  }
}

@media (max-width: 720px) {
  .record-header-main,
  .record-section-heading,
  .staff-member-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .record-actions {
    margin-left: 0;
  }

  .record-summary-grid,
  .company-overview-grid,
  .staff-info-grid,
  .record-sidebar {
    grid-template-columns: 1fr;
  }

  .record-field-list > div {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
