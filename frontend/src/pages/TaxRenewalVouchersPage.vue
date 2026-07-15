<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listCompanies } from '../api/companies'
import { listCustomers } from '../api/customers'
import { listEmployees } from '../api/employees'
import {
  createTaxRenewalAgentTemplate,
  createTaxRenewalRecord,
  deleteTaxRenewalAgentTemplate,
  deleteTaxRenewalRecord,
  downloadTaxRenewalNumberedSample,
  generateTaxRenewalRecordPdf,
  listTaxRenewalPdfDiagnostics,
  listTaxRenewalAgentTemplates,
  listTaxRenewalRecords,
  listTaxRenewalTemplates,
  updateTaxRenewalAgentTemplate,
  updateTaxRenewalRecord,
} from '../api/accounting'
import type { Company, Customer, Employee } from '../types/api'
import type {
  TaxRenewalAgentTemplate,
  TaxRenewalAgentTemplatePayload,
  TaxRenewalCategory,
  TaxRenewalFormData,
  TaxRenewalPdfDiagnostic,
  TaxRenewalTemplate,
  TaxRenewalVoucherPayload,
  TaxRenewalVoucherRecord,
} from '../types/accounting'
import './accounting/accounting.css'

const records = ref<TaxRenewalVoucherRecord[]>([])
const templates = ref<TaxRenewalTemplate[]>([])
const agentTemplates = ref<TaxRenewalAgentTemplate[]>([])
const companies = ref<Company[]>([])
const customers = ref<Customer[]>([])
const employees = ref<Employee[]>([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const drawerVisible = ref(false)
const agentDialogVisible = ref(false)
const diagnosticsVisible = ref(false)
const agentSaving = ref(false)
const diagnosticsLoading = ref(false)
const editingId = ref<number | null>(null)
const editingAgentId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const deletingAgentId = ref<number | null>(null)
const generatingId = ref<number | null>(null)
const sampleGeneratingKey = ref<string | null>(null)
const fiscalPeriod = ref<string[]>([])
const diagnostics = ref<TaxRenewalPdfDiagnostic[]>([])
const SOCIAL_INSURANCE_TEMPLATE_KEY = 'social_insurance_payment_certificate_power_of_attorney'

const fieldLabels: Record<string, string> = {
  company_name: '会社名',
  company_number: '法人番号',
  company_address: '事業所所在地',
  company_phone: '会社電話',
  representative_name: '事業主氏名',
  representative_kana: '代表者カナ',
  representative_birth_date: '代表者生年月日',
  representative_position: '代表者肩書',
  establishment_symbol: '記号',
  establishment_number: '事業所番号',
  applicant_name: '申請人氏名',
  applicant_kana: '申請人カナ',
  applicant_address: '申請人住所',
  applicant_phone: '申請人電話',
  applicant_birth_date: '申請人生年月日',
  agent_name: '代理人氏名',
  agent_kana: '代理人カナ',
  agent_address: '代理人住所',
  agent_phone: '代理人電話',
  agent_company_name: '代理会社名',
  agent_position: '代理人職務',
  agent_relationship: '委任者との関係',
  fiscal_period_start: '決算期間開始日',
  fiscal_period_end: '決算期間終了日',
  fiscal_year: '年度',
  tax_office_name: '税務署名',
  osaka_city_ward: '大阪市区',
  osaka_prefecture_office: '大阪府税事務所',
  certificate_type: '証明書種類',
  quantity: '請求枚数',
  application_reason: '申請事由',
  submit_date: '提出日',
  employee_name: '员工姓名',
  employee_kana: '员工カナ',
  employee_birth_date: '员工生年月日',
  employee_address: '员工住所',
  employee_phone: '员工電話',
  employee_my_number: '员工 My Number',
  employment_start_date: '入职日',
  salary_amount: '薪资',
  dependents: '扶養人',
}

const fieldGroups = [
  {
    name: 'company',
    title: '公司信息',
    fields: [
      'company_name',
      'company_number',
      'company_address',
      'company_phone',
      'representative_name',
      'representative_kana',
      'representative_birth_date',
      'representative_position',
      'establishment_symbol',
      'establishment_number',
    ],
  },
  {
    name: 'applicant',
    title: '申请人信息',
    fields: ['applicant_name', 'applicant_kana', 'applicant_address', 'applicant_phone', 'applicant_birth_date'],
  },
  {
    name: 'agent',
    title: '代理人信息',
    fields: [
      'agent_name',
      'agent_kana',
      'agent_address',
      'agent_phone',
      'agent_company_name',
      'agent_position',
      'agent_relationship',
    ],
  },
  {
    name: 'fiscal',
    title: '年度 / 决算期间',
    fields: ['fiscal_period_start', 'fiscal_period_end', 'fiscal_year'],
  },
  {
    name: 'tax',
    title: '税务信息',
    fields: [
      'tax_office_name',
      'osaka_city_ward',
      'osaka_prefecture_office',
      'certificate_type',
      'quantity',
      'application_reason',
      'submit_date',
    ],
  },
  {
    name: 'employee',
    title: '员工信息',
    fields: [
      'employee_name',
      'employee_kana',
      'employee_birth_date',
      'employee_address',
      'employee_phone',
      'employee_my_number',
      'employment_start_date',
      'salary_amount',
    ],
  },
  {
    name: 'dependents',
    title: '抚养人信息',
    fields: ['dependents'],
  },
]

const query = reactive({
  page: 1,
  page_size: 20,
  search: '',
})

const agentQuery = reactive({
  page: 1,
  page_size: 100,
  search: '',
})

const emptyFormData = (): TaxRenewalFormData => ({
  company_name: '',
  company_number: '',
  company_address: '',
  company_phone: '',
  representative_name: '',
  representative_kana: '',
  representative_birth_date: null,
  applicant_name: '',
  applicant_kana: '',
  applicant_address: '',
  applicant_phone: '',
  applicant_birth_date: null,
  agent_template_id: null,
  agent_snapshot: null,
  agent_name: '',
  agent_kana: '',
  agent_address: '',
  agent_phone: '',
  agent_company_name: '',
  agent_position: '',
  tax_office_name: '',
  osaka_city_ward: '',
  osaka_prefecture_office: '',
  fiscal_year: '',
  fiscal_period_start: null,
  fiscal_period_end: null,
  fiscal_start_year: null,
  fiscal_start_month: null,
  fiscal_start_day: null,
  fiscal_end_year: null,
  fiscal_end_month: null,
  fiscal_end_day: null,
  fiscal_start_year_jp: '',
  fiscal_end_year_jp: '',
  certificate_type: '',
  quantity: '',
  employee_name: '',
  employee_kana: '',
  employee_birth_date: null,
  employee_address: '',
  employee_phone: '',
  employee_my_number: '',
  employment_start_date: null,
  salary_amount: '',
  establishment_symbol: '',
  establishment_number: '',
  social_insurance_symbol: '',
  social_insurance_office_number: '',
  application_reason: '',
  representative_position: '',
  agent_relationship: '',
  dependents: [],
  submit_date: null,
  note: '',
})

const form = reactive<TaxRenewalVoucherPayload>({
  title: '',
  category: 'renewal',
  company: null,
  customer: null,
  employee: null,
  status: 'draft',
  has_employees: false,
  has_dependents: false,
  selected_templates: [],
  form_data: emptyFormData(),
  generated_files: [],
  note: '',
})

const agentForm = reactive<TaxRenewalAgentTemplatePayload>({
  name: '',
  agent_name: '',
  agent_kana: '',
  agent_address: '',
  agent_phone: '',
  agent_company_name: '',
  agent_position: '',
  note: '',
  is_active: true,
  sort_order: 0,
})

const categoryLabel = (category: TaxRenewalCategory) => (category === 'renewal' ? '更新用' : '年金加入')

const filteredTemplates = computed(() =>
  templates.value
    .filter((template) => template.category === form.category)
    .sort((a, b) => a.order - b.order),
)

const selectedCompany = computed(() => companies.value.find((company) => company.id === form.company))
const selectedCustomer = computed(() => customers.value.find((customer) => customer.id === form.customer))
const selectedEmployee = computed(() => employees.value.find((employee) => employee.id === form.employee))

const unavailableReason = (template: TaxRenewalTemplate) => {
  if (!template.file_exists) return '模板文件不存在'
  if (template.condition === 'has_employees' && !form.has_employees) return '只有公司有雇员时才填写'
  if (template.condition === 'has_dependents' && !form.has_dependents) return '只有有抚养人时才填写'
  return ''
}

const templateDisabled = (template: TaxRenewalTemplate) => Boolean(unavailableReason(template))
const hasSocialInsuranceTemplate = (record: TaxRenewalVoucherRecord) =>
  (record.selected_templates || []).includes(SOCIAL_INSURANCE_TEMPLATE_KEY)
const selectedTemplateObjects = computed(() =>
  form.selected_templates
    .map((key) => templates.value.find((template) => template.key === key))
    .filter((template): template is TaxRenewalTemplate => Boolean(template)),
)
const requiredFieldSet = computed(() => {
  const set = new Set<string>()
  selectedTemplateObjects.value.forEach((template) => {
    ;(template.required_fields || []).forEach((field) => set.add(field))
  })
  return set
})
const hasRequiredFields = computed(() => requiredFieldSet.value.size > 0)
const isFieldRequired = (fieldKey: string) => requiredFieldSet.value.has(fieldKey)
const groupHasFields = (fields: string[]) => fields.some((field) => isFieldRequired(field))

const pruneSelectedTemplates = () => {
  const allowed = new Set(filteredTemplates.value.filter((template) => !templateDisabled(template)).map((template) => template.key))
  form.selected_templates = form.selected_templates.filter((key) => allowed.has(key))
}

watch(
  () => [form.category, form.has_employees, form.has_dependents, templates.value.length],
  pruneSelectedTemplates,
)

const errorMessage = (error: unknown, fallback: string) => {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}

const valueOf = (source: unknown, key: string) => {
  const value = (source as Record<string, unknown> | undefined)?.[key]
  return typeof value === 'string' || typeof value === 'number' ? String(value) : ''
}

const splitDate = (dateValue?: string | null) => {
  if (!dateValue) return null
  const parts = dateValue.split('-').map((part) => Number(part))
  if (parts.length !== 3 || parts.some((part) => Number.isNaN(part))) return null
  return { year: parts[0], month: parts[1], day: parts[2] }
}

const restoreFiscalPeriod = (data: TaxRenewalFormData) => {
  if (data.fiscal_period_start && data.fiscal_period_end) {
    fiscalPeriod.value = [data.fiscal_period_start, data.fiscal_period_end]
    return
  }
  const start = data.fiscal_start_year && data.fiscal_start_month && data.fiscal_start_day
    ? `${data.fiscal_start_year}-${String(data.fiscal_start_month).padStart(2, '0')}-${String(data.fiscal_start_day).padStart(2, '0')}`
    : ''
  const end = data.fiscal_end_year && data.fiscal_end_month && data.fiscal_end_day
    ? `${data.fiscal_end_year}-${String(data.fiscal_end_month).padStart(2, '0')}-${String(data.fiscal_end_day).padStart(2, '0')}`
    : ''
  fiscalPeriod.value = start && end ? [start, end] : []
}

const applyFiscalFields = (data: TaxRenewalFormData) => {
  if (fiscalPeriod.value.length !== 2) {
    data.fiscal_period_start = null
    data.fiscal_period_end = null
    data.fiscal_start_year = null
    data.fiscal_start_month = null
    data.fiscal_start_day = null
    data.fiscal_end_year = null
    data.fiscal_end_month = null
    data.fiscal_end_day = null
    return
  }
  const [startValue, endValue] = fiscalPeriod.value
  const start = splitDate(startValue)
  const end = splitDate(endValue)
  if (!start || !end) return
  data.fiscal_period_start = startValue
  data.fiscal_period_end = endValue
  data.fiscal_start_year = start.year
  data.fiscal_start_month = start.month
  data.fiscal_start_day = start.day
  data.fiscal_end_year = end.year
  data.fiscal_end_month = end.month
  data.fiscal_end_day = end.day
}

const loadRecords = async () => {
  loading.value = true
  try {
    const data = await listTaxRenewalRecords(query)
    records.value = data.results
    total.value = data.count
  } catch {
    ElMessage.error('记录列表の取得に失敗しました。')
  } finally {
    loading.value = false
  }
}

const loadAgentTemplates = async () => {
  const data = await listTaxRenewalAgentTemplates(agentQuery)
  agentTemplates.value = data.results
}

const loadOptions = async () => {
  const [templateData, companyData, customerData, employeeData] = await Promise.all([
    listTaxRenewalTemplates(),
    listCompanies(),
    listCustomers(),
    listEmployees(),
    loadAgentTemplates(),
  ])
  templates.value = templateData
  companies.value = companyData.results
  customers.value = customerData.results
  employees.value = employeeData.results
}

const resetForm = () => {
  editingId.value = null
  form.title = ''
  form.category = 'renewal'
  form.company = null
  form.customer = null
  form.employee = null
  form.status = 'draft'
  form.has_employees = false
  form.has_dependents = false
  form.selected_templates = []
  form.form_data = emptyFormData()
  form.generated_files = []
  form.note = ''
  fiscalPeriod.value = []
}

const openCreate = () => {
  resetForm()
  drawerVisible.value = true
}

const openEdit = (record: TaxRenewalVoucherRecord) => {
  editingId.value = record.id
  form.title = record.title
  form.category = record.category
  form.company = record.company || null
  form.customer = record.customer || null
  form.employee = record.employee || null
  form.status = record.status
  form.has_employees = record.has_employees
  form.has_dependents = record.has_dependents
  form.selected_templates = [...(record.selected_templates || [])]
  form.form_data = { ...emptyFormData(), ...(record.form_data || {}) }
  form.generated_files = record.generated_files || []
  form.note = record.note || ''
  restoreFiscalPeriod(form.form_data)
  drawerVisible.value = true
}

const applyExistingData = () => {
  const company = selectedCompany.value
  if (company) {
    form.form_data.company_name = company.name || ''
    form.form_data.company_number = company.corporate_number || company.corporate_registration_number || ''
    form.form_data.company_address = company.address || ''
    form.form_data.company_phone = company.phone || ''
    form.form_data.representative_name = company.representative_name || ''
    form.form_data.representative_kana = company.representative_name_kana || ''
    form.form_data.representative_birth_date = valueOf(company, 'representative_birth_date') || null
  }

  const customer = selectedCustomer.value
  if (customer) {
    form.form_data.applicant_name = customer.name || ''
    form.form_data.applicant_kana = customer.name_kana || ''
    form.form_data.applicant_address = customer.address || ''
    form.form_data.applicant_phone = customer.phone || ''
    form.form_data.applicant_birth_date = customer.birth_date || null
  }

  const employee = selectedEmployee.value
  if (employee) {
    form.form_data.employee_name = employee.name || ''
    form.form_data.employee_kana = valueOf(employee, 'name_kana')
    form.form_data.employee_birth_date = valueOf(employee, 'birth_date') || null
    form.form_data.employee_address = valueOf(employee, 'address')
    form.form_data.employee_phone = employee.phone || ''
    form.form_data.employee_my_number = valueOf(employee, 'my_number')
    form.form_data.employment_start_date = valueOf(employee, 'employment_start_date') || null
    form.form_data.salary_amount = valueOf(employee, 'salary_amount')
  }

  ElMessage.success('现有资料を反映しました。')
}

const buildAgentSnapshot = (template: TaxRenewalAgentTemplate) => ({
  id: template.id,
  name: template.name,
  agent_name: template.agent_name,
  agent_kana: template.agent_kana,
  agent_address: template.agent_address,
  agent_phone: template.agent_phone,
  agent_company_name: template.agent_company_name,
  agent_position: template.agent_position,
  note: template.note,
})

const applyAgentTemplate = (templateId?: number | string | null) => {
  const id = Number(templateId || form.form_data.agent_template_id)
  const template = agentTemplates.value.find((item) => item.id === id)
  if (!template) return
  form.form_data.agent_template_id = template.id
  form.form_data.agent_snapshot = buildAgentSnapshot(template)
  form.form_data.agent_name = template.agent_name
  form.form_data.agent_kana = template.agent_kana
  form.form_data.agent_address = template.agent_address
  form.form_data.agent_phone = template.agent_phone
  form.form_data.agent_company_name = template.agent_company_name
  form.form_data.agent_position = template.agent_position
}

const applySocialInsuranceTestData = () => {
  form.title = '社会保険納入証明書テスト'
  form.category = 'renewal'
  form.status = 'draft'
  form.has_employees = true
  form.has_dependents = false
  form.note = '正式PDF生成テスト'

  if (!form.selected_templates.includes(SOCIAL_INSURANCE_TEMPLATE_KEY)) {
    form.selected_templates = [...form.selected_templates, SOCIAL_INSURANCE_TEMPLATE_KEY]
  }

  form.form_data = {
    ...form.form_data,
    company_name: 'SUNRISE日晟鴻達株式会社',
    company_number: '1234567890123',
    company_address: '大阪府大阪市天王寺区勝山四丁目七番三号',
    company_phone: '06-7650-6385',
    representative_name: '山田太郎',
    representative_kana: 'ヤマダ タロウ',
    representative_birth_date: '1980-05-05',
    representative_position: '代表取締役',
    applicant_name: '王小明',
    applicant_kana: 'オウ ショウメイ',
    applicant_address: '中国上海市浦東新区世紀大道100号',
    applicant_phone: '138-0000-0000',
    applicant_birth_date: '2000-01-01',
    agent_template_id: null,
    agent_snapshot: {
      agent_name: '李北北',
      agent_kana: 'リ ホクホク',
      agent_address: '大阪府大阪市天王寺区勝山四丁目七番三号',
      agent_phone: '06-7650-6385',
      agent_company_name: 'SUNRISE日晟鴻達株式会社',
      agent_position: '担当者',
    },
    agent_name: '李北北',
    agent_kana: 'リ ホクホク',
    agent_address: '大阪府大阪市天王寺区勝山四丁目七番三号',
    agent_phone: '06-7650-6385',
    agent_company_name: 'SUNRISE日晟鴻達株式会社',
    agent_position: '担当者',
    agent_relationship: '行政書士',
    fiscal_period_start: '2025-08-01',
    fiscal_period_end: '2026-07-31',
    fiscal_start_year: 2025,
    fiscal_start_month: 8,
    fiscal_start_day: 1,
    fiscal_end_year: 2026,
    fiscal_end_month: 7,
    fiscal_end_day: 31,
    fiscal_start_year_jp: '7',
    fiscal_end_year_jp: '8',
    submit_date: '2026-07-13',
    tax_office_name: '大阪南税務署',
    osaka_city_ward: '天王寺区',
    osaka_prefecture_office: '大阪府中央府税事務所',
    fiscal_year: '2025',
    certificate_type: '納入証明書',
    quantity: 1,
    employee_name: '王小明',
    employee_kana: 'オウ ショウメイ',
    employee_birth_date: '2000-01-01',
    employee_address: '大阪府大阪市天王寺区勝山四丁目七番三号',
    employee_phone: '090-1234-5678',
    employee_my_number: '123456789012',
    employment_start_date: '2026-07-01',
    salary_amount: 300000,
    establishment_symbol: '12イロ',
    establishment_number: '123456',
    social_insurance_symbol: '12イロ',
    social_insurance_office_number: '123456',
    application_reason: '代表者在留資格更新のため',
    dependents: [],
  }
  fiscalPeriod.value = ['2025-08-01', '2026-07-31']
  ElMessage.success('テストデータを入力しました。保存前に内容を確認できます。')
}

const buildPayload = (): TaxRenewalVoucherPayload => {
  const formData = { ...form.form_data }
  applyFiscalFields(formData)
  return {
    title: form.title.trim(),
    category: form.category,
    company: form.company || null,
    customer: form.customer || null,
    employee: form.employee || null,
    status: form.status,
    has_employees: form.has_employees,
    has_dependents: form.has_dependents,
    selected_templates: form.selected_templates,
    form_data: formData,
    generated_files: form.generated_files || [],
    note: form.note || '',
  }
}

const requiredFieldValue = (fieldKey: string, data: TaxRenewalFormData) => {
  if (fieldKey === 'fiscal_period_start') return fiscalPeriod.value[0] || data.fiscal_period_start
  if (fieldKey === 'fiscal_period_end') return fiscalPeriod.value[1] || data.fiscal_period_end
  return (data as Record<string, unknown>)[fieldKey]
}

const validateRequiredFields = () => {
  const data = { ...form.form_data }
  applyFiscalFields(data)
  for (const fieldKey of requiredFieldSet.value) {
    const value = requiredFieldValue(fieldKey, data)
    const isEmptyArray = Array.isArray(value) && value.length === 0
    if (value === undefined || value === null || value === '' || isEmptyArray) {
      ElMessage.error(`${fieldLabels[fieldKey] || fieldKey}を入力してください`)
      return false
    }
  }
  return true
}

const saveRecord = async () => {
  if (!form.title.trim()) {
    ElMessage.error('记录名称を入力してください。')
    return
  }
  if (!validateRequiredFields()) return
  saving.value = true
  try {
    if (editingId.value) {
      await updateTaxRenewalRecord(editingId.value, buildPayload())
    } else {
      await createTaxRenewalRecord(buildPayload())
    }
    ElMessage.success('保存しました。')
    drawerVisible.value = false
    await loadRecords()
  } catch (error) {
    ElMessage.error(errorMessage(error, '保存に失敗しました。'))
  } finally {
    saving.value = false
  }
}

const deleteRecord = async (record: TaxRenewalVoucherRecord) => {
  try {
    await ElMessageBox.confirm(`「${record.title}」を削除しますか？`, '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
  } catch {
    return
  }
  deletingId.value = record.id
  try {
    await deleteTaxRenewalRecord(record.id)
    ElMessage.success('削除しました。')
    await loadRecords()
  } catch {
    ElMessage.error('削除に失敗しました。')
  } finally {
    deletingId.value = null
  }
}

const generatePdf = async (record: TaxRenewalVoucherRecord) => {
  generatingId.value = record.id
  try {
    await generateTaxRenewalRecordPdf(record.id)
  } catch (error) {
    ElMessage.warning(errorMessage(error, 'PDF字段映射未完成'))
  } finally {
    generatingId.value = null
  }
}

const downloadSocialInsurancePdf = async (record: TaxRenewalVoucherRecord) => {
  generatingId.value = record.id
  try {
    const result = await generateTaxRenewalRecordPdf(record.id, {
      template_key: SOCIAL_INSURANCE_TEMPLATE_KEY,
    })
    downloadBlob(result.blob, result.contentDisposition)
    const warningFields = result.warningFields ? decodeURIComponent(result.warningFields) : ''
    if (warningFields) {
      ElMessage.warning(`PDF生成しました。warning: ${warningFields}`)
    } else {
      ElMessage.success('社会保険PDFを生成しました。')
    }
  } catch (error) {
    ElMessage.warning(errorMessage(error, '社会保険PDFの生成に失敗しました。'))
  } finally {
    generatingId.value = null
  }
}

const resetAgentForm = () => {
  editingAgentId.value = null
  agentForm.name = ''
  agentForm.agent_name = ''
  agentForm.agent_kana = ''
  agentForm.agent_address = ''
  agentForm.agent_phone = ''
  agentForm.agent_company_name = ''
  agentForm.agent_position = ''
  agentForm.note = ''
  agentForm.is_active = true
  agentForm.sort_order = 0
}

const openAgentDialog = () => {
  resetAgentForm()
  agentDialogVisible.value = true
  loadAgentTemplates()
}

const editAgentTemplate = (template: TaxRenewalAgentTemplate) => {
  editingAgentId.value = template.id
  agentForm.name = template.name
  agentForm.agent_name = template.agent_name
  agentForm.agent_kana = template.agent_kana
  agentForm.agent_address = template.agent_address
  agentForm.agent_phone = template.agent_phone
  agentForm.agent_company_name = template.agent_company_name
  agentForm.agent_position = template.agent_position
  agentForm.note = template.note
  agentForm.is_active = template.is_active
  agentForm.sort_order = template.sort_order
}

const saveAgentTemplate = async () => {
  if (!agentForm.name?.trim() || !agentForm.agent_name?.trim()) {
    ElMessage.error('模板名称と代理人姓名を入力してください。')
    return
  }
  agentSaving.value = true
  try {
    if (editingAgentId.value) {
      await updateTaxRenewalAgentTemplate(editingAgentId.value, agentForm)
    } else {
      await createTaxRenewalAgentTemplate(agentForm)
    }
    ElMessage.success('代理人模板を保存しました。')
    resetAgentForm()
    await loadAgentTemplates()
  } catch (error) {
    ElMessage.error(errorMessage(error, '代理人模板の保存に失敗しました。'))
  } finally {
    agentSaving.value = false
  }
}

const deleteAgentTemplate = async (template: TaxRenewalAgentTemplate) => {
  deletingAgentId.value = template.id
  try {
    await deleteTaxRenewalAgentTemplate(template.id)
    ElMessage.success('代理人模板を停用しました。')
    await loadAgentTemplates()
    if (form.form_data.agent_template_id === template.id) {
      form.form_data.agent_template_id = null
    }
  } catch {
    ElMessage.error('代理人模板の停用に失敗しました。')
  } finally {
    deletingAgentId.value = null
  }
}

const addDependent = () => {
  if (!form.form_data.dependents) form.form_data.dependents = []
  form.form_data.dependents.push({
    name: '',
    kana: '',
    birth_date: null,
    relationship: '',
    my_number: '',
    address: '',
  })
}

const removeDependent = (index: number) => {
  form.form_data.dependents?.splice(index, 1)
}

const handleSearch = () => {
  query.page = 1
  loadRecords()
}

const handleAgentSearch = () => {
  agentQuery.page = 1
  loadAgentTemplates()
}

const formatDateTime = (value?: string) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const extractFilename = (contentDisposition?: string) => {
  if (!contentDisposition) return 'numbered_sample.pdf'
  const encoded = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
  if (encoded?.[1]) return decodeURIComponent(encoded[1])
  const plain = contentDisposition.match(/filename="?([^";]+)"?/)
  return plain?.[1] || 'numbered_sample.pdf'
}

const downloadBlob = (blob: Blob, contentDisposition?: string) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = extractFilename(contentDisposition)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const openDiagnostics = async () => {
  diagnosticsVisible.value = true
  diagnosticsLoading.value = true
  try {
    diagnostics.value = await listTaxRenewalPdfDiagnostics()
  } catch {
    ElMessage.error('PDF字段诊断の取得に失敗しました。')
  } finally {
    diagnosticsLoading.value = false
  }
}

const downloadNumberedSample = async (diagnostic: TaxRenewalPdfDiagnostic) => {
  sampleGeneratingKey.value = diagnostic.template_key
  try {
    const { blob, contentDisposition } = await downloadTaxRenewalNumberedSample(diagnostic.template_key)
    downloadBlob(blob, contentDisposition)
  } catch (error) {
    ElMessage.warning(errorMessage(error, '该 PDF 没有 AcroForm 字段，需要坐标 mapping'))
  } finally {
    sampleGeneratingKey.value = null
  }
}

onMounted(async () => {
  await Promise.all([loadRecords(), loadOptions()])
})
</script>

<template>
  <section class="accounting-page tax-renewal-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>税务证明更新用</h1>
          <p>既存資料と代理人テンプレートを反映し、証明書生成用の記録を保存します。</p>
        </div>
        <div class="accounting-toolbar">
          <el-button @click="openDiagnostics">PDF字段诊断</el-button>
          <el-button type="primary" @click="openCreate">新建</el-button>
        </div>
      </div>
    </div>

    <el-card class="accounting-card" shadow="never">
      <div class="tax-list-toolbar">
        <el-input
          v-model="query.search"
          class="tax-search"
          clearable
          placeholder="标题 / 公司 / 客户"
          @clear="handleSearch"
          @keyup.enter="handleSearch"
        />
        <el-button @click="handleSearch">検索</el-button>
      </div>

      <el-table v-loading="loading" :data="records" row-key="id">
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column label="分类" width="110">
          <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column prop="company_name" label="公司" min-width="160" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" min-width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="selected_template_count" label="模板数" width="90" align="center" />
        <el-table-column label="更新时间" width="190">
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
                  <el-dropdown-item @click="openEdit(row)">编辑</el-dropdown-item>
                  <el-dropdown-item :disabled="generatingId === row.id" @click="generatePdf(row)">PDF生成</el-dropdown-item>
                  <el-dropdown-item
                    v-if="hasSocialInsuranceTemplate(row)"
                    :disabled="generatingId === row.id"
                    @click="downloadSocialInsurancePdf(row)"
                  >
                    社会保険PDF
                  </el-dropdown-item>
                  <el-dropdown-item divided class="danger-item" :disabled="deletingId === row.id" @click="deleteRecord(row)">
                    删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div class="tax-pagination">
        <el-pagination
          v-model:current-page="query.page"
          :page-size="query.page_size"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="loadRecords"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawerVisible" :title="editingId ? '编辑税务证明更新用记录' : '新建税务证明更新用记录'" size="86%">
      <div class="tax-drawer">
        <el-form label-position="top">
          <div class="tax-section-title">
            <span>基本信息</span>
            <el-button plain @click="applySocialInsuranceTestData">
              テストデータ入力
            </el-button>
          </div>
          <el-row :gutter="12">
            <el-col :xs="24" :md="8">
              <el-form-item label="标题">
                <el-input v-model="form.title" placeholder="例：SUNRISE 更新用证明" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="4">
              <el-form-item label="分类">
                <el-select v-model="form.category">
                  <el-option label="更新用" value="renewal" />
                  <el-option label="年金加入" value="pension" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="4">
              <el-form-item label="状态">
                <el-select v-model="form.status">
                  <el-option label="draft" value="draft" />
                  <el-option label="completed" value="completed" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="4">
              <el-form-item label="有雇员">
                <el-switch v-model="form.has_employees" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="4">
              <el-form-item label="有抚养人">
                <el-switch v-model="form.has_dependents" />
              </el-form-item>
            </el-col>
          </el-row>

          <div class="tax-section-title">模板选择</div>
          <el-checkbox-group v-model="form.selected_templates" class="template-list">
            <label v-for="template in filteredTemplates" :key="template.key" class="template-option">
              <el-checkbox :label="template.key" :disabled="templateDisabled(template)">
                <span>{{ template.order }}. {{ template.name }}</span>
              </el-checkbox>
              <span class="template-filename">{{ template.filename || '未匹配 PDF 文件' }}</span>
              <el-tag v-if="unavailableReason(template)" size="small" type="warning">
                {{ unavailableReason(template) }}
              </el-tag>
            </label>
          </el-checkbox-group>

          <div class="tax-section-title">自动套用资料</div>
          <el-row :gutter="12">
            <el-col :xs="24" :md="7">
              <el-form-item label="公司">
                <el-select v-model="form.company" clearable filterable placeholder="会社">
                  <el-option v-for="company in companies" :key="company.id" :label="company.name" :value="company.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="7">
              <el-form-item label="客户">
                <el-select v-model="form.customer" clearable filterable placeholder="顧客">
                  <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="7">
              <el-form-item label="员工 / 担当">
                <el-select v-model="form.employee" clearable filterable placeholder="员工 / 担当">
                  <el-option v-for="employee in employees" :key="employee.id" :label="employee.name" :value="employee.id" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="3">
              <el-form-item label="反映">
                <el-button class="full-width" @click="applyExistingData">套用资料</el-button>
              </el-form-item>
            </el-col>
          </el-row>

          <el-alert
            v-if="!hasRequiredFields"
            title="PDFを選択すると、必要な入力項目だけ表示されます。"
            type="info"
            :closable="false"
            show-icon
          />

          <div v-if="hasRequiredFields" class="tax-section-title">必填内容</div>
          <el-collapse v-if="hasRequiredFields">
            <el-collapse-item
              v-if="groupHasFields(fieldGroups[0].fields)"
              :title="fieldGroups[0].title"
              name="company"
            >
              <el-row :gutter="12">
                <el-col v-if="isFieldRequired('company_name')" :xs="24" :md="8"><el-form-item :label="fieldLabels.company_name"><el-input v-model="form.form_data.company_name" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('company_number')" :xs="24" :md="8"><el-form-item :label="fieldLabels.company_number"><el-input v-model="form.form_data.company_number" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('company_phone')" :xs="24" :md="8"><el-form-item :label="fieldLabels.company_phone"><el-input v-model="form.form_data.company_phone" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('establishment_symbol')" :xs="24" :md="8"><el-form-item :label="fieldLabels.establishment_symbol"><el-input v-model="form.form_data.establishment_symbol" placeholder="例：12イロ" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('establishment_number')" :xs="24" :md="8"><el-form-item :label="fieldLabels.establishment_number"><el-input v-model="form.form_data.establishment_number" placeholder="例：123456" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('representative_name')" :xs="24" :md="8"><el-form-item :label="fieldLabels.representative_name"><el-input v-model="form.form_data.representative_name" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('representative_kana')" :xs="24" :md="8"><el-form-item :label="fieldLabels.representative_kana"><el-input v-model="form.form_data.representative_kana" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('representative_position')" :xs="24" :md="8"><el-form-item :label="fieldLabels.representative_position"><el-input v-model="form.form_data.representative_position" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('representative_birth_date')" :xs="24" :md="8"><el-form-item :label="fieldLabels.representative_birth_date"><el-date-picker v-model="form.form_data.representative_birth_date" value-format="YYYY-MM-DD" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('company_address')" :xs="24"><el-form-item :label="fieldLabels.company_address"><el-input v-model="form.form_data.company_address" /></el-form-item></el-col>
              </el-row>
            </el-collapse-item>

            <el-collapse-item
              v-if="groupHasFields(fieldGroups[1].fields)"
              :title="fieldGroups[1].title"
              name="applicant"
            >
              <el-row :gutter="12">
                <el-col v-if="isFieldRequired('applicant_name')" :xs="24" :md="8"><el-form-item :label="fieldLabels.applicant_name"><el-input v-model="form.form_data.applicant_name" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('applicant_kana')" :xs="24" :md="8"><el-form-item :label="fieldLabels.applicant_kana"><el-input v-model="form.form_data.applicant_kana" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('applicant_phone')" :xs="24" :md="8"><el-form-item :label="fieldLabels.applicant_phone"><el-input v-model="form.form_data.applicant_phone" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('applicant_birth_date')" :xs="24" :md="8"><el-form-item :label="fieldLabels.applicant_birth_date"><el-date-picker v-model="form.form_data.applicant_birth_date" value-format="YYYY-MM-DD" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('applicant_address')" :xs="24"><el-form-item :label="fieldLabels.applicant_address"><el-input v-model="form.form_data.applicant_address" /></el-form-item></el-col>
              </el-row>
            </el-collapse-item>

            <el-collapse-item
              v-if="groupHasFields(fieldGroups[2].fields)"
              :title="fieldGroups[2].title"
              name="agent"
            >
              <div class="tax-section-title">
                <span>代理人模板</span>
                <el-button plain @click="openAgentDialog">代理人模板管理</el-button>
              </div>
              <el-row :gutter="12">
                <el-col :xs="24" :md="8">
                  <el-form-item label="代理人模板">
                    <el-select
                      v-model="form.form_data.agent_template_id"
                      clearable
                      filterable
                      placeholder="选择模板"
                      @change="applyAgentTemplate"
                    >
                      <el-option
                        v-for="template in agentTemplates"
                        :key="template.id"
                        :label="template.name"
                        :value="template.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col v-if="isFieldRequired('agent_name')" :xs="24" :md="8"><el-form-item :label="fieldLabels.agent_name"><el-input v-model="form.form_data.agent_name" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('agent_kana')" :xs="24" :md="8"><el-form-item :label="fieldLabels.agent_kana"><el-input v-model="form.form_data.agent_kana" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('agent_phone')" :xs="24" :md="8"><el-form-item :label="fieldLabels.agent_phone"><el-input v-model="form.form_data.agent_phone" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('agent_company_name')" :xs="24" :md="8"><el-form-item :label="fieldLabels.agent_company_name"><el-input v-model="form.form_data.agent_company_name" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('agent_position')" :xs="24" :md="8"><el-form-item :label="fieldLabels.agent_position"><el-input v-model="form.form_data.agent_position" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('agent_relationship')" :xs="24" :md="8"><el-form-item :label="fieldLabels.agent_relationship"><el-input v-model="form.form_data.agent_relationship" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('agent_address')" :xs="24"><el-form-item :label="fieldLabels.agent_address"><el-input v-model="form.form_data.agent_address" /></el-form-item></el-col>
              </el-row>
            </el-collapse-item>

            <el-collapse-item
              v-if="groupHasFields(fieldGroups[3].fields)"
              :title="fieldGroups[3].title"
              name="fiscal"
            >
              <el-row :gutter="12">
                <el-col v-if="isFieldRequired('fiscal_period_start') || isFieldRequired('fiscal_period_end')" :xs="24" :md="10">
                  <el-form-item label="決算期間">
                    <el-date-picker
                      v-model="fiscalPeriod"
                      type="daterange"
                      value-format="YYYY-MM-DD"
                      start-placeholder="开始日期"
                      end-placeholder="结束日期"
                      clearable
                    />
                  </el-form-item>
                </el-col>
                <el-col v-if="isFieldRequired('fiscal_year')" :xs="24" :md="6"><el-form-item :label="fieldLabels.fiscal_year"><el-input v-model="form.form_data.fiscal_year" placeholder="例：2026年度" /></el-form-item></el-col>
                <el-col :xs="24" :md="8"><div class="tax-hint">保存时自动生成开始年/月/日、结束年/月/日字段。</div></el-col>
              </el-row>
            </el-collapse-item>

            <el-collapse-item
              v-if="groupHasFields(fieldGroups[4].fields)"
              :title="fieldGroups[4].title"
              name="tax"
            >
              <el-row :gutter="12">
                <el-col v-if="isFieldRequired('application_reason')" :xs="24" :md="8"><el-form-item :label="fieldLabels.application_reason"><el-input v-model="form.form_data.application_reason" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('tax_office_name')" :xs="24" :md="8"><el-form-item :label="fieldLabels.tax_office_name"><el-input v-model="form.form_data.tax_office_name" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('osaka_city_ward')" :xs="24" :md="8"><el-form-item :label="fieldLabels.osaka_city_ward"><el-input v-model="form.form_data.osaka_city_ward" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('osaka_prefecture_office')" :xs="24" :md="8"><el-form-item :label="fieldLabels.osaka_prefecture_office"><el-input v-model="form.form_data.osaka_prefecture_office" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('certificate_type')" :xs="24" :md="8"><el-form-item :label="fieldLabels.certificate_type"><el-input v-model="form.form_data.certificate_type" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('quantity')" :xs="24" :md="8"><el-form-item :label="fieldLabels.quantity"><el-input v-model="form.form_data.quantity" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('submit_date')" :xs="24" :md="8"><el-form-item :label="fieldLabels.submit_date"><el-date-picker v-model="form.form_data.submit_date" value-format="YYYY-MM-DD" /></el-form-item></el-col>
              </el-row>
            </el-collapse-item>

            <el-collapse-item
              v-if="groupHasFields(fieldGroups[5].fields)"
              :title="fieldGroups[5].title"
              name="employee"
            >
              <el-row :gutter="12">
                <el-col v-if="isFieldRequired('employee_name')" :xs="24" :md="8"><el-form-item :label="fieldLabels.employee_name"><el-input v-model="form.form_data.employee_name" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('employee_kana')" :xs="24" :md="8"><el-form-item :label="fieldLabels.employee_kana"><el-input v-model="form.form_data.employee_kana" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('employee_birth_date')" :xs="24" :md="8"><el-form-item :label="fieldLabels.employee_birth_date"><el-date-picker v-model="form.form_data.employee_birth_date" value-format="YYYY-MM-DD" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('employee_phone')" :xs="24" :md="8"><el-form-item :label="fieldLabels.employee_phone"><el-input v-model="form.form_data.employee_phone" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('employee_my_number')" :xs="24" :md="8"><el-form-item :label="fieldLabels.employee_my_number"><el-input v-model="form.form_data.employee_my_number" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('employment_start_date')" :xs="24" :md="8"><el-form-item :label="fieldLabels.employment_start_date"><el-date-picker v-model="form.form_data.employment_start_date" value-format="YYYY-MM-DD" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('salary_amount')" :xs="24" :md="8"><el-form-item :label="fieldLabels.salary_amount"><el-input v-model="form.form_data.salary_amount" /></el-form-item></el-col>
                <el-col v-if="isFieldRequired('employee_address')" :xs="24"><el-form-item :label="fieldLabels.employee_address"><el-input v-model="form.form_data.employee_address" /></el-form-item></el-col>
              </el-row>
            </el-collapse-item>

            <el-collapse-item
              v-if="groupHasFields(fieldGroups[6].fields) && form.has_dependents"
              :title="fieldGroups[6].title"
              name="dependents"
            >
              <div class="tax-section-title">
                <span>抚养人信息</span>
                <el-button plain @click="addDependent">追加</el-button>
              </div>
              <div v-for="(dependent, index) in form.form_data.dependents" :key="index" class="dependent-row">
                <el-input v-model="dependent.name" placeholder="姓名" />
                <el-input v-model="dependent.kana" placeholder="カナ" />
                <el-date-picker v-model="dependent.birth_date" value-format="YYYY-MM-DD" placeholder="生日" />
                <el-input v-model="dependent.relationship" placeholder="关系" />
                <el-input v-model="dependent.my_number" placeholder="My Number" />
                <el-input v-model="dependent.address" placeholder="地址" />
                <el-button text type="danger" @click="removeDependent(index)">删除</el-button>
              </div>
            </el-collapse-item>
          </el-collapse>

          <el-form-item class="tax-note-field" label="备注">
            <el-input v-model="form.note" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>

        <div class="tax-drawer-footer">
          <el-button @click="drawerVisible = false">关闭</el-button>
          <el-button type="primary" :loading="saving" @click="saveRecord">保存</el-button>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="agentDialogVisible" title="代理人模板管理" width="920px">
      <div class="agent-dialog-layout">
        <div>
          <div class="tax-list-toolbar">
            <el-input
              v-model="agentQuery.search"
              class="tax-search"
              clearable
              placeholder="模板 / 代理人"
              @clear="handleAgentSearch"
              @keyup.enter="handleAgentSearch"
            />
            <el-button @click="handleAgentSearch">検索</el-button>
          </div>
          <el-table :data="agentTemplates" row-key="id" max-height="420">
            <el-table-column prop="name" label="模板名称" min-width="150" />
            <el-table-column prop="agent_name" label="代理人" min-width="120" />
            <el-table-column prop="agent_phone" label="电话" width="130" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-dropdown trigger="click">
                  <el-button text type="primary" class="table-action-trigger">
                    操作
                    <el-icon><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item @click="editAgentTemplate(row)">编辑</el-dropdown-item>
                      <el-dropdown-item divided class="danger-item" :disabled="deletingAgentId === row.id" @click="deleteAgentTemplate(row)">
                        停用
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="agent-form-panel">
          <div class="tax-section-title">{{ editingAgentId ? '编辑模板' : '新增模板' }}</div>
          <el-form label-position="top">
            <el-form-item label="模板名称"><el-input v-model="agentForm.name" /></el-form-item>
            <el-form-item label="代理人姓名"><el-input v-model="agentForm.agent_name" /></el-form-item>
            <el-form-item label="代理人カナ"><el-input v-model="agentForm.agent_kana" /></el-form-item>
            <el-form-item label="代理公司名"><el-input v-model="agentForm.agent_company_name" /></el-form-item>
            <el-form-item label="职务"><el-input v-model="agentForm.agent_position" /></el-form-item>
            <el-form-item label="电话"><el-input v-model="agentForm.agent_phone" /></el-form-item>
            <el-form-item label="地址"><el-input v-model="agentForm.agent_address" /></el-form-item>
            <el-form-item label="备注"><el-input v-model="agentForm.note" type="textarea" :rows="2" /></el-form-item>
            <div class="agent-actions">
              <el-button @click="resetAgentForm">清空</el-button>
              <el-button type="primary" :loading="agentSaving" @click="saveAgentTemplate">保存模板</el-button>
            </div>
          </el-form>
        </div>
      </div>
    </el-dialog>

    <el-drawer v-model="diagnosticsVisible" title="PDF字段诊断" size="82%">
      <div v-loading="diagnosticsLoading" class="diagnostics-list">
        <el-empty v-if="!diagnostics.length && !diagnosticsLoading" description="暂无诊断结果" />
        <el-card v-for="item in diagnostics" :key="item.template_key" class="diagnostic-card" shadow="never">
          <div class="diagnostic-header">
            <div>
              <div class="diagnostic-title">{{ item.template_name }}</div>
              <div class="template-filename">{{ item.filename || '未匹配 PDF 文件' }}</div>
            </div>
            <div class="diagnostic-actions">
              <el-tag v-if="!item.file_exists" type="danger">模板文件不存在</el-tag>
              <el-tag v-else-if="item.has_acroform" type="success">AcroForm {{ item.field_count }}</el-tag>
              <el-tag v-else type="warning">需要坐标 mapping</el-tag>
              <el-button
                size="small"
                :disabled="!item.has_acroform"
                :loading="sampleGeneratingKey === item.template_key"
                @click="downloadNumberedSample(item)"
              >
                下载编号样本
              </el-button>
            </div>
          </div>

          <div class="diagnostic-meta">
            <span>页数: {{ item.page_count }}</span>
            <span v-for="page in item.pages" :key="page.page">
              P{{ page.page }}: {{ page.width }} x {{ page.height }} pt
            </span>
          </div>

          <el-table v-if="item.fields.length" :data="item.fields" size="small" row-key="index">
            <el-table-column prop="index" label="#" width="64" />
            <el-table-column prop="field_name" label="字段名" min-width="220" show-overflow-tooltip />
            <el-table-column prop="field_type" label="类型" width="140" show-overflow-tooltip />
            <el-table-column prop="page" label="页" width="70" />
            <el-table-column label="Rect" min-width="220">
              <template #default="{ row }">
                <span v-if="row.rect">
                  {{ row.rect.x0 }}, {{ row.rect.y0 }}, {{ row.rect.x1 }}, {{ row.rect.y1 }}
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="选项" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.options?.join(', ') || '-' }}</template>
            </el-table-column>
          </el-table>
          <el-alert
            v-else-if="item.file_exists"
            title="该 PDF 没有 AcroForm 字段，需要坐标 mapping"
            type="warning"
            :closable="false"
            show-icon
          />
        </el-card>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.tax-list-toolbar {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.tax-search {
  width: min(320px, 100%);
}

.tax-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.tax-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 18px 0 10px;
  font-weight: 800;
  color: var(--sunrise-text);
}

