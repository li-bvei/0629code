<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { listCases } from '../api/cases'
import { getCompany } from '../api/companies'
import { getCustomer, updateCustomer } from '../api/customers'
import { residenceStatusOptions } from '../constants/options'
import {
  createFamilyMember,
  deleteFamilyMember,
  listFamilyMembers,
  updateFamilyMember,
} from '../api/familyMembers'
import type { Case, Company, Customer, FamilyMember, FamilyMemberPayload, UpdateCustomerPayload } from '../types/api'
import { formatDate, formatDateTime } from '../utils/date'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const customer = ref<Customer | null>(null)
const cases = ref<Case[]>([])
const relatedCompanies = ref<Company[]>([])
const familyMembers = ref<FamilyMember[]>([])
const customerSubmitting = ref(false)
const customerDialogVisible = ref(false)
const customerFormRef = ref<FormInstance>()
const familySubmitting = ref(false)
const familyDialogVisible = ref(false)
const editingFamilyMemberId = ref<number | null>(null)
const familyFormRef = ref<FormInstance>()
const familyForm = ref<FamilyMemberPayload>({
  customer: 0,
  relationship: '',
  name: '',
  name_kana: '',
  birth_date: null,
  gender: '',
  nationality: '',
  phone: '',
  postal_code: '',
  address: '',
  my_number: '',
  residence_status: '',
  residence_card_no: '',
  residence_expiry: null,
  is_dependent: true,
  note: '',
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
const formatFiscalMonth = (value?: string | null) => (value ? `${value}月` : '-')
const getRepresentativeName = (company: Company) => (
  company.representative_customer_name || company.representative_name
)
const getFamilyCardTitle = (familyMember: FamilyMember) => {
  const relationship = getFamilyRelationshipLabel(familyMember) || '家族'
  const name = familyMember.name || '未入力'
  return `${relationship}　${name}`
}

const genderOptions = [
  { label: '男性', value: '男性' },
  { label: '女性', value: '女性' },
  { label: 'その他', value: 'その他' },
]

const customerRules: FormRules<UpdateCustomerPayload> = {
  name: [{ required: true, message: '氏名を入力してください。', trigger: 'blur' }],
  birth_date: [{ required: true, message: '生年月日を入力してください。', trigger: 'change' }],
}

const familyRules: FormRules<FamilyMemberPayload> = {
  relationship: [{ required: true, message: '関係を選択してください。', trigger: 'change' }],
  name: [{ required: true, message: '氏名を入力してください。', trigger: 'blur' }],
}

const formatGender = (gender?: string | null) => {
  const labels: Record<string, string> = {
    male: '男性',
    female: '女性',
    other: 'その他',
  }
  return gender ? labels[gender] || gender : '-'
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
    my_number: customer.value.my_number,
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
    customer.value = await updateCustomer(customerId.value, customerForm.value)
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
    const [customerData, familyMemberData, caseData] = await Promise.all([
      getCustomer(customerId.value),
      listFamilyMembers({ customer: customerId.value }),
      listCases({ customer: customerId.value }),
    ])
    customer.value = customerData
    familyMembers.value = familyMemberData.results
    cases.value = caseData.results
    const companyIds = Array.from(new Set(
      caseData.results
        .map((caseItem) => caseItem.company)
        .filter((companyId): companyId is number => companyId !== null),
    ))
    relatedCompanies.value = await Promise.all(companyIds.map((companyId) => getCompany(companyId)))
  } catch {
    errorMessage.value = '顧客詳細の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const fetchFamilyMembers = async () => {
  const data = await listFamilyMembers({ customer: customerId.value })
  familyMembers.value = data.results
}

const resetFamilyForm = () => {
  editingFamilyMemberId.value = null
  familyForm.value = {
    customer: customerId.value,
    relationship: '',
    name: '',
    name_kana: '',
    birth_date: null,
    gender: '',
    nationality: '',
    phone: '',
    postal_code: customer.value?.postal_code || '',
    address: customer.value?.address || '',
    my_number: '',
    residence_status: '',
    residence_card_no: '',
    residence_expiry: null,
    is_dependent: true,
    note: '',
  }
  familyFormRef.value?.clearValidate()
}

const openCreateFamilyDialog = () => {
  resetFamilyForm()
  familyDialogVisible.value = true
}

const openEditFamilyDialog = (familyMember: FamilyMember) => {
  editingFamilyMemberId.value = familyMember.id
  familyForm.value = {
    customer: customerId.value,
    relationship: familyMember.relationship,
    name: familyMember.name,
    name_kana: familyMember.name_kana,
    birth_date: familyMember.birth_date,
    gender: familyMember.gender,
    nationality: familyMember.nationality,
    phone: familyMember.phone,
    postal_code: familyMember.postal_code,
    address: familyMember.address,
    my_number: familyMember.my_number,
    residence_status: familyMember.residence_status,
    residence_card_no: familyMember.residence_card_no,
    residence_expiry: familyMember.residence_expiry,
    is_dependent: familyMember.is_dependent,
    note: familyMember.note,
  }
  familyFormRef.value?.clearValidate()
  familyDialogVisible.value = true
}

const submitFamilyMember = async () => {
  if (!familyFormRef.value) return

  const valid = await familyFormRef.value.validate().catch(() => false)
  if (!valid) return

  familySubmitting.value = true
  try {
    const payload = {
      ...familyForm.value,
      customer: customerId.value,
      postal_code: familyForm.value.postal_code || customer.value?.postal_code || '',
      address: familyForm.value.address || customer.value?.address || '',
    }
    if (editingFamilyMemberId.value) {
      await updateFamilyMember(editingFamilyMemberId.value, payload)
      ElMessage.success('家族情報を更新しました。')
    } else {
      await createFamilyMember(payload)
      ElMessage.success('家族情報を追加しました。')
    }
    familyDialogVisible.value = false
    await fetchFamilyMembers()
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
    await fetchFamilyMembers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      errorMessage.value = '家族情報の削除に失敗しました。'
    }
  }
}

onMounted(() => {
  fetchCustomerDetail()
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>顧客詳細</h1>
      <el-button @click="router.push('/customers')">一覧へ戻る</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <div v-loading="loading" class="detail-grid">
      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>基本情報</span>
            <el-button type="primary" @click="openEditCustomerDialog">編集</el-button>
          </div>
        </template>
        <el-descriptions v-if="customer" :column="2" border>
          <el-descriptions-item label="フリガナ" :span="2">{{ displayValue(customer.name_kana) }}</el-descriptions-item>
          <el-descriptions-item label="氏名" :span="2">{{ displayValue(customer.name) }}</el-descriptions-item>
          <el-descriptions-item label="生年月日">{{ formatDate(customer.birth_date) }}</el-descriptions-item>
          <el-descriptions-item label="性別">{{ formatGender(customer.gender) }}</el-descriptions-item>
          <el-descriptions-item label="国籍">{{ displayValue(customer.nationality) }}</el-descriptions-item>
          <el-descriptions-item label="電話番号">{{ displayValue(customer.phone) }}</el-descriptions-item>
          <el-descriptions-item label="メール" :span="2">{{ displayValue(customer.email) }}</el-descriptions-item>
          <el-descriptions-item label="郵便番号" :span="2">{{ displayValue(customer.postal_code) }}</el-descriptions-item>
          <el-descriptions-item label="住所" :span="2">{{ displayValue(customer.address) }}</el-descriptions-item>
          <el-descriptions-item label="在留資格" :span="2">{{ displayValue(customer.residence_status) }}</el-descriptions-item>
          <el-descriptions-item label="在留カード番号">{{ displayValue(customer.residence_card_no) }}</el-descriptions-item>
          <el-descriptions-item label="在留期限">{{ formatDate(customer.residence_expiry) }}</el-descriptions-item>
          <el-descriptions-item label="パスポート番号">{{ displayValue(customer.passport_no) }}</el-descriptions-item>
          <el-descriptions-item label="パスポート期限">{{ formatDate(customer.passport_expiry) }}</el-descriptions-item>
          <el-descriptions-item label="マイナンバー">{{ displayValue(customer.my_number) }}</el-descriptions-item>
          <el-descriptions-item label="備考" :span="2">{{ displayValue(customer.note) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>家族情報</span>
            <el-button type="primary" @click="openCreateFamilyDialog">家族を追加</el-button>
          </div>
        </template>
        <div v-if="sortedFamilyMembers.length" class="family-member-list">
          <div v-for="familyMember in sortedFamilyMembers" :key="familyMember.id" class="family-member-block">
            <div class="family-member-header">
              <strong>{{ getFamilyCardTitle(familyMember) }}</strong>
              <el-dropdown trigger="click">
                <el-button text type="primary" class="table-action-trigger">
                  操作
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="openEditFamilyDialog(familyMember)">編集</el-dropdown-item>
                    <el-dropdown-item divided class="danger-item" @click="confirmDeleteFamilyMember(familyMember)">削除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="フリガナ" :span="2">{{ displayValue(familyMember.name_kana) }}</el-descriptions-item>
              <el-descriptions-item label="氏名" :span="2">{{ displayValue(familyMember.name) }}</el-descriptions-item>
              <el-descriptions-item label="関係">{{ displayValue(familyMember.relationship_display) }}</el-descriptions-item>
              <el-descriptions-item label="生年月日">{{ formatDate(familyMember.birth_date) }}</el-descriptions-item>
              <el-descriptions-item label="性別">{{ displayValue(familyMember.gender_display) }}</el-descriptions-item>
              <el-descriptions-item label="国籍">{{ displayValue(familyMember.nationality) }}</el-descriptions-item>
              <el-descriptions-item label="電話番号">{{ displayValue(familyMember.phone) }}</el-descriptions-item>
              <el-descriptions-item label="郵便番号" :span="2">{{ displayValue(familyMember.postal_code) }}</el-descriptions-item>
              <el-descriptions-item label="住所" :span="2">{{ displayValue(familyMember.address) }}</el-descriptions-item>
              <el-descriptions-item label="在留資格" :span="2">{{ displayValue(familyMember.residence_status) }}</el-descriptions-item>
              <el-descriptions-item label="在留カード番号">{{ displayValue(familyMember.residence_card_no) }}</el-descriptions-item>
              <el-descriptions-item label="在留期限">{{ formatDate(familyMember.residence_expiry) }}</el-descriptions-item>
              <el-descriptions-item label="マイナンバー">{{ displayValue(familyMember.my_number) }}</el-descriptions-item>
              <el-descriptions-item label="扶養対象">{{ familyMember.is_dependent ? 'はい' : 'いいえ' }}</el-descriptions-item>
              <el-descriptions-item label="備考" :span="2">{{ displayValue(familyMember.note) }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
        <p v-if="!familyMembers.length" class="empty-text">該当データなし</p>
      </el-card>

      <el-card shadow="never">
        <template #header>関連会社</template>
        <div v-if="relatedCompanies.length" class="related-company-list">
          <div v-for="company in relatedCompanies" :key="company.id" class="related-company-block">
            <div class="related-company-header">
              <strong>
                <router-link class="text-link" :to="`/companies/${company.id}`">
                  {{ displayValue(company.name) }}
                </router-link>
              </strong>
            </div>

            <div class="company-info-section">
              <h3>基本情報</h3>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="会社名フリガナ" :span="2">
                  {{ displayValue(company.name_kana) }}
                </el-descriptions-item>
                <el-descriptions-item label="会社名" :span="2">
                  {{ displayValue(company.name) }}
                </el-descriptions-item>
                <el-descriptions-item label="代表者フリガナ" :span="2">
                  {{ displayValue(company.representative_name_kana) }}
                </el-descriptions-item>
                <el-descriptions-item label="代表者氏名" :span="2">
                  {{ displayValue(getRepresentativeName(company)) }}
                </el-descriptions-item>
                <el-descriptions-item label="法人番号">
                  {{ displayValue(company.corporate_number) }}
                </el-descriptions-item>
                <el-descriptions-item label="会社法人等番号">
                  {{ displayValue(company.corporate_registration_number) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="company-info-section">
              <h3>連絡先</h3>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="メール">
                  {{ displayValue(company.email) }}
                </el-descriptions-item>
                <el-descriptions-item label="電話番号">
                  {{ displayValue(company.phone) }}
                </el-descriptions-item>
                <el-descriptions-item label="郵便番号" :span="2">
                  {{ displayValue(company.postal_code) }}
                </el-descriptions-item>
                <el-descriptions-item label="住所" :span="2">
                  {{ displayValue(company.address) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="company-info-section">
              <h3>決算情報</h3>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="決算月">
                  {{ formatFiscalMonth(company.fiscal_month) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="company-info-section">
              <h3>銀行情報</h3>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="銀行名">
                  {{ displayValue(company.bank_name) }}
                </el-descriptions-item>
                <el-descriptions-item label="支店名">
                  {{ displayValue(company.bank_branch) }}
                </el-descriptions-item>
                <el-descriptions-item label="預金種別">
                  {{ displayValue(company.bank_account_type) }}
                </el-descriptions-item>
                <el-descriptions-item label="口座番号">
                  {{ displayValue(company.bank_account_number) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <div class="company-info-section">
              <h3>システム情報</h3>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="作成日時">
                  {{ formatDateTime(company.created_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="更新日時">
                  {{ formatDateTime(company.updated_at) }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </div>
        </div>
        <p v-if="!relatedCompanies.length" class="empty-text">関連会社はありません</p>
      </el-card>

      <el-card shadow="never">
        <template #header>関連案件</template>
        <el-table :data="relatedCases" stripe>
          <el-table-column label="案件番号" min-width="150">
            <template #default="{ row }">
              <router-link class="text-link" :to="`/cases/${row.id}`">
                {{ row.case_number }}
              </router-link>
            </template>
          </el-table-column>
          <el-table-column prop="case_type" label="案件種別" min-width="150" />
          <el-table-column prop="status" label="ステータス" width="130" />
          <el-table-column prop="company_name" label="会社名" min-width="180">
            <template #default="{ row }">{{ displayValue(row.company_name) }}</template>
          </el-table-column>
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

      <el-card shadow="never" class="placeholder-card">
        <template #header>申請書作成</template>
        <p>準備中</p>
      </el-card>
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
                :key="status"
                :label="status"
                :value="status"
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
            <el-input v-model="customerForm.my_number" />
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

    <el-dialog
      v-model="familyDialogVisible"
      :title="editingFamilyMemberId ? '家族情報編集' : '家族を追加'"
      width="640px"
      @closed="resetFamilyForm"
    >
      <el-form ref="familyFormRef" :model="familyForm" :rules="familyRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="関係" prop="relationship">
            <el-select v-model="familyForm.relationship" placeholder="選択してください" class="form-control">
              <el-option
                v-for="option in relationshipOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="フリガナ" prop="name_kana" class="form-grid-start">
            <el-input v-model="familyForm.name_kana" />
          </el-form-item>
          <el-form-item label="氏名" prop="name" class="form-grid-start">
            <el-input v-model="familyForm.name" />
          </el-form-item>
          <el-form-item label="生年月日" prop="birth_date">
            <el-date-picker
              v-model="familyForm.birth_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="性別" prop="gender">
            <el-select v-model="familyForm.gender" clearable placeholder="選択してください" class="form-control">
              <el-option
                v-for="option in genderOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="国籍" prop="nationality">
            <el-input v-model="familyForm.nationality" />
          </el-form-item>
          <el-form-item label="電話番号" prop="phone">
            <el-input v-model="familyForm.phone" />
          </el-form-item>
          <el-form-item label="郵便番号" prop="postal_code" class="form-grid-start">
            <el-input v-model="familyForm.postal_code" />
          </el-form-item>
          <el-form-item label="住所" prop="address" class="form-grid-full">
            <el-input v-model="familyForm.address" />
          </el-form-item>
          <el-form-item label="マイナンバー" prop="my_number">
            <el-input v-model="familyForm.my_number" />
          </el-form-item>
          <el-form-item label="在留資格" prop="residence_status">
            <el-select
              v-model="familyForm.residence_status"
              clearable
              filterable
              allow-create
              default-first-option
              placeholder="選択してください"
              class="form-control"
            >
              <el-option
                v-for="status in residenceStatusOptions"
                :key="status"
                :label="status"
                :value="status"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="在留カード番号" prop="residence_card_no">
            <el-input v-model="familyForm.residence_card_no" />
          </el-form-item>
          <el-form-item label="在留期限" prop="residence_expiry">
            <el-date-picker
              v-model="familyForm.residence_expiry"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="扶養対象" prop="is_dependent">
            <el-switch v-model="familyForm.is_dependent" active-text="はい" inactive-text="いいえ" />
          </el-form-item>
        </div>
        <el-form-item label="備考" prop="note">
          <el-input v-model="familyForm.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="familyDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="familySubmitting" @click="submitFamilyMember">
          {{ editingFamilyMemberId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
