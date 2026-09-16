<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { createCase, listCaseApplicationCategories, listCaseTypeMasters } from '../api/cases'
import { getCustomer, listResidenceStatusMasters, updateCustomer } from '../api/customers'
import { listEmployees } from '../api/employees'
import {
  createFamilyMember,
  deleteFamilyMember,
  listFamilyMembers,
  updateFamilyMember,
} from '../api/familyMembers'
import RemoteCustomerSelect from '../components/RemoteCustomerSelect.vue'
import type { CaseApplicationCategory, CasePayload, CaseTypeMaster, CreateCustomerPayload, Customer, CustomerCaseSummary, CustomerDetail, CustomerRelatedCompany, Employee, FamilyMember, FamilyMemberPayload, ResidenceStatusMaster, UpdateCustomerPayload } from '../types/api'
import { getCaseDisplayStatus, getCaseDisplayStatusTagType } from '../utils/caseStatus'
import { formatDate, formatDateTime } from '../utils/date'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const customer = ref<CustomerDetail | null>(null)
const cases = ref<CustomerCaseSummary[]>([])
const relatedCompanies = ref<CustomerRelatedCompany[]>([])
const familyMembers = ref<FamilyMember[]>([])
const activeSection = ref<'overview' | 'cases' | 'relationships' | 'activity'>('overview')
const customerSubmitting = ref(false)
const customerDialogVisible = ref(false)
const customerFormRef = ref<FormInstance>()
const familySubmitting = ref(false)
const familyEditTarget = ref<number | 'new' | null>(null)
const editingFamilyMemberId = ref<number | null>(null)
const familyFormRef = ref<FormInstance>()
const caseDialogVisible = ref(false)
const caseSubmitting = ref(false)
const caseFormRef = ref<FormInstance>()
const caseTypes = ref<CaseTypeMaster[]>([])
const applicationCategories = ref<CaseApplicationCategory[]>([])
const employees = ref<Employee[]>([])
const residenceStatusOptions = ref<ResidenceStatusMaster[]>([])
const caseForm = ref<CasePayload>({
  case_type_master: null,
  application_category: null,
  customer: null,
  company: null,
  responsible_employee: null,
})
interface FamilyEditForm {
  relationship: string
  family_customer: number | null
  is_dependent: boolean
  note: string
  name: string
  name_kana: string
  birth_date: string | null
  gender: string
  nationality: string
  phone: string
  email: string
  postal_code: string
  address: string
  my_number: string
  residence_status: string
  residence_card_no: string
  residence_expiry: string | null
  passport_no: string
  passport_expiry: string | null
}

const familyForm = ref<FamilyEditForm>({
  relationship: '',
  family_customer: null,
  is_dependent: true,
  note: '',
  name: '',
  name_kana: '',
  birth_date: null,
  gender: '',
  nationality: '',
  phone: '',
  email: '',
  postal_code: '',
  address: '',
  my_number: '',
  residence_status: '',
  residence_card_no: '',
  residence_expiry: null,
  passport_no: '',
  passport_expiry: null,
})

const caseTargetOptions = computed(() => {
  const seen = new Set<number>()
  const options: { id: number; label: string }[] = []
  if (customer.value) {
    options.push({ id: customerId.value, label: `${customer.value.name}（本人）` })
    seen.add(customerId.value)
  }
  for (const member of familyMembers.value) {
    if (!member.family_customer || seen.has(member.family_customer)) continue
    seen.add(member.family_customer)
    const relationship = getFamilyRelationshipLabel(member) || '家族'
    options.push({ id: member.family_customer, label: `${member.name}（${relationship}）` })
  }
  return options
})
const customerForm = ref<UpdateCustomerPayload>({
  name: '',
  name_kana: '',
  birth_date: '',
  gender: '',
  nationality: '',
  email: '',
  phone: '',
  postal_code: '',
  address: '',
  my_number: '',
  residence_status: '',
  residence_card_no: '',
  residence_expiry: null,
  passport_no: '',
  passport_expiry: null,
  note: '',
})

const customerId = computed(() => Number(route.params.id))

const relatedCases = computed(() => cases.value)
const activeCases = computed(() => relatedCases.value.filter((caseItem) => (
  caseItem.registration_status === 'active'
  && !['rejected', 'withdrawn', 'completed'].includes(caseItem.status)
)))
const historicalCases = computed(() => relatedCases.value.filter((caseItem) => (
  !activeCases.value.some((activeCase) => activeCase.id === caseItem.id)
)))
const primaryCase = computed(() => customer.value?.summary.primary_case || null)
const summaryItems = computed(() => [
  { key: 'cases' as const, label: '進行中案件', value: customer.value?.summary.active_cases_count || 0 },
  { key: 'cases' as const, label: '履歴案件', value: customer.value?.summary.historical_cases_count || 0 },
  { key: 'relationships' as const, label: '家族', value: customer.value?.summary.family_count || 0 },
  { key: 'relationships' as const, label: '関連会社', value: customer.value?.summary.company_count || 0 },
  { key: 'activity' as const, label: '最近の活動', value: customer.value?.recent_activities.length || 0 },
])

const buildExpiryRisk = (label: string, value?: string | null) => {
  if (!value) return null
  const today = new Date()
  const target = new Date(`${value}T00:00:00+09:00`)
  const days = Math.ceil((target.getTime() - today.getTime()) / 86400000)
  if (days < 0) return { label, date: value, message: `${Math.abs(days)}日超過`, type: 'error' as const }
  if (days <= 30) return { label, date: value, message: `あと${days}日`, type: 'error' as const }
  if (days <= 90) return { label, date: value, message: `あと${days}日`, type: 'warning' as const }
  return null
}

