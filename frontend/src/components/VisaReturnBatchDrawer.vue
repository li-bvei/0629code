<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  CircleCheckFilled,
  CopyDocument,
  Delete,
  Plus,
  UploadFilled,
  UserFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bulkCreateVisaReturnApplications } from '../api/accounting'
import { listCustomers } from '../api/customers'
import type {
  VisaGuarantorTemplate,
  VisaReturnApplicationPayload,
  VisaReturnFormData,
  VisaReturnGender,
  VisaReturnMaritalStatus,
} from '../types/accounting'
import type { Customer } from '../types/api'

type VisaBatchForm = VisaReturnApplicationPayload & { form_data: VisaReturnFormData }
type BatchEntry = { key: number; sourceCustomerId?: number; form: VisaBatchForm }

const props = defineProps<{
  modelValue: boolean
  guarantorTemplates: VisaGuarantorTemplate[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
  manageTemplates: []
}>()

let entrySequence = 0
const activeKey = ref<number | null>(null)
const entries = ref<BatchEntry[]>([])
const selectedTemplateId = ref<number | null>(null)
const selectedCustomerIds = ref<number[]>([])
const customerOptions = ref<Customer[]>([])
const customerCache = ref<Record<number, Customer>>({})
const customerLoading = ref(false)
const pasteDialogVisible = ref(false)
const pasteText = ref('')
const submitting = ref(false)
const activeTab = ref('basic')
const commonTrip = ref({
  entry_port: '',
  airline: '',
  entry_time1: '',
  entry_time2: '',
  entry_time3: '',
})

const genderOptions: { label: string; value: VisaReturnGender }[] = [
  { label: '未設定', value: '' },
  { label: '男性', value: 'male' },
  { label: '女性', value: 'female' },
]

const maritalStatusOptions: { label: string; value: VisaReturnMaritalStatus }[] = [
  { label: '未設定', value: '' },
  { label: '未婚', value: 'single' },
  { label: '既婚', value: 'married' },
  { label: '離婚', value: 'divorced' },
  { label: '死別', value: 'widowed' },
]

const yesNoOptions = [
  { label: '否', value: 'no' },
  { label: '是', value: 'yes' },
]

const createDefaultFormData = (): VisaReturnFormData => ({
  pinyin_name1: '',
  pinyin_name2: '',
  chinese_name1: '',
  chinese_name2: '',
  used_name1: '',
  used_name2: '',
  othernationality: '无',
  birth_place: '',
  chinese_id: '',
  passport_address: '',
  passport_a: '',
  zailiu_number: '',
  entry_port: '',
  airline: '',
  entry_time1: '',
  entry_time2: '',
  entry_time3: '',
  registered_address: '',
  current_address: '',
  home_address2: '',
  home_phone: '',
  workplace_name: '',
  workplace_address: '',
  workplace_phone: '',
  hotel: '',
  hotel_phone: '',
  hotel_address: '',
  last: '',
  job_title2: '',
  guarantor_name_en: '',
  guarantor_address_en: '',
  guarantor_birth_date: '',
  guarantor_nationality: '',
  guarantor_visa_status: '',
  gender2: '',
  same: '同上',
  x1: 'no',
  x2: 'no',
  x3: 'no',
  x4: 'no',
  x5: 'no',
  x6: 'no',
})

const createEmptyForm = (): VisaBatchForm => ({
  applicant_name: '',
  nationality: '',
  birth_date: null,
  gender: '',
  marital_status: '',
  passport_number: '',
  passport_issue_date: null,
  passport_expiry_date: null,
  residence_status: '',
  address: '',
  phone: '',
  email: '',
  occupation: '',
  guarantor_name: '',
  guarantor_phone: '',
  guarantor_address: '',
  guarantor_relationship: '',
  guarantor_occupation: '',
  guarantor_snapshot: {},
  form_data: createDefaultFormData(),
  note: '',
})

const activeEntry = computed(() => entries.value.find((entry) => entry.key === activeKey.value) || null)
const activeTemplates = computed(() => props.guarantorTemplates.filter((template) => template.is_active))
const selectedTemplate = computed(
  () => activeTemplates.value.find((template) => template.id === selectedTemplateId.value) || null,
)
const completedCount = computed(() => entries.value.filter((entry) => entry.form.applicant_name?.trim()).length)

const addEmptyEntry = (seed?: Partial<VisaBatchForm>) => {
  const entry: BatchEntry = {
    key: ++entrySequence,
    form: {
      ...createEmptyForm(),
      ...seed,
      form_data: {
        ...createDefaultFormData(),
        ...(seed?.form_data || {}),
      },
    },
  }
  entries.value.push(entry)
  activeKey.value = entry.key
  activeTab.value = 'basic'
}

const resetBatch = () => {
  entries.value = []
  activeKey.value = null
  selectedTemplateId.value = activeTemplates.value[0]?.id || null
  selectedCustomerIds.value = []
  commonTrip.value = { entry_port: '', airline: '', entry_time1: '', entry_time2: '', entry_time3: '' }
  pasteText.value = ''
  addEmptyEntry()
}

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) return
    if (!entries.value.length) resetBatch()
    searchCustomers('')
  },
)

