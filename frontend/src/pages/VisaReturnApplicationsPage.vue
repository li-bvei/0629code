<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  checkVisaReturnApplication,
  createVisaGuarantorTemplate,
  createVisaReturnApplication,
  deleteVisaGuarantorTemplate,
  deleteVisaReturnApplication,
  downloadVisaPdfGeneration,
  generateVisaReturnPdf,
  listVisaPdfGenerations,
  listVisaGuarantorTemplates,
  listVisaReturnApplications,
  updateVisaGuarantorTemplate,
  updateVisaReturnApplication,
} from '../api/accounting'
import type {
  VisaCheckResult,
  VisaPdfGeneration,
  VisaGuarantorTemplate,
  VisaGuarantorTemplatePayload,
  VisaReturnApplication,
  VisaReturnFormData,
  VisaReturnApplicationPayload,
  VisaReturnGender,
  VisaReturnMaritalStatus,
} from '../types/accounting'
import { formatDate } from '../utils/date'
import VisaReturnBatchDrawer from '../components/VisaReturnBatchDrawer.vue'
import VisaImportDrawer from '../components/VisaImportDrawer.vue'
import RemoteCaseSelect from '../components/RemoteCaseSelect.vue'
import { getCase } from '../api/cases'
import { getCustomer } from '../api/customers'
import type { Case } from '../types/api'
import { extractFilename as extractDownloadName, saveBlob } from '../components/vouchers/voucherErrors'
import {
  applyGuarantorTemplateToForm, guarantorSources, stepProblems, visaErrorView, type FieldSource,
} from '../utils/visaFlow'
import './accounting/accounting.css'

type VisaReturnForm = VisaReturnApplicationPayload & {
  form_data: VisaReturnFormData
  guarantor_snapshot: Record<string, string>
  guarantor_template?: number | null
}

// --- 主流程（2026-10 P1）：申請人 → 担保人テンプレート → 必要項目 → プレビュー → PDF 生成 ---
const FLOW_STEPS = ['申請人', '担保人テンプレート', '必要項目の確認', 'プレビュー', 'PDF 生成']
const auth = useAuthStore()
const flowStep = ref(0)
const useTemplate = ref(true)
const checkResult = ref<VisaCheckResult | null>(null)
const checking = ref(false)
const generating = ref(false)
const lastGeneration = ref<VisaPdfGeneration | null>(null)
const generationError = ref<{ title: string; detail: string; fields: string[] } | null>(null)
const generations = ref<VisaPdfGeneration[]>([])
const caseSourceId = ref<number | null>(null)
const SOURCE_LABELS: Record<string, string> = { template: 'テンプレート', manual: '手入力', applicant: '申請人', '': '未入力' }

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const templateDrawerVisible = ref(false)
const batchDrawerVisible = ref(false)
// CSV/XLSX 一括取込（主な入口）。既存の「多人一括作成」（顧客選択＋TSV 貼付）は補助入口として残す。
const importDrawerVisible = ref(false)
const applications = ref<VisaReturnApplication[]>([])
const guarantorTemplates = ref<VisaGuarantorTemplate[]>([])
const selectedApplication = ref<VisaReturnApplication | null>(null)
const editingId = ref<number | null>(null)
const editingTemplateId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const templateFormRef = ref<FormInstance>()
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const filters = ref({
  search: '',
})
const templateSearch = ref('')
const templateLoading = ref(false)
const selectedGuarantorTemplateId = ref<number | null>(null)

const createEmptyTemplateForm = (): VisaGuarantorTemplatePayload => ({
  name: '',
  guarantor_name: '',
  guarantor_name_en: '',
  guarantor_phone: '',
  guarantor_address: '',
  guarantor_address_en: '',
  guarantor_birth_date: null,
  guarantor_nationality: '',
  guarantor_visa_status: '',
  guarantor_occupation: '',
  guarantor_relationship: '',
  guarantor_company_name: '',
  note: '',
  is_active: true,
  sort_order: 0,
})

const templateForm = ref<VisaGuarantorTemplatePayload>(createEmptyTemplateForm())

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

const normalizeFormData = (source?: Record<string, unknown> | null): VisaReturnFormData => {
  const defaults = createDefaultFormData()
  const merged = { ...defaults }
  if (!source) return merged

  Object.keys(defaults).forEach((key) => {
    const typedKey = key as keyof VisaReturnFormData
    const value = source[key]
    if (value !== undefined && value !== null) {
      if (key.startsWith('x') && typeof value === 'boolean') {
        merged[typedKey] = (value ? 'no' : 'yes') as never
      } else {
        merged[typedKey] = value as never
      }
    }
  })

  if (!merged.home_address2 && typeof source.home_address1 === 'string') {
    merged.home_address2 = source.home_address1
  }
  if (!merged.current_address && merged.home_address2) {
    merged.current_address = merged.home_address2
  }

  return merged
}

const normalizeFormDataForPayload = (source: VisaReturnFormData): VisaReturnFormData => {
  const normalized = normalizeFormData(source)
  normalized.home_address2 = normalized.current_address || normalized.home_address2
  return normalized
}

const createEmptyForm = (): VisaReturnForm => ({
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
  guarantor_snapshot: {
    guarantor_name_en: '',
    guarantor_address_en: '',
    guarantor_nationality: '',
    guarantor_birth_date: '',
    guarantor_visa_status: '',
  },
  form_data: createDefaultFormData(),
  note: '',
})

const form = ref<VisaReturnForm>(createEmptyForm())

const rules: FormRules<VisaReturnForm> = {
  applicant_name: [{ required: true, message: '申請人姓名を入力してください。', trigger: 'blur' }],
}

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

const genderLabel = (value?: string) => genderOptions.find((item) => item.value === value)?.label || '-'
const maritalStatusLabel = (value?: string) => maritalStatusOptions.find((item) => item.value === value)?.label || '-'