const expiryRisks = computed(() => [
  buildExpiryRisk('在留期限', customer.value?.residence_expiry),
  buildExpiryRisk('パスポート期限', customer.value?.passport_expiry),
].filter((item): item is NonNullable<typeof item> => Boolean(item)))
const relationshipOptions = [
  { label: '配偶者', value: 'spouse' },
  { label: '子', value: 'child' },
  { label: '父', value: 'father' },
  { label: '母', value: 'mother' },
  { label: '兄弟姉妹', value: 'sibling' },
  { label: 'その他', value: 'other' },
]

const relationshipOrder: Record<string, number> = {
  spouse: 0,
  '配偶者': 0,
  child: 1,
  '子': 1,
  father: 2,
  '父': 2,
  mother: 3,
  '母': 3,
  sibling: 4,
  '兄弟姉妹': 4,
  other: 5,
  'その他': 5,
}

const getFamilyRelationshipLabel = (familyMember: FamilyMember) => (
  familyMember.relationship_display || relationshipOptions.find((option) => (
    option.value === familyMember.relationship
  ))?.label || familyMember.relationship || ''
)

const sortedFamilyMembers = computed(() => (
  familyMembers.value
    .map((familyMember, index) => ({ familyMember, index }))
    .sort((left, right) => {
      const leftRelationship = getFamilyRelationshipLabel(left.familyMember) || left.familyMember.relationship
      const rightRelationship = getFamilyRelationshipLabel(right.familyMember) || right.familyMember.relationship
      const leftRank = relationshipOrder[leftRelationship] ?? 6
      const rightRank = relationshipOrder[rightRelationship] ?? 6
      if (leftRank !== rightRank) return leftRank - rightRank

      const leftDate = left.familyMember.birth_date || left.familyMember.created_at
      const rightDate = right.familyMember.birth_date || right.familyMember.created_at
      if (leftDate && rightDate && leftDate !== rightDate) {
        return leftDate.localeCompare(rightDate)
      }
      if (leftDate && !rightDate) return -1
      if (!leftDate && rightDate) return 1
      return left.index - right.index
    })
    .map(({ familyMember }) => familyMember)
))

const displayValue = (value?: string | null) => value || '-'

const genderOptions = [
  { label: '男性', value: 'male' },
  { label: '女性', value: 'female' },
  { label: 'その他', value: 'other' },
]

const customerRules: FormRules<UpdateCustomerPayload> = {
  name: [{ required: true, message: '氏名を入力してください。', trigger: 'blur' }],
  birth_date: [{ required: true, message: '生年月日を入力してください。', trigger: 'change' }],
}

