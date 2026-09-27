<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { listCaseApplicationCategories, listCaseTypeMasters } from '../api/cases'
import { listResidenceStatusMasters, matchCustomers } from '../api/customers'
import { createReception } from '../api/receptions'
import RemoteCompanySelect from '../components/RemoteCompanySelect.vue'
import RemoteStaffSelect from '../components/RemoteStaffSelect.vue'
import { bankAccountTypeOptions, fiscalMonthOptions } from '../constants/options'
import type {
  CaseApplicationCategory,
  CaseTypeMaster,
  CustomerMatchCandidate,
  ReceptionCreatePayload,
  ReceptionFamilyMemberPayload,
  ReceptionPayload,
  ResidenceStatusMaster,
} from '../types/api'

const router = useRouter()
const activeStep = ref(0)
const submitting = ref(false)

// 二重クリック・ネットワーク再試行での重複作成を防ぐための冪等キー。
// このページを開いている間は同じ値を使い回し、確定操作をやり直しても
// 同じ受付として扱われるようにする（ページを再読み込みすれば新しい値になる）。
const receptionRequestId = crypto.randomUUID()

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

// ---- STEP 1: 顧客識別 ----
const identifyForm = ref({
  name: '',
  name_kana: '',
  birth_date: '',
  phone: '',
  email: '',
  residence_card_no: '',
  passport_no: '',
})
const identifyFormRef = ref<FormInstance>()
const identifyRules: FormRules = {
  name: [{ required: true, message: '氏名を入力してください。', trigger: 'blur' }],
  birth_date: [{ required: true, message: '生年月日を入力してください。', trigger: 'change' }],
}

const matching = ref(false)
const matchDone = ref(false)
const candidates = ref<CustomerMatchCandidate[]>([])

// 選択結果： null=未決定, number=既存顧客id, 'new'=新規登録
const customerDecision = ref<number | 'new' | null>(null)
const selectedCandidate = computed(() =>
  typeof customerDecision.value === 'number'
    ? candidates.value.find((c) => c.customer_id === customerDecision.value) ?? null
    : null,
)

const strengthLabel: Record<string, string> = { strong: '強い一致', medium: '中程度の一致', weak: '弱い一致' }
const strengthTag: Record<string, 'danger' | 'warning' | 'info'> = { strong: 'danger', medium: 'warning', weak: 'info' }

const runMatch = async () => {
  const valid = await identifyFormRef.value?.validate().catch(() => false)
  if (!valid) return
  matching.value = true
  try {
    candidates.value = await matchCustomers({
      name: identifyForm.value.name,
      name_kana: identifyForm.value.name_kana,
      birth_date: identifyForm.value.birth_date || null,
      phone: identifyForm.value.phone,
      email: identifyForm.value.email,
      residence_card_number: identifyForm.value.residence_card_no,
      passport_number: identifyForm.value.passport_no,
    })
    matchDone.value = true
    customerDecision.value = null
  } catch {
    ElMessage.error('顧客候補の検索に失敗しました。')
  } finally {
    matching.value = false
  }
}

const useCandidate = (candidate: CustomerMatchCandidate) => {
  customerDecision.value = candidate.customer_id
}
const useNewCustomer = () => {
  customerDecision.value = 'new'
  // 識別フォームの入力を新規顧客フォームへ引き継ぐ
  form.value.customer.name = identifyForm.value.name
  form.value.customer.name_kana = identifyForm.value.name_kana
  form.value.customer.birth_date = identifyForm.value.birth_date
  form.value.customer.phone = identifyForm.value.phone
  form.value.customer.email = identifyForm.value.email
  form.value.customer.residence_card_no = identifyForm.value.residence_card_no
  form.value.customer.passport_no = identifyForm.value.passport_no
}

const goToStep2 = () => {
  if (customerDecision.value === null) {
    ElMessage.warning('既存顧客を使用するか、新規登録を選択してください。')
    return
  }
  activeStep.value = 1
}