const fetchApplications = async (page = currentPage.value) => {
  loading.value = true
  try {
    const data = await listVisaReturnApplications({ page, search: filters.value.search })
    applications.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    ElMessage.error('返签 visa 表一覧の取得に失敗しました。')
  } finally {
    loading.value = false
  }
}

const fetchGuarantorTemplates = async () => {
  templateLoading.value = true
  try {
    const data = await listVisaGuarantorTemplates({
      search: templateSearch.value,
      include_inactive: 1,
      page_size: 1000,
    })
    guarantorTemplates.value = data.results
  } catch {
    ElMessage.error('在日担保人テンプレートの取得に失敗しました。')
  } finally {
    templateLoading.value = false
  }
}

const resetTemplateForm = () => {
  editingTemplateId.value = null
  templateForm.value = createEmptyTemplateForm()
  templateFormRef.value?.clearValidate()
}

const openTemplateDrawer = async () => {
  templateDrawerVisible.value = true
  resetTemplateForm()
  await fetchGuarantorTemplates()
}

const editTemplate = (template: VisaGuarantorTemplate) => {
  editingTemplateId.value = template.id
  templateForm.value = {
    name: template.name,
    guarantor_name: template.guarantor_name,
    guarantor_name_en: template.guarantor_name_en,
    guarantor_phone: template.guarantor_phone,
    guarantor_address: template.guarantor_address,
    guarantor_address_en: template.guarantor_address_en,
    guarantor_birth_date: template.guarantor_birth_date,
    guarantor_nationality: template.guarantor_nationality,
    guarantor_visa_status: template.guarantor_visa_status,
    guarantor_occupation: template.guarantor_occupation,
    guarantor_relationship: template.guarantor_relationship,
    guarantor_company_name: template.guarantor_company_name,
    note: template.note,
    is_active: template.is_active,
    sort_order: template.sort_order,
  }
}

const submitTemplate = async () => {
  if (!templateForm.value.name.trim()) {
    ElMessage.warning('テンプレート名称を入力してください。')
    return
  }
  try {
    if (editingTemplateId.value) {
      await updateVisaGuarantorTemplate(editingTemplateId.value, templateForm.value)
      ElMessage.success('テンプレートを保存しました。')
    } else {
      await createVisaGuarantorTemplate(templateForm.value)
      ElMessage.success('テンプレートを追加しました。')
    }
    resetTemplateForm()
    await fetchGuarantorTemplates()
  } catch {
    ElMessage.error('テンプレートの保存に失敗しました。')
  }
}