watch(
  () => props.guarantorTemplates,
  () => {
    if (!selectedTemplateId.value && activeTemplates.value.length) {
      selectedTemplateId.value = activeTemplates.value[0].id
    }
  },
  { deep: true },
)

const searchCustomers = async (keyword: string) => {
  customerLoading.value = true
  try {
    const data = await listCustomers({ page: 1, search: keyword.trim() || undefined })
    customerOptions.value = data.results
    data.results.forEach((customer) => {
      customerCache.value[customer.id] = customer
    })
  } catch {
    ElMessage.error('顧客データの取得に失敗しました。')
  } finally {
    customerLoading.value = false
  }
}

const customerToForm = (customer: Customer): VisaBatchForm => ({
  ...createEmptyForm(),
  applicant_name: customer.name,
  nationality: customer.nationality,
  birth_date: customer.birth_date || null,
  gender: customer.gender === 'male' || customer.gender === 'female' ? customer.gender : '',
  passport_number: customer.passport_no,
  passport_expiry_date: customer.passport_expiry,
  residence_status: customer.residence_status,
  address: customer.address,
  phone: customer.phone,
  email: customer.email,
  form_data: {
    ...createDefaultFormData(),
    zailiu_number: customer.residence_card_no,
    current_address: customer.address,
    home_address2: customer.address,
  },
})

const addSelectedCustomers = () => {
  const existingCustomerIds = new Set(entries.value.map((entry) => entry.sourceCustomerId).filter(Boolean))
  let added = 0
  selectedCustomerIds.value.forEach((customerId) => {
    const customer = customerCache.value[customerId]
    if (!customer || existingCustomerIds.has(customerId)) return
    const entry: BatchEntry = {
      key: ++entrySequence,
      sourceCustomerId: customerId,
      form: customerToForm(customer),
    }
    entries.value.push(entry)
    activeKey.value = entry.key
    existingCustomerIds.add(customerId)
    added += 1
  })
  selectedCustomerIds.value = []
  if (added) ElMessage.success(`${added}名の顧客情報を追加しました。`)
  else ElMessage.info('追加できる顧客が選択されていません。')
}

const addFromCurrentTrip = () => {
  const current = activeEntry.value?.form
  addEmptyEntry({
    nationality: current?.nationality || '',
    residence_status: current?.residence_status || '',
    occupation: current?.occupation || '',
    form_data: {
      ...createDefaultFormData(),
      entry_port: current?.form_data.entry_port || '',
      airline: current?.form_data.airline || '',
      entry_time1: current?.form_data.entry_time1 || '',
      entry_time2: current?.form_data.entry_time2 || '',
      entry_time3: current?.form_data.entry_time3 || '',
      workplace_name: current?.form_data.workplace_name || '',
      workplace_address: current?.form_data.workplace_address || '',
      workplace_phone: current?.form_data.workplace_phone || '',
      hotel: current?.form_data.hotel || '',
      hotel_phone: current?.form_data.hotel_phone || '',
      hotel_address: current?.form_data.hotel_address || '',
    },
  })
}

const removeEntry = async (entry: BatchEntry) => {
  if (entries.value.length === 1) {
    ElMessage.info('少なくとも1名分の入力欄が必要です。')
    return
  }
  if (entry.form.applicant_name?.trim()) {
    try {
      await ElMessageBox.confirm(`「${entry.form.applicant_name}」を一覧から外しますか？`, '確認', {
        confirmButtonText: '外す',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      })
    } catch {
      return
    }
  }
  const index = entries.value.findIndex((item) => item.key === entry.key)
  entries.value.splice(index, 1)
  if (activeKey.value === entry.key) {
    activeKey.value = entries.value[Math.max(0, index - 1)]?.key || null
  }
}