// ---- STEP 2: 業務情報 ----
const auth = useAuthStore()
const form = ref<ReceptionPayload>({
  customer: {
    name: '', name_kana: '', birth_date: '', gender: '', nationality: '',
    email: '', phone: '', postal_code: '', address: '', my_number: '',
    residence_status: '', residence_card_no: '', residence_expiry: null,
    passport_no: '', passport_expiry: null, note: '',
  },
  family_members: [],
  company: {
    name: '', name_kana: '', representative_customer: null,
    representative_customer_is_current_customer: true,
    representative_name: '', representative_name_kana: '',
    representative_postal_code: '', representative_address: '',
    corporate_number: '', email: '', phone: '', postal_code: '', address: '',
    fiscal_month: '', establishment_symbol: '', establishment_number: '',
    bank_name: '', bank_branch: '', bank_account_type: '', bank_account_number: '',
  },
  case: {
    case_type_master: null, application_category: null,
    responsible_employee: null, accepted_at: null,
  },
})

const isNewCustomer = computed(() => customerDecision.value === 'new')
const existingCompanyId = ref<number | null>(null)
const existingCompanyName = ref('')
const companyMode = ref<'none' | 'existing' | 'new'>('none')
const showFamilySection = ref(false)

const selectedCaseType = computed(() =>
  caseTypes.value.find((t) => t.id === form.value.case.case_type_master) ?? null,
)
// 案件種別コードから、在留関連フィールドを出すか判定する簡易ルール。
const needsResidenceFields = computed(() => {
  const code = (selectedCaseType.value?.code || '').toLowerCase()
  if (!code) return false
  return !['permanent', 'naturalization', 'company_only'].some((k) => code.includes(k))
    || code.includes('visa') || code.includes('residence') || code.includes('renewal')
})

const step2FormRef = ref<FormInstance>()
const step2Rules: FormRules = {
  'case.case_type_master': [{ required: true, message: '案件種別を選択してください。', trigger: 'change' }],
  'case.application_category': [{ required: true, message: '申請区分を選択してください。', trigger: 'change' }],
}

const createEmptyFamilyMember = (): ReceptionFamilyMemberPayload => ({
  customer: null, relationship: '', name: '', name_kana: '', birth_date: null,
  gender: '', nationality: '', phone: '', postal_code: '', address: '',
  my_number: '', residence_status: '', residence_card_no: '', residence_expiry: null,
  is_dependent: true, note: '',
})
const addFamilyMember = () => form.value.family_members.push(createEmptyFamilyMember())
const removeFamilyMember = (index: number) => form.value.family_members.splice(index, 1)

const goToStep3 = async () => {
  const valid = await step2FormRef.value?.validate().catch(() => false)
  if (!valid) return
  if (companyMode.value === 'existing' && !existingCompanyId.value) {
    ElMessage.warning('関連会社を選択してください。')
    return
  }
  if (companyMode.value === 'new' && !form.value.company.name?.trim()) {
    ElMessage.warning('会社名を入力してください。')
    return
  }
  activeStep.value = 2
}

// ---- STEP 3: 確認・作成 ----
const hasAnyValue = (data: Record<string, unknown>) => (
  Object.values(data).some((v) => v !== '' && v !== null && v !== undefined && v !== false)
)

const buildPayload = (): ReceptionCreatePayload => {
  const payload: ReceptionCreatePayload = {
    request_id: receptionRequestId,
    family_members: form.value.family_members
      .filter((fm) => hasAnyValue(fm as Record<string, unknown>))
      .map((fm) => ({
        ...fm,
        postal_code: fm.postal_code || form.value.customer.postal_code || '',
        address: fm.address || form.value.customer.address || '',
      })),
    company: { ...form.value.company },
    case: {
      case_type_master: form.value.case.case_type_master,
      application_category: form.value.case.application_category,
      responsible_employee: form.value.case.responsible_employee || null,
      accepted_at: form.value.case.accepted_at || null,
    },
  }

  if (isNewCustomer.value) {
    payload.customer = { ...form.value.customer }
  } else {
    payload.existing_customer_id = customerDecision.value as number
  }

  if (companyMode.value === 'existing') {
    payload.existing_company_id = existingCompanyId.value
    payload.company = { ...payload.company, name: '' }
  } else if (companyMode.value === 'none') {
    payload.company = { ...payload.company, name: '' }
  }
  return payload
}