const deleteTemplate = async (template: VisaGuarantorTemplate) => {
  try {
    await ElMessageBox.confirm(`「${template.name}」を停止しますか？`, '停止確認', {
      confirmButtonText: '停止',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteVisaGuarantorTemplate(template.id)
    ElMessage.success('テンプレートを停止しました。')
    await fetchGuarantorTemplates()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('テンプレートの停止に失敗しました。')
    }
  }
}

const currentTemplate = computed(() =>
  guarantorTemplates.value.find((item) => item.id === selectedGuarantorTemplateId.value) ?? null)
const fieldSources = computed<Record<string, FieldSource>>(() =>
  guarantorSources(form.value as never, useTemplate.value ? currentTemplate.value : null))
const sourceTag = (key: string) => fieldSources.value[key] || ''

// テンプレートを選ぶと担保人の欄を埋める（どの欄がテンプレート由来かは fieldSources で示す）。
// 保存時は guarantor_template を送り、スナップショットは後端が DB のテンプレートから作る。
const applyGuarantorTemplate = (templateId?: number | string) => {
  const template = guarantorTemplates.value.find((item) => item.id === Number(templateId))
  if (!template) return
  form.value = applyGuarantorTemplateToForm(form.value as never, template) as VisaReturnForm
  form.value.guarantor_template = template.id
}

const resetForm = () => {
  editingId.value = null
  selectedGuarantorTemplateId.value = null
  flowStep.value = 0
  useTemplate.value = true
  checkResult.value = null
  lastGeneration.value = null
  generationError.value = null
  generations.value = []
  caseSourceId.value = null
  form.value = createEmptyForm()
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const openBatchDrawer = async () => {
  if (!guarantorTemplates.value.length) await fetchGuarantorTemplates()
  batchDrawerVisible.value = true
}

const openTemplatesFromBatch = async () => {
  batchDrawerVisible.value = false
  await openTemplateDrawer()
}

const openEditDialog = (application: VisaReturnApplication, step = 0) => {
  resetForm()
  editingId.value = application.id
  flowStep.value = step
  form.value = {
    applicant_name: application.applicant_name,
    nationality: application.nationality,
    birth_date: application.birth_date,
    gender: application.gender,
    marital_status: application.marital_status,
    passport_number: application.passport_number,
    passport_issue_date: application.passport_issue_date,
    passport_expiry_date: application.passport_expiry_date,
    residence_status: application.residence_status,
    address: application.address,
    phone: application.phone,
    email: application.email,
    occupation: application.occupation,
    guarantor_name: application.guarantor_name,
    guarantor_phone: application.guarantor_phone,
    guarantor_address: application.guarantor_address,
    guarantor_relationship: application.guarantor_relationship,
    guarantor_occupation: application.guarantor_occupation,
    guarantor_snapshot: {
      ...createEmptyForm().guarantor_snapshot,
      ...(application.guarantor_snapshot as Record<string, string>),
    },
    form_data: normalizeFormData(application.form_data as Record<string, unknown>),
    note: application.note,
  }
  formRef.value?.clearValidate()
  const snapshotId = Number((application.guarantor_snapshot as Record<string, unknown>)?.guarantor_template_id)
  const templateId = application.guarantor_template ?? (Number.isFinite(snapshotId) && snapshotId ? snapshotId : null)
  selectedGuarantorTemplateId.value = templateId
  form.value.guarantor_template = templateId
  useTemplate.value = Boolean(templateId)
  dialogVisible.value = true
}

// 一覧の「PDF 作成」：保存済みの内容でプレビュー（生成前の確認）から始める
const openForPdf = async (application: VisaReturnApplication) => {
  detailVisible.value = false
  openEditDialog(application, 3)
  await runCheck()
}

// 案件から申請人を読み込む（顧客の基本情報。既に入力した欄は空のときだけ埋める）
const loadFromCase = async (row: Case | null) => {
  if (!row?.customer) return
  try {
    const customer = await getCustomer((await getCase(row.id)).customer as number)
    const fill = (key: keyof VisaReturnForm, value?: string | null) => {
      if (value && !form.value[key]) (form.value as Record<string, unknown>)[key] = value
    }
    fill('applicant_name', customer.name)
    fill('birth_date', customer.birth_date)
    fill('nationality', customer.nationality)
    fill('passport_number', customer.passport_no)
    fill('passport_expiry_date', customer.passport_expiry)
    fill('phone', customer.phone)
    fill('address', customer.address)
    ElMessage.success('案件の顧客情報を読み込みました（空欄だけを埋めました）。')
  } catch {
    ElMessage.error('案件の顧客情報を読み込めませんでした。手入力で続けられます。')
  }
}

const saveApplication = async () => {
  const payload = buildPayload()
  if (editingId.value) {
    await updateVisaReturnApplication(editingId.value, payload)
  } else {
    const created = await createVisaReturnApplication(payload)
    editingId.value = created.id
  }
}

const runCheck = async () => {
  if (!editingId.value) return
  checking.value = true
  try {
    checkResult.value = await checkVisaReturnApplication(editingId.value)
    generations.value = await listVisaPdfGenerations(editingId.value)
  } catch (error) {
    generationError.value = visaErrorView(error)
  } finally {
    checking.value = false
  }
}

// PDF 生成からプレビューへ戻ったときは保存済みの内容で確認し直す（生成失敗の後に古い確認結果を見せない）
watch(flowStep, (step, previous) => {
  if (step === 3 && previous === 4) void runCheck()
})

// 次へ：段階ごとに足りない項目を先に示す。必要項目の確認からプレビューへ進むときに保存して後端で確認する
const nextStep = async () => {
  const problems = stepProblems(flowStep.value, form.value as never, useTemplate.value, selectedGuarantorTemplateId.value)
  if (problems.length) {
    ElMessage.warning(`次の項目を入力してください：${problems.join('、')}`)
    return
  }
  if (flowStep.value === 2) {
    submitting.value = true
    try {
      await saveApplication()
      await runCheck()
      flowStep.value = 3
      fetchApplications(currentPage.value)
    } catch (error) {
      const view = visaErrorView(error)
      ElMessage.error({ message: `${view.detail}${view.fields.length ? `（${view.fields.join('、')}）` : ''}`, duration: 6000 })
    } finally {
      submitting.value = false
    }
    return
  }
  if (flowStep.value === 3 && !checkResult.value?.ready) {
    ElMessage.warning('不足している項目を入力してから生成してください。')
    return
  }
  flowStep.value = Math.min(flowStep.value + 1, FLOW_STEPS.length - 1)
}

// PDF 生成：失敗しても入力内容はそのまま。成功しファイルが実在するときだけダウンロードを出す
const generatePdf = async () => {
  if (!editingId.value || generating.value) return
  generating.value = true
  generationError.value = null
  lastGeneration.value = null
  try {
    lastGeneration.value = await generateVisaReturnPdf(editingId.value)
    ElMessage.success('PDF を作成しました。')
  } catch (error) {
    generationError.value = visaErrorView(error)
  } finally {
    generating.value = false
    try {
      generations.value = await listVisaPdfGenerations(editingId.value)
    } catch {
      // 一覧の再取得に失敗しても生成結果の表示は残す
    }
  }
}

const downloadGeneration = async (generation: VisaPdfGeneration) => {
  if (!generation.download_url) return
  try {
    const { blob, contentDisposition } = await downloadVisaPdfGeneration(generation.download_url)
    saveBlob(blob, extractDownloadName(contentDisposition, 'visa_return.pdf'))
  } catch (error) {
    const view = visaErrorView(error)
    ElMessage.error({ message: `${view.title}：${view.detail}`, duration: 6000 })
    if (editingId.value) generations.value = await listVisaPdfGenerations(editingId.value).catch(() => generations.value)
  }
}

const openDetail = (application: VisaReturnApplication) => {
  selectedApplication.value = application
  detailVisible.value = true
}

const buildPayload = (): VisaReturnApplicationPayload => ({
  ...form.value,
  guarantor_template: useTemplate.value ? selectedGuarantorTemplateId.value : null,
  birth_date: form.value.birth_date || null,
  passport_issue_date: form.value.passport_issue_date || null,
  passport_expiry_date: form.value.passport_expiry_date || null,
  // guarantor_snapshot は後端が担保人テンプレートから作る（送っても使われない）
  guarantor_snapshot: undefined,
  form_data: { ...normalizeFormDataForPayload(form.value.form_data) },
})

const fillPdfTestData = () => {
  form.value = {
    ...form.value,
    applicant_name: '王小明',
    birth_date: '2000-01-01',
    gender: 'male',
    nationality: '中国',
    marital_status: 'single',
    passport_number: 'E12345678',
    passport_issue_date: '2023-01-01',
    passport_expiry_date: '2033-01-01',
    residence_status: '留学',
    phone: '13800000000',
    email: 'test@example.com',
    guarantor_name: '山田太郎',
    guarantor_phone: '06-1234-5678',
    guarantor_address: '大阪府大阪市天王寺区勝山四丁目七番三号',
    guarantor_occupation: '会社役員',
    guarantor_relationship: '知人',
    guarantor_snapshot: {
      guarantor_name_en: 'YAMADA TARO',
      guarantor_address_en: '4-7-3 Katsuyama, Tennoji-ku, Osaka-shi, Osaka',
      guarantor_birth_date: '1980-05-05',
      guarantor_nationality: '日本',
      guarantor_visa_status: '永住者',
    },
    form_data: {
      pinyin_name1: 'WANG',
      pinyin_name2: 'XIAOMING',
      chinese_name1: '王',
      chinese_name2: '小明',
      used_name1: 'なし',
      used_name2: '无',
      othernationality: '无',
      birth_place: '中国上海市',
      chinese_id: '310101200001010011',
      passport_address: '上海',
      passport_a: '中华人民共和国出入境管理局',
      zailiu_number: 'COE202607060001',
      entry_port: '関西国際空港',
      airline: '日本航空 JL898',
      entry_time1: '2026-08-01',
      entry_time2: '2026-10-29',
      entry_time3: '90日',
      registered_address: '中国上海市浦東新区世紀大道90号',
      current_address: '中国上海市浦東新区世紀大道100号',
      home_address2: '中国上海市浦東新区世紀大道100号',
      home_phone: '021-1234-5678',
      workplace_name: '上海国際大学',
      workplace_address: '中国上海市徐匯区学院路88号',
      workplace_phone: '021-8888-6666',
      hotel: '山田太郎',
      hotel_phone: '06-1234-5678',
      hotel_address: '大阪府大阪市天王寺区勝山四丁目七番三号',
      last: '2024年4月1日から2024年4月10日まで',
      job_title2: '学生',
      guarantor_name_en: 'YAMADA TARO',
      guarantor_address_en: '4-7-3 Katsuyama, Tennoji-ku, Osaka-shi, Osaka',
      guarantor_birth_date: '1980-05-05',
      guarantor_nationality: '日本',
      guarantor_visa_status: '永住者',
      gender2: 'male',
      same: '同上',
      x1: 'no',
      x2: 'no',
      x3: 'no',
      x4: 'no',
      x5: 'no',
      x6: 'no',
    },
  }
  ElMessage.success('PDFテストデータを入力しました。')
}

const submitApplication = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingId.value) {
      await updateVisaReturnApplication(editingId.value, buildPayload())
      ElMessage.success('返签 visa 表を更新しました。')
    } else {
      await createVisaReturnApplication(buildPayload())
      ElMessage.success('返签 visa 表を作成しました。')
    }
    dialogVisible.value = false
    await fetchApplications(editingId.value ? currentPage.value : 1)
  } catch (error) {
    const view = visaErrorView(error)
    ElMessage.error({ message: view.detail || (editingId.value ? '更新に失敗しました。' : '作成に失敗しました。'), duration: 6000 })
  } finally {
    submitting.value = false
  }
}

