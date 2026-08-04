<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { listEmployees } from '../api/employees'
import { listCustomers, listResidenceStatusMasters } from '../api/customers'
import { listCaseApplicationCategories, listCaseTypeMasters } from '../api/cases'
import { createReception } from '../api/receptions'
import { bankAccountTypeOptions, fiscalMonthOptions } from '../constants/options'
import type {
  CaseApplicationCategory,
  CaseTypeMaster,
  Employee,
  Customer,
  ReceptionCompanyPayload,
  ReceptionFamilyMemberPayload,
  ReceptionPayload,
  ResidenceStatusMaster,
} from '../types/api'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)
const employees = ref<Employee[]>([])
const customers = ref<Customer[]>([])
const caseTypes = ref<CaseTypeMaster[]>([])
const applicationCategories = ref<CaseApplicationCategory[]>([])
const residenceStatusOptions = ref<ResidenceStatusMaster[]>([])

const genderOptions = [
  { label: '男性', value: 'male' },
  { label: '女性', value: 'female' },
  { label: 'その他', value: 'other' },
]
const relationshipOptions = [
  { label: '配偶者', value: 'spouse' },
  { label: '子', value: 'child' },
  { label: '父', value: 'father' },
  { label: '母', value: 'mother' },
  { label: '兄弟姉妹', value: 'sibling' },
  { label: 'その他', value: 'other' },
]

const form = ref<ReceptionPayload>({
  customer: {
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
  },
  family_members: [],
  company: {
    name: '',
    name_kana: '',
    representative_customer: null,
    representative_customer_is_current_customer: true,
    representative_name: '',
    representative_name_kana: '',
    corporate_number: '',
    email: '',
    phone: '',
    postal_code: '',
    address: '',
    fiscal_month: '',
    bank_name: '',
    bank_branch: '',
    bank_account_type: '',
    bank_account_number: '',
  },
  case: {
    case_type_master: null,
    application_category: null,
    responsible_employee: null,
    accepted_at: null,
  },
})

const rules: FormRules<ReceptionPayload> = {
  'customer.name': [{ required: true, message: '氏名を入力してください。', trigger: 'blur' }],
  'customer.birth_date': [{ required: true, message: '生年月日を入力してください。', trigger: 'change' }],
}

const hasAnyValue = (data: Record<string, unknown>) => (
  Object.values(data).some((value) => value !== '' && value !== null && value !== undefined && value !== false)
)

const getCorporateRegistrationNumber = (corporateNumber?: string) => {
  if (corporateNumber && /^\d{13}$/.test(corporateNumber)) {
    return corporateNumber.slice(1)
  }
  return '自動生成'
}