const pasteExample = '氏名\t英文姓\t英文名\t生年月日\t性別\t国籍\tパスポート番号\t在留資格\t電話番号\tメール\t住所'

const normalizeHeader = (value: string) => value.trim().replace(/[\s_・/]/g, '').toLowerCase()
const headerAliases: Record<string, keyof VisaBatchForm | keyof VisaReturnFormData> = {
  氏名: 'applicant_name',
  申請人姓名: 'applicant_name',
  姓名: 'applicant_name',
  英文姓: 'pinyin_name1',
  英文名: 'pinyin_name2',
  中文姓: 'chinese_name1',
  中文名: 'chinese_name2',
  生年月日: 'birth_date',
  出生日期: 'birth_date',
  性別: 'gender',
  性别: 'gender',
  国籍: 'nationality',
  パスポート番号: 'passport_number',
  护照号码: 'passport_number',
  在留資格: 'residence_status',
  電話番号: 'phone',
  电话: 'phone',
  メール: 'email',
  邮箱: 'email',
  住所: 'address',
  地址: 'address',
  中国身份证号码: 'chinese_id',
  在留番号: 'zailiu_number',
}

const parseGender = (value: string): VisaReturnGender => {
  const normalized = value.trim().toLowerCase()
  if (['男性', '男', 'male', 'm'].includes(normalized)) return 'male'
  if (['女性', '女', 'female', 'f'].includes(normalized)) return 'female'
  return ''
}

const importPastedRows = () => {
  const lines = pasteText.value
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter((line) => line.trim())
  if (lines.length < 2) {
    ElMessage.warning('見出し行と、1名以上のデータを貼り付けてください。')
    return
  }
  const headers = lines[0].split('\t').map((header) => headerAliases[normalizeHeader(header)] || null)
  if (!headers.includes('applicant_name')) {
    ElMessage.warning('「氏名」列が見つかりません。')
    return
  }
  let imported = 0
  lines.slice(1).forEach((line) => {
    const values = line.split('\t')
    const form = createEmptyForm()
    headers.forEach((field, index) => {
      if (!field) return
      const value = values[index]?.trim() || ''
      if (field === 'gender') {
        form.gender = parseGender(value)
      } else if (field in form.form_data) {
        form.form_data[field as keyof VisaReturnFormData] = value as never
      } else {
        ;(form[field as keyof VisaBatchForm] as string | null | undefined) = value || null
      }
    })
    if (!form.applicant_name?.trim()) return
    const entry = { key: ++entrySequence, form }
    entries.value.push(entry)
    activeKey.value = entry.key
    imported += 1
  })
  if (!imported) {
    ElMessage.warning('追加できる申請人データがありません。')
    return
  }
  if (entries.value.length > imported && !entries.value[0].form.applicant_name?.trim()) {
    const emptyKey = entries.value[0].key
    entries.value = entries.value.filter((entry) => entry.key !== emptyKey)
  }
  pasteDialogVisible.value = false
  pasteText.value = ''
  ElMessage.success(`${imported}名を追加しました。`)
}

const guarantorPayload = (template: VisaGuarantorTemplate | null) => {
  if (!template) return {}
  return {
    // テンプレートを明示的に記録する（スナップショットは後端が DB のテンプレートから作り直す）
    guarantor_template: template.id,
    guarantor_name: template.guarantor_name,
    guarantor_phone: template.guarantor_phone,
    guarantor_address: template.guarantor_address,
    guarantor_relationship: template.guarantor_relationship,
    guarantor_occupation: template.guarantor_occupation,
  }
}