.template-list {
  display: grid;
  gap: 8px;
}

.template-option {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(160px, 260px) auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid rgba(120, 150, 180, 0.24);
  border-radius: 8px;
  background: #fff;
}

.template-filename {
  color: var(--sunrise-muted);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tax-hint {
  display: flex;
  align-items: center;
  min-height: 54px;
  color: var(--sunrise-muted);
  font-size: 13px;
}

.full-width {
  width: 100%;
}

.dependent-row {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr)) auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.tax-drawer-footer {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 0 0;
  margin-top: 18px;
  background: #fff;
}

.agent-dialog-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 18px;
}

.agent-form-panel {
  padding-left: 18px;
  border-left: 1px solid rgba(120, 150, 180, 0.24);
}

.agent-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.diagnostics-list {
  display: grid;
  gap: 14px;
}

.diagnostic-card {
  border-radius: 8px;
}

.diagnostic-header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.diagnostic-title {
  font-weight: 800;
  color: var(--sunrise-text);
}

.diagnostic-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.diagnostic-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  color: var(--sunrise-muted);
  font-size: 13px;
}

@media (max-width: 980px) {
  .template-option,
  .dependent-row,
  .agent-dialog-layout {
    grid-template-columns: 1fr;
  }

  .agent-form-panel {
    padding-left: 0;
    border-left: 0;
  }
}
</style>
