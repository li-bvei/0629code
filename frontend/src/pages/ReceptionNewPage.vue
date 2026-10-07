<script setup lang="ts">
// 新規受付：業務情報を直接入力して確認・作成する（既存顧客の照合ステップは無い）。
// P4：案件種別ごとの業務フロー（入管以外は申請区分なし）、関連元の案件（任意）、サービス項目（参考・任意・複数）。
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { listCaseApplicationCategories, listCaseTypeMasters } from '../api/cases'
import { listResidenceStatusMasters } from '../api/customers'
import { createReception } from '../api/receptions'
import RemoteCaseSelect from '../components/RemoteCaseSelect.vue'
import RemoteCompanySelect from '../components/RemoteCompanySelect.vue'
import RemoteStaffSelect from '../components/RemoteStaffSelect.vue'
import ServiceItemPicker from '../components/services/ServiceItemPicker.vue'
import type { ServiceItem } from '../types/accounting'
import { needsApplicationCategory } from '../utils/caseWorkflow'
import { serviceSummary } from '../utils/serviceItems'
import { bankAccountTypeOptions, fiscalMonthOptions } from '../constants/options'
import type {
  CaseApplicationCategory,
  CaseTypeMaster,
  ReceptionFamilyMemberPayload,
  ReceptionPayload,
  ResidenceStatusMaster,
} from '../types/api'
import { responseOf } from '../utils/apiErrors'
import { buildReceptionPayload, receptionErrorView } from '../utils/reception'
import type { ReceptionCompanyMode } from '../utils/reception'

const router = useRouter()
const auth = useAuthStore()
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

// ---- STEP 1: 業務情報 ----
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

const existingCompanyId = ref<number | null>(null)
const existingCompanyName = ref('')
const companyMode = ref<ReceptionCompanyMode>('none')
const showFamilySection = ref(false)
const responsibleName = ref('')

// アカウントが担当者（Employee）に関連付いていない場合、「未選択なら自分が担当」は成立しない。
// その場合は担当者の選択を必須にする（未割当の案件は作らない。判定は後端も同じ）。
const hasOwnEmployee = computed(() => Boolean(auth.user?.employee_id))
const canAssignOthers = auth.can('cases.case_change_all')

const selectedCaseType = computed(() =>
  caseTypes.value.find((t) => t.id === form.value.case.case_type_master) ?? null,
)
// P4：入管以外の種別（税理士委託・会社解散・手続など）は申請区分なし。種別の業務フローの段階だけが作られる
const requiresCategory = computed(() => needsApplicationCategory(selectedCaseType.value))
watch(requiresCategory, (required) => {
  if (!required) form.value.case.application_category = null
})

// P4：関連元の案件（任意）とサービス項目（参考・任意・複数）
const parentCaseLabel = ref('')
const canPickServices = auth.can('accounting.use_service_item')
interface ServiceSelection { item: ServiceItem; quantity: number }
const serviceSelections = ref<ServiceSelection[]>([])
const addService = (item: ServiceItem) => {
  const existing = serviceSelections.value.find((row) => row.item.id === item.id)
  if (existing) existing.quantity += 1
  else serviceSelections.value.push({ item, quantity: 1 })
}
const removeService = (index: number) => serviceSelections.value.splice(index, 1)
const serviceText = (item: ServiceItem) => serviceSummary({
  default_price: item.default_price === null ? null : Number(item.default_price), price_type: item.price_type, unit: item.unit,
})
// 案件種別コードから、在留関連フィールドを出すか判定する簡易ルール。
const needsResidenceFields = computed(() => {
  const code = (selectedCaseType.value?.code || '').toLowerCase()
  if (!code) return false
  return !['permanent', 'naturalization', 'company_only'].some((k) => code.includes(k))
    || code.includes('visa') || code.includes('residence') || code.includes('renewal')
})