const buildPayload = (entry: BatchEntry): VisaReturnApplicationPayload => {
  const template = selectedTemplate.value
  const formData = {
    ...entry.form.form_data,
    entry_port: entry.form.form_data.entry_port || commonTrip.value.entry_port,
    airline: entry.form.form_data.airline || commonTrip.value.airline,
    entry_time1: entry.form.form_data.entry_time1 || commonTrip.value.entry_time1,
    entry_time2: entry.form.form_data.entry_time2 || commonTrip.value.entry_time2,
    entry_time3: entry.form.form_data.entry_time3 || commonTrip.value.entry_time3,
    guarantor_name_en: template?.guarantor_name_en || entry.form.form_data.guarantor_name_en,
    guarantor_address_en: template?.guarantor_address_en || entry.form.form_data.guarantor_address_en,
    guarantor_birth_date: template?.guarantor_birth_date || entry.form.form_data.guarantor_birth_date,
    guarantor_nationality: template?.guarantor_nationality || entry.form.form_data.guarantor_nationality,
    guarantor_visa_status: template?.guarantor_visa_status || entry.form.form_data.guarantor_visa_status,
    home_address2: entry.form.form_data.current_address || entry.form.form_data.home_address2,
    source_customer_id: entry.sourceCustomerId ? String(entry.sourceCustomerId) : '',
  }
  return {
    ...entry.form,
    ...guarantorPayload(template),
    birth_date: entry.form.birth_date || null,
    passport_issue_date: entry.form.passport_issue_date || null,
    passport_expiry_date: entry.form.passport_expiry_date || null,
    form_data: formData,
  }
}