const createEmptyFamilyMember = (): ReceptionFamilyMemberPayload => ({
  customer: null,
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

const addFamilyMember = () => {
  form.value.family_members.push(createEmptyFamilyMember())
}

const removeFamilyMember = (index: number) => {
  form.value.family_members.splice(index, 1)
}

const validateCompany = () => {
  const company = form.value.company as ReceptionCompanyPayload
  const companyFields = {
    ...company,
    representative_customer_is_current_customer: false,
  }
  if (hasAnyValue(companyFields as Record<string, unknown>) && !company.name?.trim()) {
    ElMessage.error('会社情報を入力する場合は会社名が必須です。')
    return false
  }
  return true
}

const validateFamilyMembers = () => {
  const invalid = form.value.family_members.some((familyMember) => (
    !familyMember.customer
    && hasAnyValue(familyMember as Record<string, unknown>)
    && !familyMember.name?.trim()
  ))
  if (invalid) {
    ElMessage.error('家族情報を入力する場合は、既存の顧客を選択するか氏名を入力してください。')
    return false
  }
  return true
}

const validateCase = () => {
  const hasCaseType = Boolean(form.value.case.case_type_master)
  const hasApplicationCategory = Boolean(form.value.case.application_category)
  if (hasCaseType !== hasApplicationCategory) {
    ElMessage.error('案件を作成する場合は案件種別と申請区分の両方を選択してください。')
    return false
  }
  return true
}

const buildPayload = (): ReceptionPayload => {
  const familyMembers = form.value.family_members
    .filter((familyMember) => hasAnyValue(familyMember as Record<string, unknown>))
    .map((familyMember) => ({
      ...familyMember,
      postal_code: familyMember.postal_code || form.value.customer.postal_code || '',
      address: familyMember.address || form.value.customer.address || '',
    }))

  const company = { ...form.value.company }
  if (company.representative_customer_is_current_customer) {
    company.representative_customer = null
    company.representative_name = ''
    company.representative_name_kana = ''
  }

  return {
    ...form.value,
    family_members: familyMembers,
    company,
    case: {
      ...form.value.case,
      responsible_employee: form.value.case.responsible_employee || null,
      accepted_at: form.value.case.accepted_at || null,
    },
  }
}

const submitReception = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid || !validateCompany() || !validateFamilyMembers() || !validateCase()) return

  submitting.value = true
  try {
    const result = await createReception(buildPayload())
    if (result.case) {
      ElMessage.success(`案件を作成しました。${result.case_number}`)
      router.push(`/cases/${result.case}`)
    } else {
      ElMessage.success('顧客情報を登録しました。')
      router.push(`/customers/${result.customer}`)
    }
  } catch {
    ElMessage.error('新規受付の登録に失敗しました。')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const [employeeData, customerData, caseTypeData, applicationCategoryData, residenceStatusData] = await Promise.all([
      listEmployees(),
      listCustomers(),
      listCaseTypeMasters({ is_active: true, ordering: 'sort_order' }),
      listCaseApplicationCategories({ is_active: true, ordering: 'sort_order' }),
      listResidenceStatusMasters({ is_active: true, ordering: 'sort_order' }),
    ])
    employees.value = employeeData.results
    customers.value = customerData.results
    caseTypes.value = caseTypeData.results
    applicationCategories.value = applicationCategoryData.results
    residenceStatusOptions.value = residenceStatusData.results
  } catch {
    ElMessage.error('選択肢の取得に失敗しました。')
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>新規受付</h1>
      <el-button type="primary" :loading="submitting" @click="submitReception">登録</el-button>
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <div class="detail-grid">
        <el-card shadow="never">
          <template #header>顧客情報</template>
          <div class="form-grid">
            <el-form-item label="フリガナ" prop="customer.name_kana" class="form-grid-start">
              <el-input v-model="form.customer.name_kana" />
            </el-form-item>
            <el-form-item label="氏名" prop="customer.name" class="form-grid-start">
              <el-input v-model="form.customer.name" />
            </el-form-item>
            <el-form-item label="生年月日" prop="customer.birth_date">
              <el-date-picker
                v-model="form.customer.birth_date"
                type="date"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                placeholder="YYYY-MM-DD"
                class="form-control"
              />
            </el-form-item>
            <el-form-item label="性別" prop="customer.gender">
              <el-select v-model="form.customer.gender" clearable placeholder="選択してください" class="form-control">
                <el-option v-for="gender in genderOptions" :key="gender.value" :label="gender.label" :value="gender.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="国籍" prop="customer.nationality">
              <el-input v-model="form.customer.nationality" />
            </el-form-item>
            <el-form-item label="メール" prop="customer.email">
              <el-input v-model="form.customer.email" />
            </el-form-item>
            <el-form-item label="電話番号" prop="customer.phone">
              <el-input v-model="form.customer.phone" />
            </el-form-item>
            <el-form-item label="郵便番号" prop="customer.postal_code" class="form-grid-start">
              <el-input v-model="form.customer.postal_code" />
            </el-form-item>
            <el-form-item label="住所" prop="customer.address" class="form-grid-full">
              <el-input v-model="form.customer.address" />
            </el-form-item>
            <el-form-item label="マイナンバー" prop="customer.my_number">
              <el-input v-model="form.customer.my_number" />
            </el-form-item>
            <el-form-item label="在留資格" prop="customer.residence_status">
              <el-select
                v-model="form.customer.residence_status"
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
            <el-form-item label="在留カード番号" prop="customer.residence_card_no">
              <el-input v-model="form.customer.residence_card_no" />
            </el-form-item>
            <el-form-item label="在留期限" prop="customer.residence_expiry">
              <el-date-picker
                v-model="form.customer.residence_expiry"
                type="date"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                placeholder="YYYY-MM-DD"
                class="form-control"
              />
            </el-form-item>
            <el-form-item label="パスポート番号" prop="customer.passport_no">
              <el-input v-model="form.customer.passport_no" />
            </el-form-item>
            <el-form-item label="パスポート期限" prop="customer.passport_expiry">
              <el-date-picker
                v-model="form.customer.passport_expiry"
                type="date"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                placeholder="YYYY-MM-DD"
                class="form-control"
              />
            </el-form-item>
          </div>
          <el-form-item label="備考" prop="customer.note">
            <el-input v-model="form.customer.note" type="textarea" :rows="3" />
          </el-form-item>
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="card-header-row">
              <span>家族情報</span>
              <el-button type="primary" @click="addFamilyMember">家族を追加</el-button>
            </div>
          </template>

          <p v-if="!form.family_members.length" class="empty-text">該当データなし</p>
          <div v-for="(familyMember, index) in form.family_members" :key="index" class="inline-form-section">
            <div class="card-header-row inline-form-header">
              <strong>家族 {{ index + 1 }}</strong>
              <el-button text type="danger" @click="removeFamilyMember(index)">削除</el-button>
            </div>
            <div class="form-grid">
              <el-form-item label="関係">
                <el-select v-model="familyMember.relationship" clearable placeholder="選択してください" class="form-control">
                  <el-option
                    v-for="relationship in relationshipOptions"
                    :key="relationship.value"
                    :label="relationship.label"
                    :value="relationship.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="扶養対象">
                <el-switch v-model="familyMember.is_dependent" active-text="はい" inactive-text="いいえ" />
              </el-form-item>
              <el-form-item label="既存の顧客から選択" class="form-grid-full">
                <el-select
                  v-model="familyMember.customer"
                  clearable
                  filterable
                  placeholder="既に顧客として登録済みの場合はここで選択（未選択なら下で新規登録）"
                  class="form-control"
                >
                  <el-option v-for="option in customers" :key="option.id" :label="option.name" :value="option.id" />
                </el-select>
              </el-form-item>
            </div>

            <template v-if="!familyMember.customer">
              <p class="section-optional-note">既存の顧客に該当しない場合は、新しい人物として以下を入力してください。</p>
              <div class="form-grid">
                <el-form-item label="フリガナ" class="form-grid-start">
                  <el-input v-model="familyMember.name_kana" />
                </el-form-item>
                <el-form-item label="氏名" class="form-grid-start">
                  <el-input v-model="familyMember.name" />
                </el-form-item>
                <el-form-item label="生年月日">
                  <el-date-picker
                    v-model="familyMember.birth_date"
                    type="date"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    placeholder="YYYY-MM-DD"
                    class="form-control"
                  />
                </el-form-item>
                <el-form-item label="性別">
                  <el-select v-model="familyMember.gender" clearable placeholder="選択してください" class="form-control">
                    <el-option v-for="gender in genderOptions" :key="gender.value" :label="gender.label" :value="gender.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="国籍">
                  <el-input v-model="familyMember.nationality" />
                </el-form-item>
                <el-form-item label="電話番号">
                  <el-input v-model="familyMember.phone" />
                </el-form-item>
                <el-form-item label="郵便番号" class="form-grid-start">
                  <el-input v-model="familyMember.postal_code" />
                </el-form-item>
                <el-form-item label="住所" class="form-grid-full">
                  <el-input v-model="familyMember.address" />
                </el-form-item>
                <el-form-item label="マイナンバー">
                  <el-input v-model="familyMember.my_number" />
                </el-form-item>
                <el-form-item label="在留資格">
                  <el-select
                    v-model="familyMember.residence_status"
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
                <el-form-item label="在留カード番号">
                  <el-input v-model="familyMember.residence_card_no" />
                </el-form-item>
                <el-form-item label="在留期限">
                  <el-date-picker
                    v-model="familyMember.residence_expiry"
                    type="date"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    placeholder="YYYY-MM-DD"
                    class="form-control"
                  />
                </el-form-item>
              </div>
            </template>
            <el-form-item label="備考">
              <el-input v-model="familyMember.note" type="textarea" :rows="2" />
            </el-form-item>
          </div>
        </el-card>

        <el-card shadow="never">
          <template #header>会社情報</template>
          <div class="form-grid">
            <el-form-item label="会社名フリガナ" prop="company.name_kana" class="form-grid-start">
              <el-input v-model="form.company.name_kana" />
            </el-form-item>
            <el-form-item label="会社名" prop="company.name" class="form-grid-start">
              <el-input v-model="form.company.name" />
            </el-form-item>
            <el-form-item label="代表者を今回の顧客にする" prop="company.representative_customer_is_current_customer">
              <el-switch
                v-model="form.company.representative_customer_is_current_customer"
                active-text="はい"
                inactive-text="いいえ"
              />
            </el-form-item>
            <el-form-item
              v-if="!form.company.representative_customer_is_current_customer"
              label="代表者顧客"
              prop="company.representative_customer"
            >
              <el-select
                v-model="form.company.representative_customer"
                clearable
                placeholder="未設定"
                class="form-control"
              >
                <el-option
                  v-for="customer in customers"
                  :key="customer.id"
                  :label="customer.name"
                  :value="customer.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item
              v-if="!form.company.representative_customer_is_current_customer"
              label="代表者フリガナ"
              prop="company.representative_name_kana"
              class="form-grid-start"
            >
              <el-input v-model="form.company.representative_name_kana" />
            </el-form-item>
            <el-form-item
              v-if="!form.company.representative_customer_is_current_customer"
              label="代表者氏名"
              prop="company.representative_name"
              class="form-grid-start"
            >
              <el-input v-model="form.company.representative_name" />
            </el-form-item>
            <el-form-item label="法人番号" prop="company.corporate_number">
              <el-input v-model="form.company.corporate_number" />
            </el-form-item>
            <el-form-item label="会社法人等番号">
              <el-input :model-value="getCorporateRegistrationNumber(form.company.corporate_number)" disabled />
            </el-form-item>
            <el-form-item label="メール" prop="company.email">
              <el-input v-model="form.company.email" />
            </el-form-item>
            <el-form-item label="電話番号" prop="company.phone">
              <el-input v-model="form.company.phone" />
            </el-form-item>
            <el-form-item label="郵便番号" prop="company.postal_code" class="form-grid-start">
              <el-input v-model="form.company.postal_code" />
            </el-form-item>
            <el-form-item label="住所" prop="company.address" class="form-grid-full">
              <el-input v-model="form.company.address" />
            </el-form-item>
            <el-form-item label="決算月" prop="company.fiscal_month">
              <el-select v-model="form.company.fiscal_month" clearable placeholder="選択してください" class="form-control">
                <el-option
                  v-for="month in fiscalMonthOptions"
                  :key="month"
                  :label="`${month}月`"
                  :value="month"
                />
              </el-select>
            </el-form-item>
            <div class="form-section-title">銀行情報</div>
            <el-form-item label="銀行名" prop="company.bank_name">
              <el-input v-model="form.company.bank_name" />
            </el-form-item>
            <el-form-item label="支店名" prop="company.bank_branch">
              <el-input v-model="form.company.bank_branch" />
            </el-form-item>
            <el-form-item label="預金種別" prop="company.bank_account_type">
              <el-select v-model="form.company.bank_account_type" clearable placeholder="選択してください" class="form-control">
                <el-option
                  v-for="type in bankAccountTypeOptions"
                  :key="type"
                  :label="type"
                  :value="type"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="口座番号" prop="company.bank_account_number">
              <el-input v-model="form.company.bank_account_number" />
            </el-form-item>
          </div>
        </el-card>

        <el-card shadow="never">
          <template #header>案件情報</template>
          <p class="section-optional-note">まだ案件化しない場合は空欄のままで構いません。顧客情報だけ登録されます。</p>
          <div class="form-grid">
            <el-form-item label="案件番号">
              <el-input model-value="自動生成" disabled />
            </el-form-item>
            <el-form-item label="案件種別" prop="case.case_type_master">
              <el-select
                v-model="form.case.case_type_master"
                filterable
                placeholder="選択してください"
                class="form-control"
              >
                <el-option
                  v-for="caseType in caseTypes"
                  :key="caseType.id"
                  :label="caseType.name"
                  :value="caseType.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="申請区分" prop="case.application_category">
              <el-select
                v-model="form.case.application_category"
                filterable
                placeholder="選択してください"
                class="form-control"
              >
                <el-option
                  v-for="category in applicationCategories"
                  :key="category.id"
                  :label="category.name"
                  :value="category.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="担当者" prop="case.responsible_employee">
              <el-select v-model="form.case.responsible_employee" clearable filterable placeholder="選択してください" class="form-control">
                <el-option label="未設定" value="" />
                <el-option
                  v-for="employee in employees"
                  :key="employee.id"
                  :label="employee.name"
                  :value="employee.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="受任日" prop="case.accepted_at">
              <el-date-picker
                v-model="form.case.accepted_at"
                type="date"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                placeholder="YYYY-MM-DD"
                class="form-control"
              />
            </el-form-item>
          </div>
        </el-card>
      </div>

      <div class="page-actions">
        <el-button @click="router.push('/dashboard')">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitReception">登録</el-button>
      </div>
    </el-form>
  </section>
</template>