const formRef = ref<FormInstance>()
const rules = computed<FormRules>(() => ({
  'customer.name': [{ required: true, whitespace: true, message: '氏名を入力してください。', trigger: 'blur' }],
  'customer.birth_date': [{ required: true, message: '生年月日を入力してください。', trigger: 'change' }],
  'case.case_type_master': [{ required: true, message: '案件種別を選択してください。', trigger: 'change' }],
  'case.application_category': requiresCategory.value
    ? [{ required: true, message: '申請区分を選択してください。', trigger: 'change' }]
    : [],
  'case.responsible_employee': hasOwnEmployee.value
    ? []
    : [{ required: true, message: '担当者を選択してください。', trigger: 'change' }],
}))

// 後端の 400（項目ごとの理由）。上部の要約と各入力欄の下の両方に、後端の文言をそのまま出す。
const errorLines = ref<string[]>([])
const fieldErrors = ref<Record<string, string>>({})
const clearServerErrors = () => {
  errorLines.value = []
  fieldErrors.value = {}
}

const createEmptyFamilyMember = (): ReceptionFamilyMemberPayload => ({
  customer: null, relationship: '', name: '', name_kana: '', birth_date: null,
  gender: '', nationality: '', phone: '', postal_code: '', address: '',
  my_number: '', residence_status: '', residence_card_no: '', residence_expiry: null,
  is_dependent: true, note: '',
})
const addFamilyMember = () => form.value.family_members.push(createEmptyFamilyMember())
const removeFamilyMember = (index: number) => form.value.family_members.splice(index, 1)

const goToConfirm = async () => {
  clearServerErrors()
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    ElMessage.warning('未入力の必須項目があります。赤字の項目をご確認ください。')
    return
  }
  if (companyMode.value === 'existing' && !existingCompanyId.value) {
    ElMessage.warning('関連会社を選択してください。')
    return
  }
  if (companyMode.value === 'new' && !form.value.company.name?.trim()) {
    ElMessage.warning('会社名を入力してください。')
    return
  }
  activeStep.value = 1
}