const submitBatch = async () => {
  const invalid = entries.value.find((entry) => !entry.form.applicant_name?.trim())
  if (invalid) {
    activeKey.value = invalid.key
    activeTab.value = 'basic'
    ElMessage.warning('すべての申請人氏名を入力してください。')
    return
  }
  if (!selectedTemplate.value) {
    try {
      await ElMessageBox.confirm(
        '在日担保人テンプレートが未選択です。このまま作成しますか？',
        'テンプレート未選択',
        { confirmButtonText: 'このまま作成', cancelButtonText: '戻る', type: 'warning' },
      )
    } catch {
      return
    }
  }
  submitting.value = true
  try {
    const result = await bulkCreateVisaReturnApplications(entries.value.map(buildPayload))
    ElMessage.success(`${result.created}名分の返签 visa 表を作成しました。`)
    emit('update:modelValue', false)
    emit('saved')
    resetBatch()
  } catch {
    ElMessage.error('一括作成に失敗しました。入力内容を確認してください。')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="返签 VISA 多人一括作成"
    size="94%"
    :with-header="false"
    class="visa-batch-drawer"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="batch-shell">
      <header class="batch-header">
        <div>
          <div class="batch-eyebrow">返签 VISA · 多人作成</div>
          <h2>共通情報は一度だけ、申請人を続けて入力</h2>
          <p>担保人と入国予定を全員に適用し、登録済み顧客や表計算データも再利用できます。</p>
        </div>
        <el-button @click="emit('update:modelValue', false)">閉じる</el-button>
      </header>

      <div class="batch-common-panel">
        <section class="batch-common-section">
          <div class="batch-section-heading">
            <span class="batch-step">1</span>
            <div>
              <strong>在日担保人を選択</strong>
              <small>選択した内容を全員へ自動反映</small>
            </div>
            <el-button link type="primary" @click="emit('manageTemplates')">テンプレート管理</el-button>
          </div>
          <div v-if="activeTemplates.length" class="guarantor-choice-grid">
            <button
              v-for="template in activeTemplates"
              :key="template.id"
              type="button"
              class="guarantor-choice"
              :class="{ 'is-selected': selectedTemplateId === template.id }"
              @click="selectedTemplateId = template.id"
            >
              <el-icon><CircleCheckFilled /></el-icon>
              <span>
                <strong>{{ template.name }}</strong>
                <small>{{ template.guarantor_name || '氏名未登録' }}</small>
              </span>
            </button>
          </div>
          <el-empty v-else description="担保人テンプレートがありません" :image-size="42">
            <el-button type="primary" plain @click="emit('manageTemplates')">テンプレートを登録</el-button>
          </el-empty>
        </section>

        <section class="batch-common-section batch-trip-section">
          <div class="batch-section-heading">
            <span class="batch-step">2</span>
            <div>
              <strong>共通の入国予定</strong>
              <small>個別入力がある人は、その内容を優先</small>
            </div>
          </div>
          <div class="batch-trip-grid">
            <el-input v-model="commonTrip.entry_port" placeholder="入境口岸" />
            <el-input v-model="commonTrip.airline" placeholder="航空会社 / 便名" />
            <el-input v-model="commonTrip.entry_time1" placeholder="入国日 YYYY-MM-DD" />
            <el-input v-model="commonTrip.entry_time2" placeholder="離境日 YYYY-MM-DD" />
            <el-input v-model="commonTrip.entry_time3" placeholder="滞在期間 例：90日" />
          </div>
        </section>
      </div>

      <div class="batch-workspace">
        <aside class="batch-roster">
          <div class="batch-section-heading">
            <span class="batch-step">3</span>
            <div>
              <strong>申請人を追加</strong>
              <small>{{ entries.length }}名 · 入力済み {{ completedCount }}名</small>
            </div>
          </div>

          <div class="customer-import-box">
            <el-select
              v-model="selectedCustomerIds"
              multiple
              filterable
              remote
              collapse-tags
              collapse-tags-tooltip
              :remote-method="searchCustomers"
              :loading="customerLoading"
              placeholder="登録済み顧客を検索"
              class="batch-customer-select"
            >
              <el-option
                v-for="customer in customerOptions"
                :key="customer.id"
                :label="`${customer.name} · ${customer.passport_no || '旅券未登録'}`"
                :value="customer.id"
              />
            </el-select>
            <el-button :disabled="!selectedCustomerIds.length" @click="addSelectedCustomers">選択した顧客を追加</el-button>
          </div>

          <div class="batch-add-actions">
            <el-button :icon="Plus" @click="addEmptyEntry()">空欄を追加</el-button>
            <el-button :icon="UploadFilled" @click="pasteDialogVisible = true">表から貼付</el-button>
          </div>

          <div class="batch-person-list">
            <button
              v-for="(entry, index) in entries"
              :key="entry.key"
              type="button"
              class="batch-person-item"
              :class="{ 'is-active': activeKey === entry.key }"
              @click="activeKey = entry.key"
            >
              <span class="batch-person-index">{{ index + 1 }}</span>
              <span class="batch-person-copy">
                <strong>{{ entry.form.applicant_name || '氏名未入力' }}</strong>
                <small>{{ entry.form.passport_number || (entry.sourceCustomerId ? '顧客情報から追加' : '新規入力') }}</small>
              </span>
              <el-icon v-if="entry.form.applicant_name" class="batch-person-ready"><CircleCheckFilled /></el-icon>
            </button>
          </div>

          <el-button class="batch-copy-trip" :icon="CopyDocument" @click="addFromCurrentTrip">
            この人の行程を引き継いで追加
          </el-button>
        </aside>

        <main v-if="activeEntry" class="batch-editor">
          <div class="batch-editor-head">
            <div>
              <span>申請人 {{ entries.findIndex((entry) => entry.key === activeEntry?.key) + 1 }}</span>
              <h3>{{ activeEntry.form.applicant_name || '氏名を入力してください' }}</h3>
            </div>
            <el-button type="danger" plain :icon="Delete" @click="removeEntry(activeEntry)">この人を外す</el-button>
          </div>

          <el-tabs v-model="activeTab" class="batch-form-tabs">
            <el-tab-pane label="基本・旅券" name="basic">
              <el-form :model="activeEntry.form" label-position="top" class="batch-form-grid">
                <el-form-item label="申請人姓名" required>
                  <el-input v-model="activeEntry.form.applicant_name" placeholder="例：王 小明" />
                </el-form-item>
                <el-form-item label="生年月日">
                  <el-date-picker v-model="activeEntry.form.birth_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
                </el-form-item>
                <el-form-item label="性別">
                  <el-select v-model="activeEntry.form.gender" class="form-control">
                    <el-option v-for="option in genderOptions" :key="option.value" :label="option.label" :value="option.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="婚姻状況">
                  <el-select v-model="activeEntry.form.marital_status" class="form-control">
                    <el-option v-for="option in maritalStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="国籍"><el-input v-model="activeEntry.form.nationality" /></el-form-item>
                <el-form-item label="職業"><el-input v-model="activeEntry.form.occupation" /></el-form-item>
                <el-form-item label="英文姓"><el-input v-model="activeEntry.form.form_data.pinyin_name1" /></el-form-item>
                <el-form-item label="英文名"><el-input v-model="activeEntry.form.form_data.pinyin_name2" /></el-form-item>
                <el-form-item label="中文 姓"><el-input v-model="activeEntry.form.form_data.chinese_name1" /></el-form-item>
                <el-form-item label="中文 名"><el-input v-model="activeEntry.form.form_data.chinese_name2" /></el-form-item>
                <el-form-item label="パスポート番号"><el-input v-model="activeEntry.form.passport_number" /></el-form-item>
                <el-form-item label="パスポート発行日"><el-date-picker v-model="activeEntry.form.passport_issue_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" /></el-form-item>
                <el-form-item label="パスポート期限"><el-date-picker v-model="activeEntry.form.passport_expiry_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" /></el-form-item>
                <el-form-item label="护照签发地"><el-input v-model="activeEntry.form.form_data.passport_address" /></el-form-item>
                <el-form-item label="护照签发机关" class="batch-form-full"><el-input v-model="activeEntry.form.form_data.passport_a" /></el-form-item>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="在留・入国" name="entry">
              <el-form :model="activeEntry.form" label-position="top" class="batch-form-grid">
                <el-form-item label="在留資格"><el-input v-model="activeEntry.form.residence_status" /></el-form-item>
                <el-form-item label="在留番号"><el-input v-model="activeEntry.form.form_data.zailiu_number" /></el-form-item>
                <el-form-item label="出生地"><el-input v-model="activeEntry.form.form_data.birth_place" /></el-form-item>
                <el-form-item label="中国身份证号码"><el-input v-model="activeEntry.form.form_data.chinese_id" /></el-form-item>
                <el-form-item label="曾用名英文"><el-input v-model="activeEntry.form.form_data.used_name1" /></el-form-item>
                <el-form-item label="曾用名中文"><el-input v-model="activeEntry.form.form_data.used_name2" /></el-form-item>
                <el-form-item label="其他国籍"><el-input v-model="activeEntry.form.form_data.othernationality" /></el-form-item>
                <el-form-item label="入境口岸"><el-input v-model="activeEntry.form.form_data.entry_port" :placeholder="commonTrip.entry_port || '共通設定を使用'" /></el-form-item>
                <el-form-item label="航空会社 / 便名"><el-input v-model="activeEntry.form.form_data.airline" :placeholder="commonTrip.airline || '共通設定を使用'" /></el-form-item>
                <el-form-item label="预定入境日"><el-input v-model="activeEntry.form.form_data.entry_time1" :placeholder="commonTrip.entry_time1 || 'YYYY-MM-DD'" /></el-form-item>
                <el-form-item label="预定离境日"><el-input v-model="activeEntry.form.form_data.entry_time2" :placeholder="commonTrip.entry_time2 || 'YYYY-MM-DD'" /></el-form-item>
                <el-form-item label="预定滞在期间"><el-input v-model="activeEntry.form.form_data.entry_time3" :placeholder="commonTrip.entry_time3 || '例：90日'" /></el-form-item>
                <el-form-item label="上次赴日记录" class="batch-form-full"><el-input v-model="activeEntry.form.form_data.last" type="textarea" :rows="3" /></el-form-item>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="連絡先・勤務先" name="contact">
              <el-form :model="activeEntry.form" label-position="top" class="batch-form-grid">
                <el-form-item label="電話番号"><el-input v-model="activeEntry.form.phone" /></el-form-item>
                <el-form-item label="メール"><el-input v-model="activeEntry.form.email" /></el-form-item>
                <el-form-item label="住所" class="batch-form-full"><el-input v-model="activeEntry.form.address" /></el-form-item>
                <el-form-item label="本国電話"><el-input v-model="activeEntry.form.form_data.home_phone" /></el-form-item>
                <el-form-item label="职业 / 身份补足"><el-input v-model="activeEntry.form.form_data.job_title2" /></el-form-item>
                <el-form-item label="户籍地址" class="batch-form-full"><el-input v-model="activeEntry.form.form_data.registered_address" /></el-form-item>
                <el-form-item label="现住址" class="batch-form-full"><el-input v-model="activeEntry.form.form_data.current_address" /></el-form-item>
                <el-form-item label="工作单位 / 学校"><el-input v-model="activeEntry.form.form_data.workplace_name" /></el-form-item>
                <el-form-item label="工作单位 / 学校电话"><el-input v-model="activeEntry.form.form_data.workplace_phone" /></el-form-item>
                <el-form-item label="工作单位 / 学校地址" class="batch-form-full"><el-input v-model="activeEntry.form.form_data.workplace_address" /></el-form-item>
                <el-form-item label="日本滞在先名称"><el-input v-model="activeEntry.form.form_data.hotel" /></el-form-item>
                <el-form-item label="日本滞在先电话"><el-input v-model="activeEntry.form.form_data.hotel_phone" /></el-form-item>
                <el-form-item label="日本滞在先地址" class="batch-form-full"><el-input v-model="activeEntry.form.form_data.hotel_address" /></el-form-item>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="確認項目・備考" name="checks">
              <div class="batch-check-grid">
                <label v-for="index in 6" :key="index">
                  <span>Page2 x{{ index }}</span>
                  <el-select v-model="activeEntry.form.form_data[`x${index}`]" class="form-control">
                    <el-option v-for="option in yesNoOptions" :key="option.value" :label="option.label" :value="option.value" />
                  </el-select>
                </label>
              </div>
              <el-form :model="activeEntry.form" label-position="top">
                <el-form-item label="邀请人信息同上"><el-input v-model="activeEntry.form.form_data.same" /></el-form-item>
                <el-form-item label="備考"><el-input v-model="activeEntry.form.note" type="textarea" :rows="5" /></el-form-item>
              </el-form>
            </el-tab-pane>
          </el-tabs>
        </main>
      </div>

      <footer class="batch-footer">
        <div class="batch-footer-summary">
          <el-icon><UserFilled /></el-icon>
          <span><strong>{{ entries.length }}名</strong>を一括作成</span>
          <span v-if="selectedTemplate" class="batch-footer-template">担保人：{{ selectedTemplate.name }}</span>
        </div>
        <div>
          <el-button @click="emit('update:modelValue', false)">下書きを閉じる</el-button>
          <el-button type="primary" :loading="submitting" @click="submitBatch">{{ entries.length }}名分を保存</el-button>
        </div>
      </footer>
    </div>

    <el-dialog v-model="pasteDialogVisible" title="表計算データから一括追加" width="720px" append-to-body>
      <p class="paste-help">Excel / Google Sheets から見出しを含めてコピーし、そのまま貼り付けてください。</p>
      <el-input
        v-model="pasteText"
        type="textarea"
        :rows="12"
        :placeholder="`${pasteExample}\n王 小明\tWANG\tXIAOMING\t2000-01-01\t男\t中国\tE12345678\t留学`"
      />
      <div class="paste-columns">対応列：氏名、英文姓・名、中文姓・名、生年月日、性別、国籍、旅券、在留資格、電話、メール、住所、中国身份证号码、在留番号</div>
      <template #footer>
        <el-button @click="pasteDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" @click="importPastedRows">申請人を追加</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<style scoped>
.batch-shell {
  min-height: 100%;
  padding: 24px 28px 96px;
  background: #f7fafc;
}

.batch-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.batch-eyebrow {
  margin-bottom: 6px;
  color: #4e8fbf;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.batch-header h2 {
  margin: 0;
  color: var(--sunrise-text);
  font-size: 24px;
}

.batch-header p {
  margin: 7px 0 0;
  color: var(--sunrise-muted);
  font-size: 13px;
}

.batch-common-panel {
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(520px, 1.4fr);
  gap: 14px;
  margin-bottom: 14px;
}

.batch-common-section,
.batch-roster,
.batch-editor {
  border: 1px solid var(--sunrise-border);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 10px 26px rgba(98, 135, 163, 0.08);
}

.batch-common-section {
  padding: 16px;
}

.batch-section-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 36px;
}

.batch-section-heading > div {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.batch-section-heading strong {
  color: var(--sunrise-text);
  font-size: 14px;
}

.batch-section-heading small {
  margin-top: 2px;
  color: var(--sunrise-muted);
  font-size: 11px;
}

.batch-step {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;
  border-radius: 9px;
  color: #315b78;
  background: var(--sunrise-blue-soft);
  font-size: 13px;
  font-weight: 800;
}

.guarantor-choice-grid {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  overflow-x: auto;
}

.guarantor-choice {
  display: flex;
  min-width: 142px;
  align-items: center;
  gap: 9px;
  padding: 10px 12px;
  border: 1px solid var(--sunrise-border);
  border-radius: 10px;
  color: var(--sunrise-muted);
  background: #fff;
  cursor: pointer;
  text-align: left;
}

.guarantor-choice.is-selected {
  border-color: #79b6df;
  color: #4e8fbf;
  background: var(--sunrise-blue-soft);
  box-shadow: inset 0 0 0 1px rgba(121, 182, 223, 0.28);
}

.guarantor-choice span {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.guarantor-choice strong {
  color: var(--sunrise-text);
  font-size: 13px;
}

.guarantor-choice small {
  overflow: hidden;
  margin-top: 2px;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-trip-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(150px, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.batch-workspace {
  display: grid;
  grid-template-columns: 292px minmax(0, 1fr);
  gap: 14px;
  min-height: 560px;
}

.batch-roster {
  display: flex;
  min-height: 0;
  flex-direction: column;
  padding: 16px;
}

.customer-import-box {
  display: grid;
  gap: 8px;
  padding: 12px;
  margin-top: 14px;
  border-radius: 10px;
  background: #f7fafc;
}

.batch-customer-select {
  width: 100%;
}

.batch-add-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 10px 0;
}

.batch-add-actions .el-button {
  margin-left: 0;
}

.batch-person-list {
  display: flex;
  min-height: 180px;
  max-height: 440px;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
}

.batch-person-item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 18px;
  gap: 8px;
  align-items: center;
  width: 100%;
  padding: 9px;
  border: 1px solid transparent;
  border-radius: 9px;
  color: var(--sunrise-text);
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.batch-person-item:hover {
  background: #f7fafc;
}

.batch-person-item.is-active {
  border-color: rgba(121, 182, 223, 0.56);
  background: var(--sunrise-blue-soft);
}

.batch-person-index {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 8px;
  color: var(--sunrise-muted);
  background: #eef2f5;
  font-size: 12px;
  font-weight: 800;
}

.batch-person-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.batch-person-copy strong,
.batch-person-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-person-copy strong {
  font-size: 13px;
}

.batch-person-copy small {
  margin-top: 2px;
  color: var(--sunrise-muted);
  font-size: 11px;
}

.batch-person-ready {
  color: #67c23a;
}

.batch-copy-trip {
  width: 100%;
  margin-top: 10px;
}

.batch-editor {
  min-width: 0;
  padding: 18px 22px 24px;
}

.batch-editor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--sunrise-border);
}

.batch-editor-head span {
  color: var(--sunrise-muted);
  font-size: 11px;
  font-weight: 700;
}

.batch-editor-head h3 {
  margin: 3px 0 0;
  color: var(--sunrise-text);
  font-size: 18px;
}

.batch-form-tabs {
  margin-top: 4px;
}

.batch-form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 14px;
}

.batch-form-full {
  grid-column: 1 / -1;
}

.batch-check-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 8px 0 20px;
}