const confirmDelete = async (application: VisaReturnApplication) => {
  try {
    await ElMessageBox.confirm(
      `「${application.applicant_name || application.passport_number || application.id}」を削除しますか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteVisaReturnApplication(application.id)
    ElMessage.success('削除しました。')
    await fetchApplications(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('削除に失敗しました。')
    }
  }
}

const handleActionCommand = (application: VisaReturnApplication, command: string) => {
  if (command === 'detail') openDetail(application)
  if (command === 'edit') openEditDialog(application)
  if (command === 'pdf') openForPdf(application)
  if (command === 'delete') confirmDelete(application)
}

const detailRows = computed(() => {
  const application = selectedApplication.value
  if (!application) return []
  return [
    ['申請人姓名', application.applicant_name],
    ['国籍', application.nationality],
    ['生年月日', application.birth_date ? formatDate(application.birth_date) : '-'],
    ['性別', genderLabel(application.gender)],
    ['婚姻状況', maritalStatusLabel(application.marital_status)],
    ['パスポート番号', application.passport_number],
    ['在留資格', application.residence_status],
    ['住所', application.address],
    ['電話番号', application.phone],
    ['メール', application.email],
    ['職業', application.occupation],
    ['保証人氏名', application.guarantor_name],
    ['保証人電話番号', application.guarantor_phone],
    ['保証人住所', application.guarantor_address],
    ['申請人との関係', application.guarantor_relationship],
    ['保証人職業', application.guarantor_occupation],
    ['備考', application.note],
  ]
})

onMounted(() => {
  fetchApplications()
  fetchGuarantorTemplates()
})
</script>

<template>
  <section class="accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>返签 visa 表作成</h1>
          <p>申請人 → 担保人テンプレート → 必要項目 → プレビュー → PDF 生成 の順に進めます。</p>
        </div>
        <div class="accounting-toolbar">
          <el-button type="primary" @click="openCreateDialog">返签 visa 表を作成</el-button>
          <el-button @click="openTemplateDrawer">在日担保人テンプレート</el-button>
          <el-dropdown trigger="click">
            <el-button>まとめて作成<el-icon><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="importDrawerVisible = true">CSV / Excel から一括作成</el-dropdown-item>
                <el-dropdown-item @click="openBatchDrawer">貼り付けで複数名を作成</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <div class="visa-quick-flow" aria-label="作成の流れ">
      <div v-for="(label, index) in FLOW_STEPS" :key="label"><strong>{{ index + 1 }}. {{ label }}</strong></div>
    </div>

    <el-card class="accounting-filter-card" shadow="never">
      <div class="filter-title">検索条件</div>
      <div class="accounting-filter-row">
        <el-input
          v-model="filters.search"
          clearable
          placeholder="申請人姓名・旅券番号・電話番号"
          class="accounting-filter-search"
          @keyup.enter="fetchApplications(1)"
        />
        <div class="accounting-filter-actions">
          <el-button type="primary" @click="fetchApplications(1)">検索</el-button>
          <el-button
            @click="() => {
              filters.search = ''
              fetchApplications(1)
            }"
          >
            リセット
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="accounting-card" shadow="never">
      <el-table v-loading="loading" :data="applications" stripe>
        <el-table-column label="申請人姓名" min-width="160">
          <template #default="{ row }">{{ row.applicant_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="国籍" width="110">
          <template #default="{ row }">{{ row.nationality || '-' }}</template>
        </el-table-column>
        <el-table-column label="旅券番号" min-width="140">
          <template #default="{ row }">{{ row.passport_number || '-' }}</template>
        </el-table-column>
        <el-table-column label="在留資格" min-width="150">
          <template #default="{ row }">{{ row.residence_status || '-' }}</template>
        </el-table-column>
        <el-table-column label="電話番号" min-width="140">
          <template #default="{ row }">{{ row.phone || '-' }}</template>
        </el-table-column>
        <el-table-column label="保証人" min-width="150">
          <template #default="{ row }">{{ row.guarantor_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="更新日時" width="150">
          <template #default="{ row }">{{ row.updated_at ? formatDate(row.updated_at) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click" @command="handleActionCommand(row, $event)">
              <el-button text type="primary" class="table-action-trigger">
                操作
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="detail">詳細</el-dropdown-item>
                  <el-dropdown-item command="edit">編集</el-dropdown-item>
                  <el-dropdown-item command="pdf">PDF 作成</el-dropdown-item>
                  <el-dropdown-item command="delete" divided class="danger-item">削除</el-dropdown-item>
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
          @current-change="fetchApplications"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '返签 visa 表' : '返签 visa 表を作成'"
      width="min(900px, 96vw)"
      class="accounting-expense-dialog"
      @closed="resetForm"
    >
      <el-steps :active="flowStep" finish-status="success" simple class="visa-flow-steps">
        <el-step v-for="label in FLOW_STEPS" :key="label" :title="label" />
      </el-steps>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div v-if="auth.devToolsEnabled && flowStep === 0" class="accounting-toolbar visa-return-test-toolbar">
          <el-button plain size="small" @click="fillPdfTestData">PDFテストデータ入力（開発用）</el-button>
        </div>

        <!-- 1. 申請人 -->
        <div v-show="flowStep === 0" class="visa-return-form">
          <el-form-item label="案件から読み込む（任意）" class="visa-return-full">
            <RemoteCaseSelect v-model="caseSourceId" clearable placeholder="案件を選ぶと顧客の基本情報で空欄を埋めます" @change="loadFromCase" />
          </el-form-item>
          <el-form-item label="申請人氏名" prop="applicant_name" required><el-input v-model="form.applicant_name" /></el-form-item>
          <el-form-item label="国籍" required><el-input v-model="form.nationality" /></el-form-item>
          <el-form-item label="英文姓" required><el-input v-model="form.form_data.pinyin_name1" placeholder="PDF の氏名欄（中文姓でも可）" /></el-form-item>
          <el-form-item label="英文名"><el-input v-model="form.form_data.pinyin_name2" /></el-form-item>
          <el-form-item label="生年月日" required>
            <el-date-picker v-model="form.birth_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="性別">
            <el-select v-model="form.gender" class="form-control">
              <el-option v-for="option in genderOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="パスポート番号" required><el-input v-model="form.passport_number" /></el-form-item>
          <el-form-item label="パスポート期限" required>
            <el-date-picker v-model="form.passport_expiry_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="電話番号"><el-input v-model="form.phone" /></el-form-item>
          <el-form-item label="在留資格"><el-input v-model="form.residence_status" /></el-form-item>
        </div>

        <!-- 2. 担保人テンプレート -->
        <div v-show="flowStep === 1" class="visa-return-form">
          <div class="visa-return-full visa-template-choice">
            <el-radio-group v-model="useTemplate">
              <el-radio :value="true">担保人テンプレートを使う（推奨）</el-radio>
              <el-radio :value="false">テンプレートを使わず手入力する</el-radio>
            </el-radio-group>
          </div>
          <el-form-item v-if="useTemplate" label="在日担保人テンプレート" class="visa-return-full" required>
            <el-select v-model="selectedGuarantorTemplateId" filterable class="form-control" placeholder="テンプレートを選択"
                       @change="applyGuarantorTemplate">
              <el-option v-for="template in guarantorTemplates.filter((item) => item.is_active || item.id === selectedGuarantorTemplateId)"
                         :key="template.id" :label="template.name" :value="template.id" />
            </el-select>
            <div class="field-hint">選ぶと下の欄に担保人の情報が入ります。変更した欄は「手入力」として扱います。
              <el-button link type="primary" size="small" @click="openTemplateDrawer">テンプレートを管理</el-button></div>
          </el-form-item>
          <el-form-item v-for="field in [
            { key: 'guarantor_name', label: '担保人氏名', fd: false, required: true },
            { key: 'guarantor_name_en', label: '担保人氏名（英字）', fd: true, required: false },
            { key: 'guarantor_phone', label: '電話番号', fd: false, required: true },
            { key: 'guarantor_relationship', label: '申請人との関係', fd: false, required: false },
            { key: 'guarantor_occupation', label: '職業', fd: false, required: false },
            { key: 'guarantor_nationality', label: '国籍', fd: true, required: false },
            { key: 'guarantor_visa_status', label: '在留資格', fd: true, required: false },
            { key: 'guarantor_birth_date', label: '生年月日', fd: true, required: false },
          ]" :key="field.key" :required="field.required">
            <template #label>
              {{ field.label }}
              <el-tag v-if="sourceTag(field.key)" size="small" :type="sourceTag(field.key) === 'template' ? 'success' : 'warning'" effect="plain">
                {{ SOURCE_LABELS[sourceTag(field.key)] }}
              </el-tag>
            </template>
            <el-input v-if="field.fd" v-model="(form.form_data as Record<string, string>)[field.key]" />
            <el-input v-else v-model="(form as unknown as Record<string, string>)[field.key]" />
          </el-form-item>
          <el-form-item class="visa-return-full" required>
            <template #label>担保人住所 <el-tag v-if="sourceTag('guarantor_address')" size="small" :type="sourceTag('guarantor_address') === 'template' ? 'success' : 'warning'" effect="plain">{{ SOURCE_LABELS[sourceTag('guarantor_address')] }}</el-tag></template>
            <el-input v-model="form.guarantor_address" />
          </el-form-item>
          <el-form-item class="visa-return-full">
            <template #label>担保人住所（英字） <el-tag v-if="sourceTag('guarantor_address_en')" size="small" :type="sourceTag('guarantor_address_en') === 'template' ? 'success' : 'warning'" effect="plain">{{ SOURCE_LABELS[sourceTag('guarantor_address_en')] }}</el-tag></template>
            <el-input v-model="form.form_data.guarantor_address_en" />
          </el-form-item>
        </div>

        <!-- 3. 必要項目の確認（常用項目を先に、詳細項目は折りたたみ） -->
        <div v-show="flowStep === 2">
          <div class="visa-return-form">
            <el-form-item label="婚姻状況">
              <el-select v-model="form.marital_status" class="form-control">
                <el-option v-for="option in maritalStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="職業"><el-input v-model="form.occupation" /></el-form-item>
            <el-form-item label="预定入境日"><el-input v-model="form.form_data.entry_time1" placeholder="例：2026-08-01" /></el-form-item>
            <el-form-item label="预定离境日"><el-input v-model="form.form_data.entry_time2" placeholder="例：2026-10-29" /></el-form-item>
            <el-form-item label="预定滞在期间"><el-input v-model="form.form_data.entry_time3" placeholder="例：90日" /></el-form-item>
            <el-form-item label="入境口岸"><el-input v-model="form.form_data.entry_port" /></el-form-item>
            <el-form-item label="现住址" class="visa-return-full"><el-input v-model="form.form_data.current_address" /></el-form-item>
            <el-form-item label="日本滞在先名称"><el-input v-model="form.form_data.hotel" /></el-form-item>
            <el-form-item label="日本滞在先电话"><el-input v-model="form.form_data.hotel_phone" /></el-form-item>
            <el-form-item label="日本滞在先地址" class="visa-return-full"><el-input v-model="form.form_data.hotel_address" /></el-form-item>
          </div>
          <el-collapse class="visa-advanced">
            <el-collapse-item title="詳細項目（必要なときだけ）" name="advanced">
              <div class="visa-return-form">
                <el-form-item label="住所（日本語表記）" class="visa-return-full"><el-input v-model="form.address" /></el-form-item>
                <el-form-item label="メール"><el-input v-model="form.email" /></el-form-item>
          <el-form-item label="パスポート発行日">
            <el-date-picker v-model="form.passport_issue_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="パスポート期限">
            <el-date-picker v-model="form.passport_expiry_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="在留資格">
            <el-input v-model="form.residence_status" />
          </el-form-item>
          <el-form-item label="中国身份证号码">
            <el-input v-model="form.form_data.chinese_id" />
          </el-form-item>
          <el-form-item label="护照签发地">
            <el-input v-model="form.form_data.passport_address" />
          </el-form-item>
          <el-form-item label="护照签发机关">
            <el-input v-model="form.form_data.passport_a" />
          </el-form-item>
          <el-form-item label="在留番号">
            <el-input v-model="form.form_data.zailiu_number" />
          </el-form-item>

                    <el-form-item label="中文 姓">
            <el-input v-model="form.form_data.chinese_name1" />
          </el-form-item>
          <el-form-item label="中文 名">
            <el-input v-model="form.form_data.chinese_name2" />
          </el-form-item>
          <el-form-item label="曾用名英文">
            <el-input v-model="form.form_data.used_name1" />
          </el-form-item>
          <el-form-item label="曾用名中文">
            <el-input v-model="form.form_data.used_name2" />
          </el-form-item>
          <el-form-item label="其他国籍">
            <el-input v-model="form.form_data.othernationality" />
          </el-form-item>
          <el-form-item label="出生地">
            <el-input v-model="form.form_data.birth_place" />
          </el-form-item>
          <el-form-item label="航空会社 / 便名">
            <el-input v-model="form.form_data.airline" />
          </el-form-item>
          <el-form-item label="本国电话">
            <el-input v-model="form.form_data.home_phone" />
          </el-form-item>
          <el-form-item label="户籍地址" class="visa-return-full">
            <el-input v-model="form.form_data.registered_address" />
          </el-form-item>
          <el-form-item label="工作单位 / 学校">
            <el-input v-model="form.form_data.workplace_name" />
          </el-form-item>
          <el-form-item label="工作单位 / 学校电话">
            <el-input v-model="form.form_data.workplace_phone" />
          </el-form-item>
          <el-form-item label="工作单位 / 学校地址" class="visa-return-full">
            <el-input v-model="form.form_data.workplace_address" />
          </el-form-item>
          <el-form-item label="上次赴日记录" class="visa-return-full">
            <el-input v-model="form.form_data.last" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="职业 / 身份补足">
            <el-input v-model="form.form_data.job_title2" />
          </el-form-item>
          <el-form-item label="邀请人信息同上">
            <el-input v-model="form.form_data.same" />
          </el-form-item>

          <el-form-item label="保証人性別">
            <el-select v-model="form.form_data.gender2" class="form-control">
              <el-option v-for="option in genderOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <div class="visa-return-checks visa-return-full">
            <span>Page2 確認項目</span>
            <el-select v-model="form.form_data.x1" size="small" class="visa-return-yes-no">
              <el-option v-for="option in yesNoOptions" :key="option.value" :label="`x1：${option.label}`" :value="option.value" />
            </el-select>
            <el-select v-model="form.form_data.x2" size="small" class="visa-return-yes-no">
              <el-option v-for="option in yesNoOptions" :key="option.value" :label="`x2：${option.label}`" :value="option.value" />
            </el-select>
            <el-select v-model="form.form_data.x3" size="small" class="visa-return-yes-no">
              <el-option v-for="option in yesNoOptions" :key="option.value" :label="`x3：${option.label}`" :value="option.value" />
            </el-select>
            <el-select v-model="form.form_data.x4" size="small" class="visa-return-yes-no">
              <el-option v-for="option in yesNoOptions" :key="option.value" :label="`x4：${option.label}`" :value="option.value" />
            </el-select>
            <el-select v-model="form.form_data.x5" size="small" class="visa-return-yes-no">
              <el-option v-for="option in yesNoOptions" :key="option.value" :label="`x5：${option.label}`" :value="option.value" />
            </el-select>
            <el-select v-model="form.form_data.x6" size="small" class="visa-return-yes-no">
              <el-option v-for="option in yesNoOptions" :key="option.value" :label="`x6：${option.label}`" :value="option.value" />
            </el-select>
          </div>
              </div>
            </el-collapse-item>
          </el-collapse>
          <el-form-item label="備考"><el-input v-model="form.note" type="textarea" :rows="2" /></el-form-item>
        </div>

        <!-- 4. プレビュー（保存済みの内容を後端で確認） -->
        <div v-show="flowStep === 3" v-loading="checking">
          <template v-if="checkResult">
            <el-alert v-if="checkResult.missing.length" type="error" show-icon :closable="false" title="次の項目が足りないため、まだ生成できません。">
              <ul class="visa-missing"><li v-for="item in checkResult.missing" :key="item.field">{{ item.label }}</li></ul>
              <el-button size="small" @click="flowStep = 0">申請人へ戻る</el-button>
              <el-button size="small" @click="flowStep = 1">担保人へ戻る</el-button>
            </el-alert>
            <el-alert v-else type="success" show-icon :closable="false" title="必要な項目はそろっています。内容を確認して PDF を生成してください。" />
            <el-alert v-if="checkResult.guarantor_template.updated_since_selected" type="warning" show-icon :closable="false"
                      title="選択後に担保人テンプレートが更新されています。最新の内容にする場合は担保人の段階でテンプレートを選び直してください。" />
            <div class="visa-preview-meta">
              <span>担保人テンプレート：{{ checkResult.guarantor_template.name || 'なし（手入力）' }}</span>
              <span>PDF の作り方：{{ checkResult.pdf_template.method === 'form' ? 'フォーム項目へ入力' : checkResult.pdf_template.method === 'coordinates' ? '座標へ描画' : '（テンプレートがありません）' }}</span>
            </div>
            <el-table :data="checkResult.fields" size="small" border>
              <el-table-column label="項目" prop="label" width="180" />
              <el-table-column label="値" min-width="220"><template #default="{ row }">{{ row.value || '—' }}</template></el-table-column>
              <el-table-column label="出所" width="120">
                <template #default="{ row }">
                  <el-tag size="small" effect="plain" :type="row.source === 'template' ? 'success' : row.source === 'manual' ? 'warning' : 'info'">
                    {{ SOURCE_LABELS[row.source] || '申請人' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </div>

        <!-- 5. PDF 生成 -->
        <div v-show="flowStep === 4" class="visa-generate">
          <el-alert v-if="generationError" type="error" show-icon :closable="false" :title="generationError.title">
            <div>{{ generationError.detail }}</div>
            <ul v-if="generationError.fields.length" class="visa-missing"><li v-for="f in generationError.fields.slice(0, 20)" :key="f">{{ f }}</li></ul>
            <div class="field-hint">入力内容はそのまま残っています。修正してから「もう一度生成」を押してください。</div>
          </el-alert>
          <el-alert v-if="lastGeneration?.download_url" type="success" show-icon :closable="false" title="PDF を作成しました。">
            <div>作り方：{{ lastGeneration.method_display }}／テンプレートの版：{{ lastGeneration.template_version }}／担保人テンプレート：{{ lastGeneration.guarantor_template_name || 'なし（手入力）' }}</div>
            <el-button type="primary" size="small" @click="downloadGeneration(lastGeneration)">PDF をダウンロード</el-button>
          </el-alert>
          <el-button type="primary" :loading="generating" @click="generatePdf">{{ generationError || lastGeneration ? 'もう一度生成' : 'PDF を生成' }}</el-button>
          <div v-if="generations.length" class="visa-generations">
            <div class="form-section-title">生成記録</div>
            <el-table :data="generations" size="small">
              <el-table-column label="日時" width="160"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
              <el-table-column label="結果" width="80"><template #default="{ row }"><el-tag size="small" :type="row.status === 'success' ? 'success' : 'danger'">{{ row.status_display }}</el-tag></template></el-table-column>
              <el-table-column label="内容" min-width="240"><template #default="{ row }">{{ row.status === 'success' ? `${row.method_display}・版 ${row.template_version}` : row.error_message }}</template></el-table-column>
              <el-table-column label="" width="110">
                <template #default="{ row }"><el-button v-if="row.download_url" link type="primary" @click="downloadGeneration(row)">ダウンロード</el-button></template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">閉じる</el-button>
        <el-button v-if="flowStep > 0" @click="flowStep -= 1">戻る</el-button>
        <el-button v-if="flowStep <= 2" :loading="submitting" @click="submitApplication">保存して閉じる</el-button>
        <el-button v-if="flowStep < 4" type="primary" :loading="submitting" @click="nextStep">
          {{ flowStep === 2 ? '保存してプレビュー' : flowStep === 3 ? 'PDF 生成へ' : '次へ' }}
        </el-button>
      </template>
    </el-dialog>

    <VisaImportDrawer v-model="importDrawerVisible" @imported="fetchApplications(1)" />
    <VisaReturnBatchDrawer
      v-model="batchDrawerVisible"
      :guarantor-templates="guarantorTemplates"
      @saved="fetchApplications(1)"
      @manage-templates="openTemplatesFromBatch"
    />

    <el-drawer v-model="templateDrawerVisible" title="在日担保人模板管理" size="760px">
      <div class="visa-template-drawer">
        <el-card shadow="never" class="accounting-card">
          <el-form ref="templateFormRef" :model="templateForm" label-position="top">
            <div class="visa-return-form">
              <el-form-item label="模板名称" class="visa-return-full">
                <el-input v-model="templateForm.name" />
              </el-form-item>
              <el-form-item label="保証人氏名">
                <el-input v-model="templateForm.guarantor_name" />
              </el-form-item>
              <el-form-item label="英文姓名">
                <el-input v-model="templateForm.guarantor_name_en" />
              </el-form-item>
              <el-form-item label="電話番号">
                <el-input v-model="templateForm.guarantor_phone" />
              </el-form-item>
              <el-form-item label="出生日期">
                <el-date-picker v-model="templateForm.guarantor_birth_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
              </el-form-item>
              <el-form-item label="国籍">
                <el-input v-model="templateForm.guarantor_nationality" />
              </el-form-item>
              <el-form-item label="签证种类 / 在留資格">
                <el-input v-model="templateForm.guarantor_visa_status" />
              </el-form-item>
              <el-form-item label="職業 / 職務">
                <el-input v-model="templateForm.guarantor_occupation" />
              </el-form-item>
              <el-form-item label="与申请人的关系">
                <el-input v-model="templateForm.guarantor_relationship" />
              </el-form-item>
              <el-form-item label="会社名">
                <el-input v-model="templateForm.guarantor_company_name" />
              </el-form-item>
              <el-form-item label="排序">
                <el-input v-model.number="templateForm.sort_order" type="number" />
              </el-form-item>
              <el-form-item label="日文地址" class="visa-return-full">
                <el-input v-model="templateForm.guarantor_address" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="英文地址" class="visa-return-full">
                <el-input v-model="templateForm.guarantor_address_en" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="备注" class="visa-return-full">
                <el-input v-model="templateForm.note" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="有効">
                <el-switch v-model="templateForm.is_active" />
              </el-form-item>
            </div>
          </el-form>
          <div class="accounting-toolbar visa-return-template-actions">
            <el-button type="primary" @click="submitTemplate">{{ editingTemplateId ? '保存' : '追加' }}</el-button>
            <el-button @click="resetTemplateForm">クリア</el-button>
          </div>
        </el-card>

        <el-card shadow="never" class="accounting-card">
          <div class="accounting-filter-row">
            <el-input
              v-model="templateSearch"
              clearable
              placeholder="名称・保証人氏名・電話番号"
              class="accounting-filter-search"
              @keyup.enter="fetchGuarantorTemplates"
            />
            <div class="accounting-filter-actions">
              <el-button type="primary" @click="fetchGuarantorTemplates">検索</el-button>
              <el-button
                @click="() => {
                  templateSearch = ''
                  fetchGuarantorTemplates()
                }"
              >
                リセット
              </el-button>
            </div>
          </div>
          <el-table v-loading="templateLoading" :data="guarantorTemplates" stripe>
            <el-table-column label="模板名称" min-width="160">
              <template #default="{ row }">{{ row.name }}</template>
            </el-table-column>
            <el-table-column label="保証人" min-width="150">
              <template #default="{ row }">{{ row.guarantor_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="電話番号" min-width="130">
              <template #default="{ row }">{{ row.guarantor_phone || '-' }}</template>
            </el-table-column>
            <el-table-column label="有効" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '有効' : '停止' }}</el-tag>
              </template>
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
                      <el-dropdown-item @click="editTemplate(row)">編集</el-dropdown-item>
                      <el-dropdown-item divided class="danger-item" :disabled="!row.is_active" @click="deleteTemplate(row)">停止</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </el-drawer>

    <el-drawer v-model="detailVisible" title="返签 visa 表 詳細" size="520px">
      <div v-if="selectedApplication" class="visa-return-detail">
        <div v-for="[label, value] in detailRows" :key="label" class="visa-return-detail-row">
          <span>{{ label }}</span>
          <strong>{{ value || '-' }}</strong>
        </div>
        <div class="accounting-toolbar visa-return-detail-actions">
          <el-button type="primary" @click="openForPdf(selectedApplication)">PDF 作成</el-button>
          <el-button @click="openEditDialog(selectedApplication)">編集</el-button>
        </div>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.visa-return-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.visa-quick-flow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}

.visa-quick-flow > div {
  display: flex;
  min-height: 70px;
  flex-direction: column;
  justify-content: center;
  padding: 13px 16px;
  border: 1px solid rgba(170, 212, 244, 0.58);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.88);
}

.visa-quick-flow strong {
  color: var(--sunrise-text);
  font-size: 13px;
}

.visa-quick-flow span {
  margin-top: 4px;
  color: var(--sunrise-muted);
  font-size: 12px;
}

.visa-return-full {
  grid-column: 1 / -1;
}

.visa-flow-steps {
  margin-bottom: 16px;
}

.visa-template-choice {
  margin-bottom: 8px;
}

.visa-advanced {
  margin: 8px 0 12px;
}

.visa-missing {
  margin: 4px 0 8px;
  padding-left: 18px;
}

.visa-preview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 20px;
  margin: 12px 0 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.visa-generate {
  display: grid;
  gap: 12px;
  justify-items: start;
}

.visa-generate > .el-alert,
.visa-generations {
  width: 100%;
}

.visa-return-test-toolbar {
  justify-content: flex-start;
  margin-bottom: 14px;
}

.visa-return-checks {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
  min-height: 38px;
  padding: 8px 0 18px;
}

.visa-return-checks span {
  color: var(--sunrise-muted);
  font-size: 13px;
  font-weight: 700;
}

.visa-return-yes-no {
  width: 96px;
}

.visa-template-drawer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.visa-return-template-actions {
  justify-content: flex-start;
}

.visa-return-detail {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.visa-return-detail-row {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(170, 212, 244, 0.35);
}

.visa-return-detail-row span {
  color: var(--sunrise-muted);
  font-size: 13px;
  font-weight: 700;
}

.visa-return-detail-row strong {
  color: var(--sunrise-text);
  font-size: 14px;
  font-weight: 700;
  white-space: pre-wrap;
}

.visa-return-detail-actions {
  justify-content: flex-start;
  margin-top: 16px;
}

@media (max-width: 720px) {
  .visa-quick-flow,
  .visa-return-form,
  .visa-return-detail-row {
    grid-template-columns: 1fr;
  }
}
</style>