const familyRules: FormRules<FamilyEditForm> = {
  relationship: [{ required: true, message: '関係を選択してください。', trigger: 'change' }],
  name: [
    {
      validator: (_rule, value, callback) => {
        if (!familyForm.value.family_customer && !value) {
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
        if (!familyForm.value.family_customer && !value) {
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
  customer: [{ required: true, message: '対象顧客を選択してください。', trigger: 'change' }],
  case_type_master: [{ required: true, message: '案件種別を選択してください。', trigger: 'change' }],
  application_category: [{ required: true, message: '申請区分を選択してください。', trigger: 'change' }],
}

const formatGender = (gender?: string | null) => {
  const labels: Record<string, string> = {
    male: '男性',
    female: '女性',
    other: 'その他',
  }
  return gender ? labels[gender] || gender : '-'
}

const copyText = async (value?: string | null) => {
  if (!value) return
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success('コピーしました。')
  } catch {
    ElMessage.error('コピーできませんでした。')
  }
}

const resetCustomerForm = () => {
  if (!customer.value) return
  customerForm.value = {
    name: customer.value.name,
    name_kana: customer.value.name_kana,
    birth_date: customer.value.birth_date,
    gender: customer.value.gender,
    nationality: customer.value.nationality,
    email: customer.value.email,
    phone: customer.value.phone,
    postal_code: customer.value.postal_code,
    address: customer.value.address,
    my_number: '',
    residence_status: customer.value.residence_status,
    residence_card_no: customer.value.residence_card_no,
    residence_expiry: customer.value.residence_expiry,
    passport_no: customer.value.passport_no,
    passport_expiry: customer.value.passport_expiry,
    note: customer.value.note,
  }
  customerFormRef.value?.clearValidate()
}

const openEditCustomerDialog = () => {
  resetCustomerForm()
  customerDialogVisible.value = true
}

const submitCustomer = async () => {
  if (!customerFormRef.value) return

  const valid = await customerFormRef.value.validate().catch(() => false)
  if (!valid) return

  customerSubmitting.value = true
  try {
    const { my_number, ...rest } = customerForm.value
    await updateCustomer(customerId.value, my_number ? { ...rest, my_number } : rest)
    await fetchCustomerDetail()
    ElMessage.success('顧客情報を更新しました。')
    customerDialogVisible.value = false
  } catch {
    ElMessage.error('顧客情報の更新に失敗しました。')
  } finally {
    customerSubmitting.value = false
  }
}

const fetchCustomerDetail = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [customerData, familyMemberData] = await Promise.all([
      getCustomer(customerId.value),
      listFamilyMembers({ customer: customerId.value }),
    ])
    customer.value = customerData
    familyMembers.value = familyMemberData.results
    cases.value = customerData.related_cases
    relatedCompanies.value = customerData.related_companies
  } catch {
    errorMessage.value = '顧客詳細の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const fetchCaseOptions = async () => {
  const [caseTypeData, applicationCategoryData, employeeData] = await Promise.all([
    listCaseTypeMasters({ is_active: true, ordering: 'sort_order' }),
    listCaseApplicationCategories({ is_active: true, ordering: 'sort_order' }),
    listEmployees({ is_active: true }),
  ])
  caseTypes.value = caseTypeData.results
  applicationCategories.value = applicationCategoryData.results
  employees.value = employeeData.results
}

const openCreateCaseDialog = async () => {
  if (!caseTypes.value.length || !applicationCategories.value.length) {
    await fetchCaseOptions()
  }
  caseForm.value = {
    case_type_master: null,
    application_category: null,
    customer: customerId.value,
    company: relatedCompanies.value[0]?.id || null,
    responsible_employee: null,
  }
  caseFormRef.value?.clearValidate()
  caseDialogVisible.value = true
}

const handleCaseTargetChange = (targetId: number) => {
  caseForm.value.company = targetId === customerId.value ? (relatedCompanies.value[0]?.id || null) : null
}

const submitCase = async () => {
  if (!caseFormRef.value) return
  const valid = await caseFormRef.value.validate().catch(() => false)
  if (!valid) return
  caseSubmitting.value = true
  try {
    await createCase({
      ...caseForm.value,
      company: caseForm.value.company || null,
      responsible_employee: caseForm.value.responsible_employee || null,
    })
    ElMessage.success('案件を追加しました。')
    caseDialogVisible.value = false
    await fetchCustomerDetail()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '案件の追加に失敗しました。')
  } finally {
    caseSubmitting.value = false
  }
}

const resetFamilyForm = () => {
  editingFamilyMemberId.value = null
  familyForm.value = {
    relationship: '',
    family_customer: null,
    is_dependent: true,
    note: '',
    name: '',
    name_kana: '',
    birth_date: null,
    gender: '',
    nationality: '',
    phone: '',
    email: '',
    postal_code: customer.value?.postal_code || '',
    address: customer.value?.address || '',
    my_number: '',
    residence_status: '',
    residence_card_no: '',
    residence_expiry: null,
    passport_no: '',
    passport_expiry: null,
  }
  familyFormRef.value?.clearValidate()
}

const startAddFamilyMember = () => {
  resetFamilyForm()
  familyEditTarget.value = 'new'
}

const handleFamilyCustomerChange = (selected: Customer | null) => {
  if (selected?.id === customerId.value) {
    familyForm.value.family_customer = null
    ElMessage.warning('本人を家族として選択することはできません。')
  }
}

const startEditFamilyMember = (familyMember: FamilyMember) => {
  editingFamilyMemberId.value = familyMember.id
  familyForm.value = {
    relationship: familyMember.relationship,
    family_customer: familyMember.family_customer,
    is_dependent: familyMember.is_dependent,
    note: familyMember.note,
    name: familyMember.name || '',
    name_kana: familyMember.name_kana || '',
    birth_date: familyMember.birth_date || null,
    gender: familyMember.gender || '',
    nationality: familyMember.nationality || '',
    phone: familyMember.phone || '',
    email: familyMember.email || '',
    postal_code: familyMember.postal_code || '',
    address: familyMember.address || '',
    my_number: '',
    residence_status: familyMember.residence_status || '',
    residence_card_no: familyMember.residence_card_no || '',
    residence_expiry: familyMember.residence_expiry || null,
    passport_no: familyMember.passport_no || '',
    passport_expiry: familyMember.passport_expiry || null,
  }
  familyFormRef.value?.clearValidate()
  familyEditTarget.value = familyMember.id
}

const cancelFamilyEdit = () => {
  familyEditTarget.value = null
  resetFamilyForm()
}

const submitFamilyMember = async () => {
  if (!familyFormRef.value) return

  const valid = await familyFormRef.value.validate().catch(() => false)
  if (!valid) return

  familySubmitting.value = true
  try {
    const payload: FamilyMemberPayload = {
      customer: customerId.value,
      relationship: familyForm.value.relationship,
      is_dependent: familyForm.value.is_dependent,
      note: familyForm.value.note,
    }
    if (familyForm.value.family_customer) {
      payload.family_customer = familyForm.value.family_customer
    } else {
      const newCustomer: CreateCustomerPayload = {
        name: familyForm.value.name,
        name_kana: familyForm.value.name_kana,
        birth_date: familyForm.value.birth_date || '',
        gender: familyForm.value.gender,
        nationality: familyForm.value.nationality,
        phone: familyForm.value.phone,
        email: familyForm.value.email,
        postal_code: familyForm.value.postal_code || customer.value?.postal_code || '',
        address: familyForm.value.address || customer.value?.address || '',
        my_number: familyForm.value.my_number,
        residence_status: familyForm.value.residence_status,
        residence_card_no: familyForm.value.residence_card_no,
        residence_expiry: familyForm.value.residence_expiry,
        passport_no: familyForm.value.passport_no,
        passport_expiry: familyForm.value.passport_expiry,
      }
      payload.new_customer = newCustomer
    }
    if (editingFamilyMemberId.value) {
      await updateFamilyMember(editingFamilyMemberId.value, payload)
      ElMessage.success('家族情報を更新しました。')
    } else {
      await createFamilyMember(payload)
      ElMessage.success('家族情報を追加しました。')
    }
    familyEditTarget.value = null
    await fetchCustomerDetail()
  } catch {
    errorMessage.value = editingFamilyMemberId.value
      ? '家族情報の更新に失敗しました。'
      : '家族情報の追加に失敗しました。'
  } finally {
    familySubmitting.value = false
  }
}

const confirmDeleteFamilyMember = async (familyMember: FamilyMember) => {
  try {
    await ElMessageBox.confirm(
      `「${familyMember.name}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteFamilyMember(familyMember.id)
    ElMessage.success('家族情報を削除しました。')
    if (familyEditTarget.value === familyMember.id) {
      familyEditTarget.value = null
    }
    await fetchCustomerDetail()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      errorMessage.value = '家族情報の削除に失敗しました。'
    }
  }
}

const fetchResidenceStatusOptions = async () => {
  const data = await listResidenceStatusMasters({ is_active: true, ordering: 'sort_order' })
  residenceStatusOptions.value = data.results
}

onMounted(() => {
  fetchCustomerDetail()
  fetchResidenceStatusOptions()
})
</script>

<template>
  <section class="page">
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />
    <div v-loading="loading" class="customer-record">
      <el-card v-if="customer" shadow="never" class="profile-header-card">
        <div class="profile-header-main">
          <div class="profile-avatar">{{ customer.name.slice(0, 1) }}</div>
          <div class="profile-identity">
            <div class="profile-kana">{{ displayValue(customer.name_kana) }}</div>
            <h1>{{ customer.name }}</h1>
            <div class="profile-tags">
              <el-tag v-if="customer.residence_status" effect="plain">{{ customer.residence_status }}</el-tag>
              <el-tag v-if="customer.primary_applicant" type="info" effect="plain">
                {{ customer.primary_applicant.name }}の{{ customer.primary_applicant.relationship_display }}
              </el-tag>
              <el-tag v-else-if="customer.dependents_count" type="success" effect="plain">
                家族 {{ customer.dependents_count }}名
              </el-tag>
              <span class="customer-id">顧客ID #{{ customer.id }}</span>
            </div>
          </div>
          <div class="profile-actions">
            <el-button @click="router.push('/customers')">一覧へ戻る</el-button>
            <el-button @click="openEditCustomerDialog">顧客情報を編集</el-button>
            <el-button type="primary" @click="openCreateCaseDialog">案件を追加</el-button>
          </div>
        </div>
        <div class="profile-contact-row">
          <button type="button" class="contact-chip" :disabled="!customer.phone" @click="copyText(customer.phone)">
            電話 {{ displayValue(customer.phone) }}
          </button>
          <button type="button" class="contact-chip" :disabled="!customer.email" @click="copyText(customer.email)">
            メール {{ displayValue(customer.email) }}
          </button>
          <span>最終更新 {{ formatDateTime(customer.updated_at) }}</span>
        </div>
      </el-card>

      <div v-if="expiryRisks.length" class="risk-list">
        <el-alert
          v-for="risk in expiryRisks"
          :key="risk.label"
          :title="`${risk.label}：${formatDate(risk.date)}（${risk.message}）`"
          :type="risk.type"
          show-icon
          :closable="false"
        />
      </div>

      <div v-if="customer" class="customer-summary-grid">
        <button
          v-for="item in summaryItems"
          :key="`${item.label}-${item.key}`"
          type="button"
          class="summary-tile"
          @click="activeSection = item.key"
        >
          <strong>{{ item.value }}</strong>
          <span>{{ item.label }}</span>
        </button>
      </div>

      <div v-if="customer" class="customer-workspace">
        <el-card shadow="never" class="customer-main-card">
          <el-tabs v-model="activeSection" class="customer-tabs">
            <el-tab-pane label="概要" name="overview">
              <div class="overview-grid">
                <section class="info-panel">
                  <h2>基本情報</h2>
                  <dl class="field-list">
                    <div><dt>生年月日</dt><dd>{{ formatDate(customer.birth_date) }}</dd></div>
                    <div><dt>性別</dt><dd>{{ formatGender(customer.gender) }}</dd></div>
                    <div><dt>国籍</dt><dd>{{ displayValue(customer.nationality) }}</dd></div>
                  </dl>
                </section>
                <section class="info-panel">
                  <h2>連絡先</h2>
                  <dl class="field-list">
                    <div><dt>電話番号</dt><dd>{{ displayValue(customer.phone) }}</dd></div>
                    <div><dt>メール</dt><dd>{{ displayValue(customer.email) }}</dd></div>
                    <div><dt>住所</dt><dd>〒{{ displayValue(customer.postal_code) }} {{ displayValue(customer.address) }}</dd></div>
                  </dl>
                </section>
                <section class="info-panel">
                  <h2>在留・旅券</h2>
                  <dl class="field-list">
                    <div><dt>在留資格</dt><dd>{{ displayValue(customer.residence_status) }}</dd></div>
                    <div><dt>在留カード番号</dt><dd class="confirmable-value">{{ displayValue(customer.residence_card_no) }}<el-button v-if="customer.residence_card_no" text type="primary" size="small" @click="copyText(customer.residence_card_no)">コピー</el-button></dd></div>
                    <div><dt>在留期限</dt><dd>{{ formatDate(customer.residence_expiry) }}</dd></div>
                    <div><dt>パスポート番号</dt><dd class="confirmable-value">{{ displayValue(customer.passport_no) }}<el-button v-if="customer.passport_no" text type="primary" size="small" @click="copyText(customer.passport_no)">コピー</el-button></dd></div>
                    <div><dt>パスポート期限</dt><dd>{{ formatDate(customer.passport_expiry) }}</dd></div>
                    <div><dt>マイナンバー</dt><dd>{{ customer.has_my_number ? '登録済み（既定では非表示）' : '未登録' }}</dd></div>
                  </dl>
                </section>
                <section class="info-panel">
                  <h2>内部メモ</h2>
                  <p class="note-content">{{ customer.note || '未登録' }}</p>
                </section>
              </div>
            </el-tab-pane>

            <el-tab-pane :label="`案件 ${relatedCases.length}`" name="cases">
              <div class="section-heading">
                <div>
                  <h2>進行中案件</h2>
                  <p>現在対応が必要な案件を優先して表示します。</p>
                </div>
                <el-button type="primary" @click="openCreateCaseDialog">案件を追加</el-button>
              </div>
              <el-table :data="activeCases" stripe>
                <el-table-column label="案件番号" min-width="190">
                  <template #default="{ row }"><router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link></template>
                </el-table-column>
                <el-table-column label="案件種別" min-width="160">
                  <template #default="{ row }">{{ row.case_type_master_name || row.case_type }}</template>
                </el-table-column>
                <el-table-column label="現在の進捗" width="150">
                  <template #default="{ row }"><el-tag :type="getCaseDisplayStatusTagType(row.status)">{{ getCaseDisplayStatus(row.status) }}</el-tag></template>
                </el-table-column>
                <el-table-column label="担当者" min-width="120"><template #default="{ row }">{{ displayValue(row.responsible_employee_name) }}</template></el-table-column>
                <el-table-column label="次の対応" min-width="190"><template #default="{ row }">{{ displayValue(row.next_action) }}<span v-if="row.next_action_due_at" class="due-date">{{ formatDate(row.next_action_due_at) }}</span></template></el-table-column>
              </el-table>
              <p v-if="!activeCases.length" class="empty-text">進行中の案件はありません。</p>

              <el-collapse v-if="historicalCases.length" class="history-collapse">
                <el-collapse-item :title="`履歴案件 ${historicalCases.length}件`" name="history">
                  <el-table :data="historicalCases" stripe>
                    <el-table-column label="案件番号" min-width="190"><template #default="{ row }"><router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link></template></el-table-column>
                    <el-table-column label="案件種別" min-width="160"><template #default="{ row }">{{ row.case_type_master_name || row.case_type }}</template></el-table-column>
                    <el-table-column label="進捗" width="140"><template #default="{ row }"><el-tag :type="getCaseDisplayStatusTagType(row.status)" effect="plain">{{ getCaseDisplayStatus(row.status) }}</el-tag></template></el-table-column>
                    <el-table-column label="更新日時" min-width="160"><template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template></el-table-column>
                  </el-table>
                </el-collapse-item>
              </el-collapse>
            </el-tab-pane>

            <el-tab-pane :label="`家族・関係 ${familyMembers.length + relatedCompanies.length}`" name="relationships">
              <div class="section-heading">
                <div><h2>家族</h2><p>人物情報は紐付く顧客主档から参照し、ここでは関係だけを管理します。</p></div>
                <el-button type="primary" :disabled="familyEditTarget !== null" @click="startAddFamilyMember">家族を追加</el-button>
              </div>

              <div v-if="familyEditTarget !== null" class="family-member-block family-member-edit-block">
                <h3 class="family-edit-title">{{ familyEditTarget === 'new' ? '家族を追加' : '家族情報を編集' }}</h3>
                <el-form ref="familyFormRef" :model="familyForm" :rules="familyRules" label-position="top">
                  <div class="form-grid">
                    <el-form-item label="関係" prop="relationship">
                      <el-select v-model="familyForm.relationship" placeholder="選択してください" class="form-control">
                        <el-option v-for="option in relationshipOptions" :key="option.value" :label="option.label" :value="option.value" />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="扶養対象" prop="is_dependent"><el-switch v-model="familyForm.is_dependent" active-text="はい" inactive-text="いいえ" /></el-form-item>
                    <el-form-item label="既存の顧客から選択" class="form-grid-full">
                      <RemoteCustomerSelect v-model="familyForm.family_customer" placeholder="氏名・カナ・電話・案件番号で検索" @change="handleFamilyCustomerChange" />
                    </el-form-item>
                  </div>
                  <template v-if="!familyForm.family_customer">
                    <p class="section-optional-note">既存顧客に該当しない場合のみ、新しい人物として入力してください。</p>
                    <div class="form-grid">
                      <el-form-item label="フリガナ" prop="name_kana" class="form-grid-start"><el-input v-model="familyForm.name_kana" /></el-form-item>
                      <el-form-item label="氏名" prop="name" class="form-grid-start"><el-input v-model="familyForm.name" /></el-form-item>
                      <el-form-item label="生年月日" prop="birth_date"><el-date-picker v-model="familyForm.birth_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" /></el-form-item>
                      <el-form-item label="性別" prop="gender"><el-select v-model="familyForm.gender" clearable placeholder="選択してください" class="form-control"><el-option v-for="option in genderOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
                      <el-form-item label="国籍" prop="nationality"><el-input v-model="familyForm.nationality" /></el-form-item>
                      <el-form-item label="電話番号" prop="phone"><el-input v-model="familyForm.phone" /></el-form-item>
                      <el-form-item label="メール" prop="email" class="form-grid-full"><el-input v-model="familyForm.email" /></el-form-item>
                      <el-form-item label="郵便番号" prop="postal_code" class="form-grid-start"><el-input v-model="familyForm.postal_code" /></el-form-item>
                      <el-form-item label="住所" prop="address" class="form-grid-full"><el-input v-model="familyForm.address" /></el-form-item>
                      <el-form-item label="マイナンバー" prop="my_number"><el-input v-model="familyForm.my_number" show-password /></el-form-item>
                      <el-form-item label="在留資格" prop="residence_status"><el-select v-model="familyForm.residence_status" clearable filterable allow-create default-first-option placeholder="選択してください" class="form-control"><el-option v-for="status in residenceStatusOptions" :key="status.id" :label="status.name" :value="status.name" /></el-select></el-form-item>
                      <el-form-item label="在留カード番号" prop="residence_card_no"><el-input v-model="familyForm.residence_card_no" /></el-form-item>
                      <el-form-item label="在留期限" prop="residence_expiry"><el-date-picker v-model="familyForm.residence_expiry" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" /></el-form-item>
                      <el-form-item label="パスポート番号" prop="passport_no"><el-input v-model="familyForm.passport_no" /></el-form-item>
                      <el-form-item label="パスポート期限" prop="passport_expiry"><el-date-picker v-model="familyForm.passport_expiry" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="YYYY-MM-DD" class="form-control" /></el-form-item>
                    </div>
                  </template>
                  <p v-else class="section-optional-note">個人情報は選択した顧客主档を使用します。</p>
                  <el-form-item label="関係の備考" prop="note"><el-input v-model="familyForm.note" type="textarea" :rows="2" /></el-form-item>
                </el-form>
                <div class="family-member-actions"><el-button @click="cancelFamilyEdit">キャンセル</el-button><el-button type="primary" :loading="familySubmitting" @click="submitFamilyMember">{{ familyEditTarget === 'new' ? '追加' : '保存' }}</el-button></div>
              </div>

              <div v-if="sortedFamilyMembers.length" class="family-detail-list">
                <article v-for="familyMember in sortedFamilyMembers" v-show="familyEditTarget !== familyMember.id" :key="familyMember.id" class="family-detail-card">
                  <header class="family-detail-header">
                    <div class="relationship-main">
                      <el-tag effect="plain">{{ getFamilyRelationshipLabel(familyMember) }}</el-tag>
                      <div>
                        <strong>{{ familyMember.name || '未入力' }}</strong>
                        <span>{{ displayValue(familyMember.name_kana) }}</span>
                      </div>
                      <el-tag v-if="familyMember.is_dependent" size="small" type="success" effect="plain">扶養対象</el-tag>
                    </div>
                    <div class="relationship-actions">
                      <el-tag v-if="familyMember.family_customer" type="info" effect="plain">人物情報連携済み</el-tag>
                      <el-tag v-else type="warning" effect="plain">旧形式データ</el-tag>
                      <el-button text type="primary" :disabled="familyEditTarget !== null" @click="startEditFamilyMember(familyMember)">関係を編集</el-button>
                      <el-button text type="danger" :disabled="familyEditTarget !== null" @click="confirmDeleteFamilyMember(familyMember)">削除</el-button>
                    </div>
                  </header>
                  <div class="family-info-grid">
                    <section>
                      <h3>基本・連絡先</h3>
                      <dl class="field-list compact-field-list">
                        <div><dt>生年月日</dt><dd>{{ formatDate(familyMember.birth_date) }}</dd></div>
                        <div><dt>性別</dt><dd>{{ displayValue(familyMember.gender_display || formatGender(familyMember.gender)) }}</dd></div>
                        <div><dt>国籍</dt><dd>{{ displayValue(familyMember.nationality) }}</dd></div>
                        <div><dt>電話番号</dt><dd>{{ displayValue(familyMember.phone) }}</dd></div>
                        <div><dt>メール</dt><dd>{{ displayValue(familyMember.email) }}</dd></div>
                        <div><dt>住所</dt><dd>〒{{ displayValue(familyMember.postal_code) }} {{ displayValue(familyMember.address) }}</dd></div>
                      </dl>
                    </section>
                    <section>
                      <h3>在留・旅券</h3>
                      <dl class="field-list compact-field-list">
                        <div><dt>在留資格</dt><dd>{{ displayValue(familyMember.residence_status) }}</dd></div>
                        <div><dt>在留カード番号</dt><dd>{{ displayValue(familyMember.residence_card_no) }}</dd></div>
                        <div><dt>在留期限</dt><dd>{{ formatDate(familyMember.residence_expiry) }}</dd></div>
                        <div><dt>パスポート番号</dt><dd>{{ displayValue(familyMember.passport_no) }}</dd></div>
                        <div><dt>パスポート期限</dt><dd>{{ formatDate(familyMember.passport_expiry) }}</dd></div>
                        <div><dt>マイナンバー</dt><dd>{{ familyMember.has_my_number ? '登録済み' : '未登録' }}</dd></div>
                      </dl>
                    </section>
                  </div>
                  <p v-if="familyMember.note" class="family-note"><strong>関係の備考：</strong>{{ familyMember.note }}</p>
                </article>
              </div>
              <p v-else-if="familyEditTarget === null" class="empty-text">家族情報はありません。</p>

              <div class="section-heading company-heading"><div><h2>関連会社</h2><p>会社の詳細情報は会社ページで管理します。</p></div></div>
              <div v-if="relatedCompanies.length" class="relationship-list">
                <div v-for="company in relatedCompanies" :key="company.id" class="relationship-row">
                  <div class="relationship-main">
                    <div><router-link class="text-link relationship-name" :to="`/companies/${company.id}`">{{ company.name }}</router-link><span>{{ [company.phone, company.email].filter(Boolean).join(' / ') || '連絡先未登録' }}</span></div>
                  </div>
                  <div class="company-relation-meta">
                    <el-tag v-for="label in company.relation_labels" :key="label" size="small" effect="plain">{{ label }}</el-tag>
                    <span v-if="company.positions.length">{{ company.positions.join(' / ') }}</span>
                    <span>進行中案件 {{ company.active_cases_count }}件</span>
                  </div>
                </div>
              </div>
              <p v-else class="empty-text">関連会社はありません。</p>
            </el-tab-pane>

            <el-tab-pane :label="`活動 ${customer.recent_activities.length}`" name="activity">
              <div class="section-heading"><div><h2>最近の活動</h2><p>関連案件の進捗記録を新しい順に表示します。</p></div></div>
              <el-timeline v-if="customer.recent_activities.length" class="activity-timeline">
                <el-timeline-item v-for="activity in customer.recent_activities" :key="activity.id" :timestamp="formatDate(activity.occurred_at || activity.created_at)" placement="top">
                  <div class="activity-card"><div class="activity-title"><strong>{{ activity.title }}</strong><el-tag v-if="activity.event_type" size="small" type="info" effect="plain">自動</el-tag></div><p v-if="activity.content">{{ activity.content }}</p><div class="activity-meta"><router-link class="text-link" :to="`/cases/${activity.case_id}`">{{ activity.case_number }}</router-link><span>{{ activity.actor_name || 'システム' }}</span></div></div>
                </el-timeline-item>
              </el-timeline>
              <p v-else class="empty-text">活動記録はありません。</p>
            </el-tab-pane>
          </el-tabs>
        </el-card>

        <aside class="customer-sidebar">
          <el-card shadow="never">
            <template #header>現在の対応</template>
            <template v-if="primaryCase">
              <router-link class="text-link sidebar-case-number" :to="`/cases/${primaryCase.id}`">{{ primaryCase.case_number }}</router-link>
              <el-tag :type="getCaseDisplayStatusTagType(primaryCase.status)" class="sidebar-status">{{ getCaseDisplayStatus(primaryCase.status) }}</el-tag>
              <dl class="sidebar-fields">
                <div><dt>担当者</dt><dd>{{ displayValue(primaryCase.responsible_employee_name) }}</dd></div>
                <div><dt>次の対応</dt><dd>{{ displayValue(primaryCase.next_action) }}</dd></div>
                <div><dt>期限</dt><dd>{{ formatDate(primaryCase.next_action_due_at) }}</dd></div>
              </dl>
              <el-button type="primary" plain class="sidebar-action" @click="router.push(`/cases/${primaryCase.id}`)">案件を開く</el-button>
            </template>
            <p v-else class="empty-text sidebar-empty">関連案件はありません。</p>
          </el-card>
          <el-card shadow="never">
            <template #header>データ状態</template>
            <ul class="data-status-list">
              <li><span>本人情報</span><strong>{{ customer.name && customer.birth_date ? '確認可能' : '要確認' }}</strong></li>
              <li><span>連絡先</span><strong>{{ customer.phone || customer.email ? '登録済み' : '未登録' }}</strong></li>
              <li><span>在留期限</span><strong>{{ customer.residence_expiry ? formatDate(customer.residence_expiry) : '未登録' }}</strong></li>
              <li><span>マイナンバー</span><strong>{{ customer.has_my_number ? '登録済み' : '未登録' }}</strong></li>
            </ul>
          </el-card>
        </aside>
      </div>
    </div>

    <el-dialog
      v-model="customerDialogVisible"
      title="顧客情報を編集"
      width="680px"
      @closed="resetCustomerForm"
    >
      <el-form ref="customerFormRef" :model="customerForm" :rules="customerRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="フリガナ" prop="name_kana" class="form-grid-start">
            <el-input v-model="customerForm.name_kana" />
          </el-form-item>
          <el-form-item label="氏名" prop="name" class="form-grid-start">
            <el-input v-model="customerForm.name" />
          </el-form-item>
          <el-form-item label="生年月日" prop="birth_date">
            <el-date-picker
              v-model="customerForm.birth_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="性別" prop="gender">
            <el-select v-model="customerForm.gender" clearable placeholder="選択してください" class="form-control">
              <el-option v-for="option in genderOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="国籍" prop="nationality">
            <el-input v-model="customerForm.nationality" />
          </el-form-item>
          <el-form-item label="電話番号" prop="phone">
            <el-input v-model="customerForm.phone" />
          </el-form-item>
          <el-form-item label="メール" prop="email" class="form-grid-full">
            <el-input v-model="customerForm.email" />
          </el-form-item>
          <el-form-item label="郵便番号" prop="postal_code" class="form-grid-start">
            <el-input v-model="customerForm.postal_code" />
          </el-form-item>
          <el-form-item label="住所" prop="address" class="form-grid-full">
            <el-input v-model="customerForm.address" />
          </el-form-item>
          <el-form-item label="在留資格" prop="residence_status" class="form-grid-full">
            <el-select
              v-model="customerForm.residence_status"
              clearable
              filterable
              allow-create
              default-first-option
              placeholder="選択してください"
              class="form-control"
            >
              <el-option
                v-for="status in residenceStatusOptions"
                :key="status.id"
                :label="status.name"
                :value="status.name"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="在留カード番号" prop="residence_card_no">
            <el-input v-model="customerForm.residence_card_no" />
          </el-form-item>
          <el-form-item label="在留期限" prop="residence_expiry">
            <el-date-picker
              v-model="customerForm.residence_expiry"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="パスポート番号" prop="passport_no">
            <el-input v-model="customerForm.passport_no" />
          </el-form-item>
          <el-form-item label="パスポート期限" prop="passport_expiry">
            <el-date-picker
              v-model="customerForm.passport_expiry"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="マイナンバー" prop="my_number">
            <el-input
              v-model="customerForm.my_number"
              show-password
              placeholder="変更する場合のみ入力"
            />
          </el-form-item>
        </div>
        <el-form-item label="備考" prop="note">
          <el-input v-model="customerForm.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="customerDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="customerSubmitting" @click="submitCustomer">保存</el-button>
      </template>
    </el-dialog>


    <el-dialog v-model="caseDialogVisible" title="案件追加" width="560px">
      <el-form ref="caseFormRef" :model="caseForm" :rules="caseRules" label-position="top">
        <el-form-item label="対象顧客" prop="customer">
          <el-select
            v-model="caseForm.customer"
            filterable
            placeholder="選択してください"
            class="form-control"
            @change="handleCaseTargetChange"
          >
            <el-option v-for="option in caseTargetOptions" :key="option.id" :label="option.label" :value="option.id" />
          </el-select>
        </el-form-item>
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
        <el-form-item label="会社">
          <el-select v-model="caseForm.company" clearable filterable placeholder="選択してください" class="form-control">
            <el-option v-for="company in relatedCompanies" :key="company.id" :label="company.name" :value="company.id" />
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
.customer-record {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.profile-header-card :deep(.el-card__body) {
  padding: 22px 24px 18px;
}

.profile-header-main {
  display: flex;
  align-items: center;
  gap: 18px;
}

.profile-avatar {
  display: grid;
  flex: 0 0 58px;
  width: 58px;
  height: 58px;
  place-items: center;
  border-radius: 16px;
  color: var(--sunrise-text);
  background: linear-gradient(135deg, var(--sunrise-blue), var(--sunrise-pink));
  font-size: 24px;
  font-weight: 700;
}

.profile-identity {
  min-width: 0;
}

.profile-identity h1 {
  margin: 2px 0 8px;
  color: var(--sunrise-text);
  font-size: 26px;
  line-height: 1.25;
}

.profile-kana,
.customer-id,
.profile-contact-row,
.section-heading p,
.relationship-main span,
.company-relation-meta,
.activity-meta {
  color: var(--sunrise-muted);
  font-size: 13px;
}

.profile-tags,
.profile-actions,
.profile-contact-row,
.relationship-actions,
.company-relation-meta,
.activity-title,
.activity-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.profile-actions {
  margin-left: auto;
  justify-content: flex-end;
}

.profile-contact-row {
  gap: 14px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--sunrise-border);
}

.contact-chip {
  padding: 0;
  color: var(--sunrise-link);
  background: transparent;
  border: 0;
  cursor: pointer;
}

.contact-chip:disabled {
  color: var(--sunrise-muted);
  cursor: default;
}

.risk-list {
  display: grid;
  gap: 8px;
}

.customer-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.summary-tile {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  min-height: 74px;
  padding: 16px;
  color: var(--sunrise-text);
  background: #fff;
  border: 1px solid var(--sunrise-border);
  border-radius: 8px;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(170, 212, 244, 0.1);
}

.summary-tile:hover,
.summary-tile:focus-visible {
  border-color: var(--sunrise-blue);
  outline: none;
}

.summary-tile strong {
  font-size: 26px;
}

.summary-tile span {
  color: var(--sunrise-muted);
  font-size: 13px;
}

.customer-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
  align-items: start;
}

.customer-main-card {
  min-width: 0;
}

.customer-tabs :deep(.el-tabs__header) {
  margin-bottom: 20px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.info-panel {
  padding: 18px;
  border: 1px solid var(--sunrise-border);
  border-radius: 8px;
  background: #fff;
}

.info-panel h2,
.section-heading h2 {
  margin: 0;
  color: var(--sunrise-text);
  font-size: 16px;
}

.field-list,
.sidebar-fields {
  margin: 14px 0 0;
}

.field-list > div,
.sidebar-fields > div {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 12px;
  padding: 9px 0;
  border-top: 1px solid #edf3f7;
}

.field-list dt,
.sidebar-fields dt {
  color: var(--sunrise-muted);
  font-size: 13px;
}

.field-list dd,
.sidebar-fields dd {
  min-width: 0;
  margin: 0;
  color: var(--sunrise-text);
  overflow-wrap: anywhere;
}

.confirmable-value {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.note-content {
  margin: 14px 0 0;
  color: var(--sunrise-text);
  line-height: 1.8;
  white-space: pre-wrap;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-heading p {
  margin: 5px 0 0;
}

.due-date {
  display: block;
  margin-top: 3px;
  color: var(--sunrise-muted);
  font-size: 12px;
}

.history-collapse {
  margin-top: 18px;
}

.relationship-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.family-detail-list {
  display: grid;
  gap: 14px;
}

.family-detail-card {
  padding: 16px;
  border: 1px solid var(--sunrise-border);
  border-radius: 8px;
  background: #fff;
}

.family-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #edf3f7;
}

.family-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  padding-top: 12px;
}

.family-info-grid h3 {
  margin: 0;
  color: var(--sunrise-text);
  font-size: 14px;
}

.compact-field-list {
  margin-top: 8px;
}

.compact-field-list > div {
  grid-template-columns: 110px minmax(0, 1fr);
  padding: 7px 0;
}

.family-note {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: 6px;
  color: var(--sunrise-text);
  background: var(--sunrise-bg-soft, #f8fbfd);
  white-space: pre-wrap;
}

.relationship-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid var(--sunrise-border);
  border-radius: 8px;
  background: #fff;
}

.relationship-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.relationship-main > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.relationship-name {
  font-size: 15px;
}

.company-heading {
  margin-top: 28px;
}

.company-relation-meta {
  justify-content: flex-end;
}

.activity-timeline {
  padding-top: 6px;
}

.activity-card {
  padding: 14px 16px;
  border: 1px solid var(--sunrise-border);
  border-radius: 8px;
  background: #fff;
}

.activity-title {
  justify-content: space-between;
  color: var(--sunrise-text);
}

.activity-card p {
  margin: 8px 0;
  line-height: 1.65;
  white-space: pre-wrap;
}

.activity-meta {
  justify-content: space-between;
}

.customer-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: 82px;
}

.sidebar-case-number {
  display: block;
  margin-bottom: 10px;
  overflow-wrap: anywhere;
}

.sidebar-status {
  margin-bottom: 4px;
}

.sidebar-fields > div {
  grid-template-columns: 72px minmax(0, 1fr);
}

.sidebar-action {
  width: 100%;
  margin-top: 12px;
}

.sidebar-empty {
  margin-top: 0;
}

.data-status-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.data-status-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--sunrise-muted);
  font-size: 13px;
}

.data-status-list strong {
  color: var(--sunrise-text);
  font-weight: 600;
  text-align: right;
}

.family-member-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.family-member-edit-block {
  margin-bottom: 16px;
  background: var(--sunrise-bg-soft, #f8fbfd);
}

.family-edit-title {
  margin: 0 0 12px;
  font-size: 15px;
}

.family-unlinked-hint {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--el-text-color-secondary, #909399);
}

@media (max-width: 1100px) {
  .customer-summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .customer-workspace {
    grid-template-columns: 1fr;
  }

  .customer-sidebar {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    position: static;
  }
}

@media (max-width: 720px) {
  .profile-header-main,
  .relationship-row,
  .family-detail-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .profile-actions {
    width: 100%;
    margin-left: 0;
    justify-content: flex-start;
  }

  .customer-summary-grid,
  .overview-grid,
  .customer-sidebar,
  .family-info-grid {
    grid-template-columns: 1fr;
  }

  .relationship-actions,
  .company-relation-meta {
    justify-content: flex-start;
  }

  .field-list > div {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