.batch-check-grid label {
  display: grid;
  grid-template-columns: 1fr 110px;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--sunrise-border);
  border-radius: 9px;
  color: var(--sunrise-text);
  font-size: 13px;
  font-weight: 700;
}

.batch-footer {
  position: fixed;
  right: 0;
  bottom: 0;
  z-index: 4;
  display: flex;
  width: 94%;
  min-height: 72px;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 28px;
  border-top: 1px solid var(--sunrise-border);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 -8px 26px rgba(98, 135, 163, 0.12);
  backdrop-filter: blur(10px);
}

.batch-footer-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--sunrise-muted);
  font-size: 13px;
}

.batch-footer-summary strong {
  color: var(--sunrise-text);
}

.batch-footer-template {
  padding-left: 10px;
  border-left: 1px solid var(--sunrise-border);
}

.paste-help,
.paste-columns {
  color: var(--sunrise-muted);
  font-size: 13px;
  line-height: 1.65;
}

.paste-help {
  margin: 0 0 12px;
}

.paste-columns {
  margin-top: 10px;
}

@media (max-width: 1100px) {
  .batch-common-panel,
  .batch-workspace {
    grid-template-columns: 1fr;
  }

  .batch-trip-grid,
  .batch-form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .batch-person-list {
    max-height: 260px;
  }
}

@media (min-width: 1560px) {
  .batch-trip-grid {
    grid-template-columns: repeat(5, minmax(120px, 1fr));
  }
}

@media (max-width: 720px) {
  .batch-shell {
    padding: 18px 14px 100px;
  }

  .batch-common-panel,
  .batch-trip-grid,
  .batch-form-grid,
  .batch-check-grid {
    grid-template-columns: 1fr;
  }

  .batch-header {
    flex-direction: column;
  }

  .batch-form-full {
    grid-column: auto;
  }

  .batch-footer {
    width: 100%;
    flex-direction: column;
    align-items: stretch;
    padding: 10px 14px;
  }

  .batch-footer-summary {
    display: none;
  }
}
</style>