const confirmSummaryLines = computed(() => {
  const lines: string[] = []
  lines.push(isNewCustomer.value
    ? `顧客：新規登録（${form.value.customer.name}）`
    : `顧客：既存を使用（${selectedCandidate.value?.name ?? ''}）`)
  const ct = selectedCaseType.value?.name ?? '-'
  const cat = applicationCategories.value.find((c) => c.id === form.value.case.application_category)?.name ?? '-'
  lines.push(`案件：${ct} / ${cat}`)
  if (companyMode.value === 'new') lines.push(`会社：新規登録（${form.value.company.name}）`)
  if (companyMode.value === 'existing') lines.push(`会社：既存を使用（${existingCompanyName.value || `#${existingCompanyId.value}`}）`)
  if (form.value.family_members.length) lines.push(`家族：${form.value.family_members.length} 名`)
  lines.push('作成内容：案件・Checklist（テンプレート）・タイムライン初期記録')
  return lines
})

const submitReception = async () => {
  try {
    await ElMessageBox.confirm(confirmSummaryLines.value.join('\n'), 'この内容で受付を確定します', {
      confirmButtonText: '確定して案件を作成',
      cancelButtonText: '戻る',
      type: 'info',
    })
  } catch {
    return
  }

  submitting.value = true
  try {
    const result = await createReception(buildPayload())
    if (result.case) {
      ElMessage.success({
        message: `受付完了：${result.case_number}（顧客：${result.customer_reused ? '既存を使用' : '新規登録'}／Checklist ${result.checklist_item_count} 項目）`,
        duration: 5000,
      })
      router.push(`/cases/${result.case}`)
    } else {
      ElMessage.success('顧客情報を登録しました。')
      router.push(`/customers/${result.customer}`)
    }
  } catch (error) {
    const isConflict = (error as { response?: { status?: number } })?.response?.status === 409
    ElMessage.error(
      isConflict
        ? '直前の確定操作をまだ処理中です。少し待ってから画面を更新して確認してください。'
        : '新規受付の登録に失敗しました。入力内容をご確認ください。',
    )
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const [caseTypeData, applicationCategoryData, residenceStatusData] = await Promise.all([
      listCaseTypeMasters({ is_active: true, ordering: 'sort_order' }),
      listCaseApplicationCategories({ is_active: true, ordering: 'sort_order' }),
      listResidenceStatusMasters({ is_active: true, ordering: 'sort_order' }),
    ])
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
    <div class="page-header">
      <h1>新規受付</h1>
    </div>

    <el-steps :active="activeStep" align-center finish-status="success" class="reception-steps">
      <el-step title="顧客識別" description="既存顧客の確認 / 新規登録" />
      <el-step title="業務情報" description="案件種別・担当・関連情報" />
      <el-step title="確認して開始" description="内容確認・案件作成" />
    </el-steps>

    <!-- STEP 1 -->
    <div v-show="activeStep === 0" class="detail-grid">
      <el-card shadow="never">
        <template #header>STEP 1：最低限の情報で既存顧客を確認</template>
        <el-form ref="identifyFormRef" :model="identifyForm" :rules="identifyRules" label-position="top">
          <div class="form-grid">
            <el-form-item label="氏名" prop="name" class="form-grid-start">
              <el-input v-model="identifyForm.name" placeholder="例：李 明" />
            </el-form-item>
            <el-form-item label="フリガナ" prop="name_kana" class="form-grid-start">
              <el-input v-model="identifyForm.name_kana" />
            </el-form-item>
            <el-form-item label="生年月日" prop="birth_date">
              <el-date-picker
                v-model="identifyForm.birth_date"
                type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                placeholder="YYYY-MM-DD" class="form-control"
              />
            </el-form-item>
            <el-form-item label="電話番号（任意）">
              <el-input v-model="identifyForm.phone" />
            </el-form-item>
            <el-form-item label="メール（任意）">
              <el-input v-model="identifyForm.email" />
            </el-form-item>
            <el-form-item label="在留カード番号（任意）">
              <el-input v-model="identifyForm.residence_card_no" />
            </el-form-item>
            <el-form-item label="パスポート番号（任意）">
              <el-input v-model="identifyForm.passport_no" />
            </el-form-item>
          </div>
          <el-button type="primary" :loading="matching" @click="runMatch">既存顧客を照合</el-button>
        </el-form>
      </el-card>

      <el-card v-if="matchDone" shadow="never">
        <template #header>照合結果</template>

        <el-radio-group v-model="customerDecision" class="candidate-list">
          <div
            v-for="candidate in candidates"
            :key="candidate.customer_id"
            class="candidate-card"
            :class="{ 'is-selected': customerDecision === candidate.customer_id }"
          >
            <el-radio :value="candidate.customer_id" class="candidate-radio">
              <div class="candidate-body">
                <div class="candidate-head">
                  <strong>{{ candidate.name }}</strong>
                  <span v-if="candidate.name_kana" class="candidate-sub">{{ candidate.name_kana }}</span>
                  <el-tag size="small" :type="strengthTag[candidate.match_strength]">
                    {{ strengthLabel[candidate.match_strength] }}
                  </el-tag>
                </div>
                <div class="candidate-meta">
                  <span v-if="candidate.birth_date">{{ candidate.birth_date }}</span>
                  <span v-if="candidate.phone">{{ candidate.phone }}</span>
                  <span>案件 {{ candidate.case_count }} 件</span>
                </div>
                <div class="candidate-reason">疑似理由：{{ candidate.match_reason }}</div>
              </div>
            </el-radio>
            <el-button size="small" @click="useCandidate(candidate)">この顧客を使用</el-button>
          </div>

          <div class="candidate-card" :class="{ 'is-selected': customerDecision === 'new' }">
            <el-radio value="new" class="candidate-radio">
              <div class="candidate-body">
                <strong>新規顧客として登録</strong>
                <div class="candidate-reason">
                  {{ candidates.length ? '候補は同一人物ではありません。' : '該当する既存顧客は見つかりませんでした。' }}
                </div>
              </div>
            </el-radio>
            <el-button size="small" type="primary" @click="useNewCustomer">新規登録</el-button>
          </div>
        </el-radio-group>

        <p class="section-optional-note">
          同一人物かどうかの判断は必ず担当者が行ってください。システムが自動で顧客を統合することはありません。
        </p>

        <div class="page-actions">
          <el-button type="primary" @click="goToStep2">次へ（業務情報）</el-button>
        </div>
      </el-card>
    </div>

    <!-- STEP 2 -->
    <div v-show="activeStep === 1" class="detail-grid">
      <el-alert
        v-if="!isNewCustomer && selectedCandidate"
        type="success" :closable="false" show-icon
        :title="`既存顧客を使用：${selectedCandidate.name}（案件 ${selectedCandidate.case_count} 件）`"
      />

      <el-form ref="step2FormRef" :model="form" :rules="step2Rules" label-position="top">
        <el-card shadow="never">
          <template #header>案件情報</template>
          <div class="form-grid">
            <el-form-item label="案件種別" prop="case.case_type_master">
              <el-select v-model="form.case.case_type_master" filterable placeholder="選択してください" class="form-control">
                <el-option v-for="caseType in caseTypes" :key="caseType.id" :label="caseType.name" :value="caseType.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="申請区分" prop="case.application_category">
              <el-select v-model="form.case.application_category" filterable placeholder="選択してください" class="form-control">
                <el-option v-for="c in applicationCategories" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="担当者">
              <RemoteStaffSelect v-model="form.case.responsible_employee" class="form-control" />
              <div v-if="!form.case.responsible_employee" class="field-hint">
                {{ auth.user?.employee_id ? '未選択の場合は自分（ログイン中の担当者）が担当になります。' : '担当者を選択してください（アカウントが担当者に関連付いていません）。' }}
              </div>
            </el-form-item>
            <el-form-item label="受任日">
              <el-date-picker
                v-model="form.case.accepted_at"
                type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                placeholder="YYYY-MM-DD" class="form-control"
              />
            </el-form-item>
          </div>
        </el-card>

        <el-card v-if="isNewCustomer" shadow="never">
          <template #header>新規顧客の詳細</template>
          <div class="form-grid">
            <el-form-item label="氏名" class="form-grid-start">
              <el-input v-model="form.customer.name" />
            </el-form-item>
            <el-form-item label="フリガナ" class="form-grid-start">
              <el-input v-model="form.customer.name_kana" />
            </el-form-item>
            <el-form-item label="生年月日">
              <el-date-picker
                v-model="form.customer.birth_date"
                type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                placeholder="YYYY-MM-DD" class="form-control"
              />
            </el-form-item>
            <el-form-item label="性別">
              <el-select v-model="form.customer.gender" clearable placeholder="選択してください" class="form-control">
                <el-option v-for="g in genderOptions" :key="g.value" :label="g.label" :value="g.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="国籍"><el-input v-model="form.customer.nationality" /></el-form-item>
            <el-form-item label="電話番号"><el-input v-model="form.customer.phone" /></el-form-item>
            <el-form-item label="メール"><el-input v-model="form.customer.email" /></el-form-item>
            <el-form-item label="郵便番号" class="form-grid-start"><el-input v-model="form.customer.postal_code" /></el-form-item>
            <el-form-item label="住所" class="form-grid-full"><el-input v-model="form.customer.address" /></el-form-item>
          </div>
          <template v-if="needsResidenceFields">
            <div class="form-section-title">在留情報</div>
            <div class="form-grid">
              <el-form-item label="在留資格">
                <el-select
                  v-model="form.customer.residence_status" clearable filterable allow-create
                  default-first-option placeholder="選択してください" class="form-control"
                >
                  <el-option v-for="s in residenceStatusOptions" :key="s.id" :label="s.name" :value="s.name" />
                </el-select>
              </el-form-item>
              <el-form-item label="在留カード番号"><el-input v-model="form.customer.residence_card_no" /></el-form-item>
              <el-form-item label="在留期限">
                <el-date-picker
                  v-model="form.customer.residence_expiry"
                  type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                  placeholder="YYYY-MM-DD" class="form-control"
                />
              </el-form-item>
              <el-form-item label="パスポート番号"><el-input v-model="form.customer.passport_no" /></el-form-item>
              <el-form-item label="パスポート期限">
                <el-date-picker
                  v-model="form.customer.passport_expiry"
                  type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                  placeholder="YYYY-MM-DD" class="form-control"
                />
              </el-form-item>
            </div>
          </template>
        </el-card>

        <el-card shadow="never">
          <template #header>関連会社（任意）</template>
          <el-radio-group v-model="companyMode">
            <el-radio value="none">なし</el-radio>
            <el-radio value="existing">既存の会社</el-radio>
            <el-radio value="new">新規登録</el-radio>
          </el-radio-group>
          <div v-if="companyMode === 'existing'" style="margin-top: 12px;">
            <RemoteCompanySelect
              v-model="existingCompanyId"
              class="form-control"
              @change="(row) => { existingCompanyName = row?.name ?? '' }"
            />
          </div>
          <div v-if="companyMode === 'new'" class="form-grid" style="margin-top: 12px;">
            <el-form-item label="会社名" class="form-grid-start"><el-input v-model="form.company.name" /></el-form-item>
            <el-form-item label="会社名フリガナ" class="form-grid-start"><el-input v-model="form.company.name_kana" /></el-form-item>
            <el-form-item label="代表者を今回の顧客にする">
              <el-switch v-model="form.company.representative_customer_is_current_customer" active-text="はい" inactive-text="いいえ" />
            </el-form-item>
            <el-form-item label="決算月">
              <el-select v-model="form.company.fiscal_month" clearable placeholder="選択してください" class="form-control">
                <el-option v-for="m in fiscalMonthOptions" :key="m" :label="`${m}月`" :value="m" />
              </el-select>
            </el-form-item>
            <el-form-item label="法人番号"><el-input v-model="form.company.corporate_number" /></el-form-item>
            <el-form-item label="電話番号"><el-input v-model="form.company.phone" /></el-form-item>
            <el-form-item label="住所" class="form-grid-full"><el-input v-model="form.company.address" /></el-form-item>
            <el-form-item label="銀行名"><el-input v-model="form.company.bank_name" /></el-form-item>
            <el-form-item label="支店名"><el-input v-model="form.company.bank_branch" /></el-form-item>
            <el-form-item label="預金種別">
              <el-select v-model="form.company.bank_account_type" clearable placeholder="選択してください" class="form-control">
                <el-option v-for="t in bankAccountTypeOptions" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
            <el-form-item label="口座番号"><el-input v-model="form.company.bank_account_number" /></el-form-item>
          </div>
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="card-header-row">
              <span>家族情報（任意）</span>
              <el-button v-if="!showFamilySection" text type="primary" @click="showFamilySection = true">追加する</el-button>
            </div>
          </template>
          <p v-if="!showFamilySection" class="section-optional-note">家族滞在など、家族が関係する案件の場合のみ入力してください。</p>
          <template v-else>
            <el-button type="primary" @click="addFamilyMember">家族を追加</el-button>
            <p v-if="!form.family_members.length" class="empty-text">まだ追加されていません。</p>
            <div v-for="(fm, index) in form.family_members" :key="index" class="inline-form-section">
              <div class="card-header-row inline-form-header">
                <strong>家族 {{ index + 1 }}</strong>
                <el-button text type="danger" @click="removeFamilyMember(index)">削除</el-button>
              </div>
              <div class="form-grid">
                <el-form-item label="関係">
                  <el-select v-model="fm.relationship" clearable placeholder="選択" class="form-control">
                    <el-option v-for="r in relationshipOptions" :key="r.value" :label="r.label" :value="r.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="扶養対象">
                  <el-switch v-model="fm.is_dependent" active-text="はい" inactive-text="いいえ" />
                </el-form-item>
                <el-form-item label="氏名" class="form-grid-start"><el-input v-model="fm.name" /></el-form-item>
                <el-form-item label="フリガナ" class="form-grid-start"><el-input v-model="fm.name_kana" /></el-form-item>
                <el-form-item label="生年月日">
                  <el-date-picker
                    v-model="fm.birth_date"
                    type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                    placeholder="YYYY-MM-DD" class="form-control"
                  />
                </el-form-item>
              </div>
            </div>
          </template>
        </el-card>
      </el-form>

      <div class="page-actions">
        <el-button @click="activeStep = 0">戻る</el-button>
        <el-button type="primary" @click="goToStep3">次へ（確認）</el-button>
      </div>
    </div>

    <!-- STEP 3 -->
    <div v-show="activeStep === 2" class="detail-grid">
      <el-card shadow="never">
        <template #header>STEP 3：内容確認</template>
        <ul class="confirm-list">
          <li v-for="(line, index) in confirmSummaryLines" :key="index">{{ line }}</li>
        </ul>
        <p class="section-optional-note">
          「確定」を押すと、顧客の作成／紐付け・案件・Checklist・タイムラインが1つの処理でまとめて作成され、
          そのまま案件ワークスペースへ移動します。
        </p>
      </el-card>
      <div class="page-actions">
        <el-button @click="activeStep = 1">戻る</el-button>
        <el-button type="primary" :loading="submitting" @click="submitReception">確定して案件を作成</el-button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.reception-steps {
  margin: 8px 0 20px;
}

.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.candidate-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: var(--el-border-radius-base);
  padding: 12px 14px;
}

.candidate-card.is-selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.candidate-radio {
  height: auto;
  align-items: flex-start;
  white-space: normal;
}

.candidate-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.candidate-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.candidate-sub,
.candidate-meta,
.candidate-reason {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.candidate-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.confirm-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.9;
}
</style>