// ---- STEP 2: 確認・作成 ----
const confirmSummaryLines = computed(() => {
  const lines: string[] = []
  lines.push(`顧客：${form.value.customer.name}（生年月日 ${form.value.customer.birth_date || '-'}）を新規登録`)
  const ct = selectedCaseType.value?.name ?? '-'
  const cat = applicationCategories.value.find((c) => c.id === form.value.case.application_category)?.name ?? '-'
  lines.push(requiresCategory.value ? `案件：${ct} / ${cat}` : `案件：${ct}`)
  if (selectedCaseType.value?.workflow_template_name) lines.push(`業務フロー：${selectedCaseType.value.workflow_template_name}`)
  if (form.value.case.parent_case) lines.push(`関連元の案件：${parentCaseLabel.value || `#${form.value.case.parent_case}`}`)
  if (serviceSelections.value.length) {
    lines.push(`サービス項目（参考）：${serviceSelections.value.map((row) => `${row.item.name}×${row.quantity}`).join('、')}`)
  }
  lines.push(`担当者：${form.value.case.responsible_employee ? (responsibleName.value || '選択した担当者') : '自分（ログイン中の担当者）'}`)
  if (form.value.case.accepted_at) lines.push(`受任日：${form.value.case.accepted_at}`)
  if (companyMode.value === 'new') lines.push(`会社：新規登録（${form.value.company.name}）`)
  if (companyMode.value === 'existing') lines.push(`会社：既存を使用（${existingCompanyName.value || `#${existingCompanyId.value}`}）`)
  if (form.value.family_members.length) lines.push(`家族：${form.value.family_members.length} 名`)
  lines.push('作成内容：顧客・案件・Checklist（テンプレート）・タイムライン初期記録')
  return lines
})

const showErrors = async (data: unknown) => {
  const view = receptionErrorView(data)
  errorLines.value = view.lines.length ? view.lines : ['入力内容を確認できませんでした。もう一度お試しください。']
  fieldErrors.value = view.fields
  activeStep.value = 0
  await nextTick()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const submitReception = async () => {
  clearServerErrors()
  submitting.value = true
  try {
    const result = await createReception(buildReceptionPayload(form.value, {
      requestId: receptionRequestId, companyMode: companyMode.value, existingCompanyId: existingCompanyId.value,
      requiresCategory: requiresCategory.value,
      serviceItems: serviceSelections.value.map((row) => ({ service_item: row.item.id, quantity: row.quantity })),
    }))
    if (result.case) {
      ElMessage.success({
        message: `受付完了：${result.case_number}（Checklist ${result.checklist_item_count} 項目）`,
        duration: 5000,
      })
      router.push(`/cases/${result.case}`)
    } else {
      ElMessage.success('顧客情報を登録しました。')
      router.push(`/customers/${result.customer}`)
    }
  } catch (error) {
    const { status, data } = responseOf(error)
    if (status === 409) {
      ElMessage.error('直前の確定操作をまだ処理中です。少し待ってから画面を更新して確認してください。')
    } else if (status === 400 || status === 403) {
      // 後端が返した理由（どの項目が・なぜ）をそのまま表示する
      await showErrors(data)
    } else {
      ElMessage.error('新規受付を登録できませんでした。通信状況を確認して、もう一度お試しください。')
    }
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
      <el-step title="業務情報" description="顧客・案件種別・担当・関連情報" />
      <el-step title="確認して作成" description="内容確認・案件作成" />
    </el-steps>

    <el-alert v-if="errorLines.length" type="error" :closable="false" show-icon class="page-alert"
              title="登録できませんでした。次の項目をご確認ください。">
      <ul class="error-list">
        <li v-for="(line, index) in errorLines" :key="index">{{ line }}</li>
      </ul>
    </el-alert>

    <!-- STEP 1 -->
    <div v-show="activeStep === 0" class="detail-grid">
      <el-alert v-if="!hasOwnEmployee" type="warning" :closable="false" show-icon
                title="このアカウントは担当者に関連付いていないため、案件の担当者を必ず選択してください。">
        <div v-if="!canAssignOthers">
          他の担当者を指定する権限がない場合は登録できません。管理者にアカウントと担当者の関連付けを依頼してください。
        </div>
      </el-alert>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-card shadow="never">
          <template #header>顧客情報</template>
          <div class="form-grid">
            <el-form-item label="氏名" prop="customer.name" :error="fieldErrors['customer.name']" class="form-grid-start">
              <el-input v-model="form.customer.name" placeholder="例：李 明" />
            </el-form-item>
            <el-form-item label="フリガナ" prop="customer.name_kana" :error="fieldErrors['customer.name_kana']" class="form-grid-start">
              <el-input v-model="form.customer.name_kana" />
            </el-form-item>
            <el-form-item label="生年月日" prop="customer.birth_date" :error="fieldErrors['customer.birth_date']">
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
            <el-form-item label="電話番号" :error="fieldErrors['customer.phone']"><el-input v-model="form.customer.phone" /></el-form-item>
            <el-form-item label="メール" :error="fieldErrors['customer.email']"><el-input v-model="form.customer.email" /></el-form-item>
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
              <el-form-item label="在留期限" :error="fieldErrors['customer.residence_expiry']">
                <el-date-picker
                  v-model="form.customer.residence_expiry"
                  type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                  placeholder="YYYY-MM-DD" class="form-control"
                />
              </el-form-item>
              <el-form-item label="パスポート番号"><el-input v-model="form.customer.passport_no" /></el-form-item>
              <el-form-item label="パスポート期限" :error="fieldErrors['customer.passport_expiry']">
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
          <template #header>案件情報</template>
          <div class="form-grid">
            <el-form-item label="案件種別" prop="case.case_type_master" :error="fieldErrors['case.case_type_master'] || fieldErrors['case']">
              <el-select v-model="form.case.case_type_master" filterable placeholder="選択してください" class="form-control">
                <el-option v-for="caseType in caseTypes" :key="caseType.id" :label="caseType.name" :value="caseType.id" />
              </el-select>
            </el-form-item>
            <el-form-item v-if="requiresCategory" label="申請区分" prop="case.application_category" :error="fieldErrors['case.application_category']">
              <el-select v-model="form.case.application_category" filterable placeholder="選択してください" class="form-control">
                <el-option v-for="c in applicationCategories" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
            <el-form-item v-else label="業務フロー">
              <div class="field-hint">
                {{ selectedCaseType?.workflow_template_name || '—' }}（申請区分は不要。入管の 13 段階ではなく、この種別の段階と必要資料だけを作成します）
              </div>
            </el-form-item>
            <el-form-item label="担当者" prop="case.responsible_employee" :error="fieldErrors['case.responsible_employee']">
              <RemoteStaffSelect v-model="form.case.responsible_employee" class="form-control"
                                 @change="(row) => { responsibleName = row?.name ?? '' }" />
              <div v-if="hasOwnEmployee && !form.case.responsible_employee" class="field-hint">
                未選択の場合は自分（ログイン中の担当者）が担当になります。
              </div>
            </el-form-item>
            <el-form-item label="受任日" :error="fieldErrors['case.accepted_at']">
              <el-date-picker
                v-model="form.case.accepted_at"
                type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD"
                placeholder="YYYY-MM-DD" class="form-control"
              />
            </el-form-item>
            <el-form-item label="関連元の案件（任意）" :error="fieldErrors['case.parent_case']">
              <RemoteCaseSelect v-model="form.case.parent_case" clearable placeholder="例：経営管理→就労変更の元の在留案件"
                                class="form-control" @change="(row) => { parentCaseLabel = row?.case_number ?? '' }" />
              <div class="field-hint">年金・入社手続などを元の案件と結び付けます。元の案件の進捗・履歴は変わりません。</div>
            </el-form-item>
          </div>
        </el-card>

        <el-card v-if="canPickServices" shadow="never">
          <template #header>サービス項目（参考・任意）</template>
          <p class="field-hint">標準価格は参考です。実際の金額は見積書・請求書で決めます。選んだ時点の内容を案件に記録し、後でマスタを変えても変わりません。</p>
          <ServiceItemPicker @pick="addService" />
          <el-table v-if="serviceSelections.length" :data="serviceSelections" size="small" class="service-table">
            <el-table-column label="項目" min-width="200">
              <template #default="{ row }">{{ row.item.name }}<span class="service-category">{{ row.item.category }}</span></template>
            </el-table-column>
            <el-table-column label="標準価格（参考）" min-width="200">
              <template #default="{ row }">{{ serviceText(row.item) }}
                <el-tag v-if="row.item.price_status === 'provisional'" size="small" type="warning" effect="plain">暫定価格</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="数量" width="130">
              <template #default="{ row }"><el-input-number v-model="row.quantity" :min="1" :max="999" size="small" /></template>
            </el-table-column>
            <el-table-column width="80">
              <template #default="{ $index }"><el-button link type="danger" @click="removeService($index)">外す</el-button></template>
            </el-table-column>
          </el-table>
          <div v-if="fieldErrors['case.service_items']" class="field-error">{{ fieldErrors['case.service_items'] }}</div>
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
            <el-form-item label="会社名" :error="fieldErrors['company.name']" class="form-grid-start"><el-input v-model="form.company.name" /></el-form-item>
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
                <el-form-item label="氏名" :error="fieldErrors[`family_members.${index}.name`]" class="form-grid-start"><el-input v-model="fm.name" /></el-form-item>
                <el-form-item label="フリガナ" class="form-grid-start"><el-input v-model="fm.name_kana" /></el-form-item>
                <el-form-item label="生年月日" :error="fieldErrors[`family_members.${index}.birth_date`]">
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
        <el-button type="primary" @click="goToConfirm">次へ（確認）</el-button>
      </div>
    </div>

    <!-- STEP 2 -->
    <div v-show="activeStep === 1" class="detail-grid">
      <el-card shadow="never">
        <template #header>内容確認</template>
        <ul class="confirm-list">
          <li v-for="(line, index) in confirmSummaryLines" :key="index">{{ line }}</li>
        </ul>
        <p class="section-optional-note">
          「確定」を押すと、顧客・案件・Checklist・タイムラインが1つの処理でまとめて作成され、
          そのまま案件ワークスペースへ移動します。
        </p>
      </el-card>
      <div class="page-actions">
        <el-button @click="activeStep = 0">戻る</el-button>
        <el-button type="primary" :loading="submitting" @click="submitReception">確定して案件を作成</el-button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.reception-steps {
  margin: 8px 0 20px;
}

.error-list,
.confirm-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.9;
}

.service-table {
  margin-top: 8px;
}

.service-category {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.field-error {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-color-danger);
}
</style>
