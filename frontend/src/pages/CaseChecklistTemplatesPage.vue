<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createAcquisitionPlacePreset,
  createCaseApplicationCategory,
  createCaseChecklistTemplate,
  createCaseChecklistTemplateItem,
  createCaseTypeMaster,
  createResponsiblePartyPreset,
  listAcquisitionPlacePresets,
  listCaseApplicationCategories,
  listCaseChecklistItemNameSuggestions,
  listCaseChecklistItemOptions,
  listCaseChecklistDeletionHistory,
  listCaseChecklistTemplateItems,
  listCaseChecklistTemplates,
  listCaseStatusSettings,
  listCaseTypeMasters,
  listResponsiblePartyPresets,
  moveCaseChecklistTemplateItemDown,
  moveCaseChecklistTemplateItemUp,
  restoreCaseChecklistTemplate,
  restoreCaseChecklistTemplateItem,
  seedStandardCaseChecklistTemplates,
  softDeleteCaseChecklistTemplate,
  softDeleteCaseChecklistTemplateItem,
  updateAcquisitionPlacePreset,
  updateCaseApplicationCategory,
  updateCaseChecklistTemplate,
  updateCaseChecklistTemplateItem,
  updateCaseStatusSetting,
  updateCaseTypeMaster,
  updateResponsiblePartyPreset,
} from '../api/cases'
import { createEmployee, listEmployees, updateEmployee } from '../api/employees'
import type {
  AcquisitionPlacePreset,
  CaseApplicationCategory,
  CaseChecklistDeletionHistoryItem,
  CaseChecklistItemType,
  CaseChecklistTemplate,
  CaseChecklistTemplateItem,
  CaseChecklistTemplateItemPayload,
  CaseChecklistTemplatePayload,
  CaseStatusSetting,
  CaseTypeMaster,
  Employee,
  EmployeePayload,
  ItemNameSuggestion,
  ResponsiblePartyPreset,
} from '../types/api'
import { formatDateTime } from '../utils/date'

const loading = ref(false)
const templates = ref<CaseChecklistTemplate[]>([])
const selectedTemplateId = ref<number | null>(null)
const templateSearch = ref('')
const templateActiveFilter = ref<'true' | 'false' | ''>('true')
const templateDialogVisible = ref(false)
const templateSubmitting = ref(false)
const templateFormRef = ref<FormInstance>()
const editingTemplateId = ref<number | null>(null)
const itemDialogVisible = ref(false)
const itemSubmitting = ref(false)
const itemFormRef = ref<FormInstance>()
const editingItemId = ref<number | null>(null)
const templateItems = ref<CaseChecklistTemplateItem[]>([])
const demoSeedSubmitting = ref(false)
const deletionHistory = ref<CaseChecklistDeletionHistoryItem[]>([])
const deletionHistoryLoading = ref(false)
const deletionHistoryDialogVisible = ref(false)
const templateCurrentPage = ref(1)
const templatePageSize = ref(20)
const templateTotal = ref(0)
const itemCurrentPage = ref(1)
const itemPageSize = ref(20)
const itemTotal = ref(0)
const deletionCurrentPage = ref(1)
const deletionPageSize = ref(10)
const deletionTotal = ref(0)
const latestDeletedAt = ref<string | null>(null)
const categoryCandidates = ref<string[]>([])
let templateRequestId = 0
let templateItemRequestId = 0
let deletionHistoryRequestId = 0
const caseSettingTab = ref('case-types')
const caseTypes = ref<CaseTypeMaster[]>([])
const applicationCategories = ref<CaseApplicationCategory[]>([])
const caseStatusSettings = ref<CaseStatusSetting[]>([])
const acquisitionPlacePresets = ref<AcquisitionPlacePreset[]>([])
const responsiblePartyPresets = ref<ResponsiblePartyPreset[]>([])
const employees = ref<Employee[]>([])
const settingDialogVisible = ref(false)
const settingDialogType = ref<'case-type' | 'application-category' | 'status' | 'acquisition-place' | 'responsible-party' | 'employee'>('case-type')
const editingSettingId = ref<number | null>(null)
const settingFormRef = ref<FormInstance>()
const settingSubmitting = ref(false)
const settingForm = ref({
  name: '',
  code: '',
  number_abbreviation: '',
  display_name: '',
  sort_order: 0,
  is_active: true,
  is_visible: true,
  email: '',
  phone: '',
})

const presetCategories = [
  '本人資料',
  '会社資料',
  '会社設立資料',
  '勤務先資料',
  '学歴・職歴資料',
  '事業計画資料',
  '事務所資料',
  '資本金・資金資料',
  '税務資料',
  '税務・届出資料',
  '社会保険資料',
  '年金・保険資料',
  '給与・税務資料',
  '経営状況資料',
  '職業・収入資料',
  '身元保証人資料',
  '在留履歴資料',
  'ポイント計算資料',
  '年収・契約資料',
  '雇用条件資料',
  '申請準備',
  'その他',
]

const itemTypeOptions = [
  { label: '手続事項', value: 'task' },
  { label: '必要資料', value: 'document' },
  { label: '確認事項', value: 'confirmation' },
] as const

const responsiblePartyOptions = [
  { label: '未設定', value: '' },
  { label: '顧客本人', value: 'customer' },
  { label: '会社', value: 'company' },
  { label: '本公司代办', value: 'our_company' },
  { label: '行政書士', value: 'gyousei' },
  { label: '税理士', value: 'tax_accountant' },
  { label: 'その他', value: 'other' },
] as const

const importanceLevelOptions = [
  { label: '通常', value: 'normal', type: 'info' },
  { label: '重要', value: 'important', type: 'warning' },
  { label: '要注意', value: 'warning', type: 'danger' },
] as const

type NoticeLanguage = 'zh' | 'ja'
type NoticeType = 'initial' | 'additional' | 'reminder'

const materialNoticeDialogVisible = ref(false)
const materialNoticeText = ref('')
const materialNoticeOptions = ref({
  noticeType: 'initial' as NoticeType,
  language: 'zh' as NoticeLanguage,
  showPlace: true,
  showRequiredDetails: true,
  showCustomerNote: true,
})

const templateForm = ref<CaseChecklistTemplatePayload>({
  name: '',
  description: '',
  is_active: true,
  sort_order: 0,
})

const itemForm = ref<CaseChecklistTemplateItemPayload>({
  template: 0,
  category: '',
  name: '',
  item_type: 'document',
  quantity: null,
  unit: '',
  is_required: true,
  description: '',
  responsible_party: '',
  acquisition_place: '',
  required_details: '',
  internal_note: '',
  customer_note: '',
  is_visible_to_customer: true,
  importance_level: 'normal',
  sort_order: 0,
  is_active: true,
})

const templateRules: FormRules<CaseChecklistTemplatePayload> = {
  name: [{ required: true, message: 'テンプレート名を入力してください。', trigger: 'blur' }],
}

const itemRules: FormRules<CaseChecklistTemplateItemPayload> = {
  category: [{ required: true, message: '分類を選択してください。', trigger: 'change' }],
  name: [{ required: true, message: '項目名を入力してください。', trigger: 'blur' }],
  item_type: [{ required: true, message: '項目タイプを選択してください。', trigger: 'change' }],
}

const settingRules: FormRules = {
  name: [{ required: true, message: '名称を入力してください。', trigger: 'blur' }],
  display_name: [{ required: true, message: '表示名を入力してください。', trigger: 'blur' }],
}

const usageNotes = {
  caseType: {
    use: ['案件一覧 ＞ 新規案件 ＞ 案件種別', '顧客詳細 ＞ 案件を追加 ＞ 案件種別', '会社詳細 ＞ 案件を追加 ＞ 案件種別', '案件基本情報 ＞ 編集 ＞ 案件種別'],
    impact: ['新規案件の案件種別選択肢', '案件番号の案件種別略称'],
  },
  applicationCategory: {
    use: ['案件一覧 ＞ 新規案件 ＞ 申請区分', '顧客詳細 ＞ 案件を追加 ＞ 申請区分', '会社詳細 ＞ 案件を追加 ＞ 申請区分', '案件基本情報 ＞ 編集 ＞ 申請区分'],
    impact: ['新規案件の申請区分選択肢', '案件番号の申請区分略称'],
  },
  status: {
    use: ['案件詳細 ＞ 進捗変更', '案件一覧 ＞ 現在の進捗筛选', '案件一覧 ＞ 進捗表示', '顧客詳細 ＞ 関連案件', '会社詳細 ＞ 関連案件'],
    impact: ['表示名・表示順・表示可否のみ変更できます', '内部コードと日付連動ルールは変更できません'],
  },
  checklist: {
    use: ['案件詳細 ＞ 案件進捗・必要資料', '案件詳細 ＞ テンプレートから追加', '顧客向け材料案内', '顧客通知文案'],
    impact: ['Checklistテンプレートと項目', '取得場所・準備者・必要内容・顧客注意事項'],
  },
  presets: {
    use: ['Checklistテンプレート項目 ＞ 手続先・取得場所', '案件実際事項 ＞ 手続先・取得場所', 'Checklistテンプレート項目 ＞ 準備者／担当区分', '案件実際事項 ＞ 準備者／担当区分'],
    impact: ['有効な预设は選択肢に表示', '自由入力と歴史テキストは保持'],
  },
  employee: {
    use: ['案件一覧 ＞ 新規案件 ＞ 担当者', '顧客詳細 ＞ 案件を追加 ＞ 担当者', '会社詳細 ＞ 案件を追加 ＞ 担当者', '案件基本情報 ＞ 編集 ＞ 担当者', '案件一覧 ＞ 担当者筛选'],
    impact: ['有効な担当者は新規・編集フォームに表示', '無効担当者は新規選択肢から除外され、歴史案件では氏名表示を保持'],
  },
}

const selectedTemplate = computed(() => (
  templates.value.find((template) => template.id === selectedTemplateId.value) || null
))

const sortedItems = computed(() => (
  [...templateItems.value].sort((left, right) => {
    if ((left.sort_order || 0) !== (right.sort_order || 0)) {
      return (left.sort_order || 0) - (right.sort_order || 0)
    }
    return left.id - right.id
  })
))

const categoryOptions = computed(() => {
  const currentValues = templateItems.value.map((item) => item.category).filter(Boolean)
  const values = [...categoryCandidates.value, ...currentValues]
  return [...new Set([...presetCategories, ...values])]
})

const getItemTypeLabel = (type: CaseChecklistItemType) => (
  itemTypeOptions.find((option) => option.value === type)?.label || type
)

const getImportanceOption = (level: string) => (
  importanceLevelOptions.find((option) => option.value === level) || importanceLevelOptions[0]
)

const getImportanceLabel = (level: string) => getImportanceOption(level).label

const normalizeOptionText = (value: string) => value.trim().replace(/\s+/g, ' ')

const formatApiError = (error: unknown, fallback: string) => {
  const data = (error as { response?: { data?: unknown } })?.response?.data
  if (!data || typeof data !== 'object') return fallback
  const message = Object.entries(data as Record<string, unknown>).map(([field, value]) => {
    if (Array.isArray(value)) return `${field}：${value.join('、')}`
    if (typeof value === 'string') return `${field}：${value}`
    return `${field}：${JSON.stringify(value)}`
  }).join('\n')
  return message || fallback
}

const fetchSettingData = async () => {
  try {
    const [
      caseTypeData,
      applicationCategoryData,
      statusData,
      acquisitionPlaceData,
      responsiblePartyData,
      employeeData,
    ] = await Promise.all([
      listCaseTypeMasters({ ordering: 'sort_order' }),
      listCaseApplicationCategories({ ordering: 'sort_order' }),
      listCaseStatusSettings({ ordering: 'sort_order' }),
      listAcquisitionPlacePresets({ ordering: 'sort_order' }),
      listResponsiblePartyPresets({ ordering: 'sort_order' }),
      listEmployees(),
    ])
    caseTypes.value = caseTypeData.results
    applicationCategories.value = applicationCategoryData.results
    caseStatusSettings.value = statusData.results
    acquisitionPlacePresets.value = acquisitionPlaceData.results
    responsiblePartyPresets.value = responsiblePartyData.results
    employees.value = employeeData.results
  } catch {
    ElMessage.error('設定データの取得に失敗しました。')
  }
}

const resetSettingForm = () => {
  editingSettingId.value = null
  settingForm.value = {
    name: '',
    code: '',
    number_abbreviation: '',
    display_name: '',
    sort_order: 0,
    is_active: true,
    is_visible: true,
    email: '',
    phone: '',
  }
  settingFormRef.value?.clearValidate()
}

const openSettingDialog = (
  type: typeof settingDialogType.value,
  row?: CaseTypeMaster | CaseApplicationCategory | CaseStatusSetting | AcquisitionPlacePreset | ResponsiblePartyPreset | Employee,
) => {
  resetSettingForm()
  settingDialogType.value = type
  if (row) {
    editingSettingId.value = row.id
    settingForm.value.name = 'name' in row ? row.name : ''
    settingForm.value.code = 'code' in row ? row.code : ''
    settingForm.value.number_abbreviation = 'number_abbreviation' in row ? row.number_abbreviation : ''
    settingForm.value.display_name = 'display_name' in row ? row.display_name : ''
    settingForm.value.sort_order = 'sort_order' in row ? row.sort_order : 0
    settingForm.value.is_active = 'is_active' in row ? row.is_active : true
    settingForm.value.is_visible = 'is_visible' in row ? row.is_visible : true
    settingForm.value.email = 'email' in row ? row.email : ''
    settingForm.value.phone = 'phone' in row ? row.phone : ''
  }
  settingDialogVisible.value = true
}

const submitSetting = async () => {
  if (!settingFormRef.value) return
  const valid = await settingFormRef.value.validate().catch(() => false)
  if (!valid) return
  settingSubmitting.value = true
  try {
    const id = editingSettingId.value
    if (settingDialogType.value === 'case-type') {
      const payload = {
        name: settingForm.value.name.trim(),
        code: settingForm.value.code.trim() || undefined,
        number_abbreviation: settingForm.value.number_abbreviation.trim(),
        sort_order: settingForm.value.sort_order,
        is_active: settingForm.value.is_active,
      }
      if (id) await updateCaseTypeMaster(id, payload)
      else await createCaseTypeMaster(payload)
    } else if (settingDialogType.value === 'application-category') {
      const payload = {
        name: settingForm.value.name.trim(),
        code: settingForm.value.code.trim() || undefined,
        number_abbreviation: settingForm.value.number_abbreviation.trim(),
        sort_order: settingForm.value.sort_order,
        is_active: settingForm.value.is_active,
      }
      if (id) await updateCaseApplicationCategory(id, payload)
      else await createCaseApplicationCategory(payload)
    } else if (settingDialogType.value === 'status') {
      if (id) await updateCaseStatusSetting(id, {
        display_name: settingForm.value.display_name.trim(),
        sort_order: settingForm.value.sort_order,
        is_visible: settingForm.value.is_visible,
      })
    } else if (settingDialogType.value === 'acquisition-place') {
      const payload = {
        name: settingForm.value.name.trim(),
        sort_order: settingForm.value.sort_order,
        is_active: settingForm.value.is_active,
      }
      if (id) await updateAcquisitionPlacePreset(id, payload)
      else await createAcquisitionPlacePreset(payload)
    } else if (settingDialogType.value === 'responsible-party') {
      const payload = {
        name: settingForm.value.name.trim(),
        code: settingForm.value.code.trim() || undefined,
        sort_order: settingForm.value.sort_order,
        is_active: settingForm.value.is_active,
      }
      if (id) await updateResponsiblePartyPreset(id, payload)
      else await createResponsiblePartyPreset(payload)
    } else if (settingDialogType.value === 'employee') {
      const payload: EmployeePayload = {
        name: settingForm.value.name.trim(),
        email: settingForm.value.email.trim(),
        phone: settingForm.value.phone.trim(),
        is_active: settingForm.value.is_active,
      }
      if (id) await updateEmployee(id, payload)
      else await createEmployee(payload)
    }
    ElMessage.success('設定を保存しました。')
    settingDialogVisible.value = false
    await fetchSettingData()
  } catch (error) {
    ElMessage.error(formatApiError(error, '設定の保存に失敗しました。'))
  } finally {
    settingSubmitting.value = false
  }
}

const fetchItemOptions = async () => {
  try {
    const data = await listCaseChecklistItemOptions()
    categoryCandidates.value = data.categories
  } catch {
    ElMessage.error('項目候補の取得に失敗しました。')
  }
}

const queryItemNameSuggestions = async (
  query: string,
  callback: (suggestions: ItemNameSuggestion[]) => void,
) => {
  try {
    const suggestions = await listCaseChecklistItemNameSuggestions({ q: query || undefined })
    callback(suggestions)
  } catch {
    callback([])
  }
}

const fetchTemplates = async (page = templateCurrentPage.value) => {
  const requestId = ++templateRequestId
  loading.value = true
  try {
    const data = await listCaseChecklistTemplates({
      page,
      page_size: templatePageSize.value,
      search: templateSearch.value || undefined,
      is_active: templateActiveFilter.value || undefined,
      ordering: 'sort_order',
    })
    if (requestId !== templateRequestId) return
    templates.value = data.results
    templateTotal.value = data.count
    templateCurrentPage.value = page
    if (selectedTemplateId.value && !data.results.some((template) => template.id === selectedTemplateId.value)) {
      selectedTemplateId.value = null
      templateItems.value = []
      itemTotal.value = 0
    }
    if (!selectedTemplateId.value && data.results.length) {
      selectedTemplateId.value = data.results[0].id
    }
    if (selectedTemplateId.value) {
      await fetchTemplateItems(selectedTemplateId.value)
    }
  } catch {
    if (requestId === templateRequestId) {
      ElMessage.error('案件事項テンプレートの取得に失敗しました。')
    }
  } finally {
    if (requestId === templateRequestId) {
      loading.value = false
    }
  }
}

const fetchDeletionHistory = async (page = deletionCurrentPage.value) => {
  const requestId = ++deletionHistoryRequestId
  deletionHistoryLoading.value = true
  try {
    const data = await listCaseChecklistDeletionHistory({
      page,
      page_size: deletionPageSize.value,
    })
    if (requestId !== deletionHistoryRequestId) return
    deletionHistory.value = data.results
    deletionTotal.value = data.count
    latestDeletedAt.value = data.latest_deleted_at
    deletionCurrentPage.value = page
  } catch {
    if (requestId === deletionHistoryRequestId) {
      ElMessage.error('削除履歴の取得に失敗しました。')
    }
  } finally {
    if (requestId === deletionHistoryRequestId) {
      deletionHistoryLoading.value = false
    }
  }
}

const fetchTemplateItems = async (templateId: number, page = itemCurrentPage.value) => {
  const requestId = ++templateItemRequestId
  const data = await listCaseChecklistTemplateItems({
    template: templateId,
    page,
    page_size: itemPageSize.value,
    ordering: 'sort_order',
  })
  if (requestId !== templateItemRequestId) return
  templateItems.value = data.results
  itemTotal.value = data.count
  itemCurrentPage.value = page
}

const selectTemplate = async (template: CaseChecklistTemplate) => {
  selectedTemplateId.value = template.id
  itemCurrentPage.value = 1
  await fetchTemplateItems(template.id, 1)
}

const searchTemplates = async () => {
  templateCurrentPage.value = 1
  await fetchTemplates(1)
}

const handleTemplatePageSizeChange = async (size: number) => {
  templatePageSize.value = size
  templateCurrentPage.value = 1
  await fetchTemplates(1)
}

const handleTemplatePageChange = async (page: number) => {
  await fetchTemplates(page)
}

const handleItemPageSizeChange = async (size: number) => {
  itemPageSize.value = size
  itemCurrentPage.value = 1
  if (selectedTemplateId.value) {
    await fetchTemplateItems(selectedTemplateId.value, 1)
  }
}

const handleItemPageChange = async (page: number) => {
  if (selectedTemplateId.value) {
    await fetchTemplateItems(selectedTemplateId.value, page)
  }
}

const fetchTemplateItemPageByPosition = async (position: number) => {
  if (!selectedTemplateId.value) return
  const targetPage = Math.max(1, Math.ceil(position / itemPageSize.value))
  await fetchTemplateItems(selectedTemplateId.value, targetPage)
}

const handleDeletionPageSizeChange = async (size: number) => {
  deletionPageSize.value = size
  deletionCurrentPage.value = 1
  await fetchDeletionHistory(1)
}

const handleDeletionPageChange = async (page: number) => {
  await fetchDeletionHistory(page)
}

const refreshCurrentTemplateItems = async () => {
  if (!selectedTemplateId.value) return
  await fetchTemplateItems(selectedTemplateId.value, itemCurrentPage.value)
  if (!templateItems.value.length && itemCurrentPage.value > 1) {
    await fetchTemplateItems(selectedTemplateId.value, itemCurrentPage.value - 1)
  }
}

const resetTemplateForm = () => {
  editingTemplateId.value = null
  templateForm.value = {
    name: '',
    description: '',
    is_active: true,
    sort_order: (templates.value.reduce((max, item) => Math.max(max, item.sort_order || 0), 0) || 0) + 1,
  }
  templateFormRef.value?.clearValidate()
}

const openCreateTemplateDialog = () => {
  resetTemplateForm()
  templateDialogVisible.value = true
}

const openEditTemplateDialog = (template: CaseChecklistTemplate) => {
  editingTemplateId.value = template.id
  templateForm.value = {
    name: template.name,
    description: template.description,
    is_active: template.is_active,
    sort_order: template.sort_order,
  }
  templateFormRef.value?.clearValidate()
  templateDialogVisible.value = true
}

const submitTemplate = async () => {
  if (!templateFormRef.value) return
  const valid = await templateFormRef.value.validate().catch(() => false)
  if (!valid) return

  templateSubmitting.value = true
  try {
    if (editingTemplateId.value) {
      await updateCaseChecklistTemplate(editingTemplateId.value, templateForm.value)
      ElMessage.success('テンプレートを更新しました。')
    } else {
      const created = await createCaseChecklistTemplate(templateForm.value)
      selectedTemplateId.value = created.id
      ElMessage.success('テンプレートを追加しました。')
    }
    templateDialogVisible.value = false
    await fetchTemplates(editingTemplateId.value ? templateCurrentPage.value : 1)
  } catch {
    ElMessage.error(editingTemplateId.value ? 'テンプレートの更新に失敗しました。' : 'テンプレートの追加に失敗しました。')
  } finally {
    templateSubmitting.value = false
  }
}

const setTemplateActive = async (template: CaseChecklistTemplate, isActive: boolean) => {
  if (!isActive) {
    try {
      await ElMessageBox.confirm(
        'このテンプレートを無効にしますか？\n既存案件に追加済みの項目には影響しません。',
        '無効化確認',
        { confirmButtonText: '無効化', cancelButtonText: 'キャンセル', type: 'warning' },
      )
    } catch {
      return
    }
  }

  try {
    await updateCaseChecklistTemplate(template.id, { is_active: isActive })
    ElMessage.success(isActive ? '有効にしました。' : '無効にしました。')
    await fetchTemplates(templateCurrentPage.value)
  } catch {
    ElMessage.error('テンプレート状態の更新に失敗しました。')
  }
}

const handleTemplateActionCommand = (template: CaseChecklistTemplate, command: string) => {
  if (command === 'edit') {
    openEditTemplateDialog(template)
    return
  }
  if (command === 'deactivate') {
    setTemplateActive(template, false)
    return
  }
  if (command === 'activate') {
    setTemplateActive(template, true)
    return
  }
  if (command === 'delete') {
    deleteTemplate(template)
  }
}

const resetItemForm = () => {
  editingItemId.value = null
  itemForm.value = {
    template: selectedTemplateId.value || 0,
    category: '',
    name: '',
    item_type: 'document',
    quantity: null,
    unit: '',
    is_required: true,
    description: '',
    responsible_party: '',
    acquisition_place: '',
    required_details: '',
    internal_note: '',
    customer_note: '',
    is_visible_to_customer: true,
    importance_level: 'normal',
    sort_order: (templateItems.value.filter((item) => !item.deleted_at).reduce((max, item) => Math.max(max, item.sort_order || 0), 0) || 0) + 1,
    is_active: true,
  }
  itemFormRef.value?.clearValidate()
}

const openCreateItemDialog = () => {
  if (!selectedTemplateId.value) {
    ElMessage.warning('先にテンプレートを選択してください。')
    return
  }
  resetItemForm()
  itemDialogVisible.value = true
}

const openEditItemDialog = (item: CaseChecklistTemplateItem) => {
  editingItemId.value = item.id
  itemForm.value = {
    template: item.template,
    category: item.category,
    name: item.name,
    item_type: item.item_type,
    quantity: item.quantity,
    unit: item.unit,
    is_required: item.is_required,
    description: item.description,
    responsible_party: item.responsible_party || '',
    acquisition_place: item.acquisition_place || '',
    required_details: item.required_details || '',
    internal_note: item.internal_note || '',
    customer_note: item.customer_note || '',
    is_visible_to_customer: item.is_visible_to_customer,
    importance_level: item.importance_level || 'normal',
    sort_order: item.sort_order,
    is_active: item.is_active,
  }
  itemFormRef.value?.clearValidate()
  itemDialogVisible.value = true
}

const submitItem = async () => {
  if (!itemFormRef.value || !selectedTemplateId.value) return
  const valid = await itemFormRef.value.validate().catch(() => false)
  if (!valid) return

  const category = normalizeOptionText(itemForm.value.category || '')
  const name = normalizeOptionText(itemForm.value.name || '')
  if (!category || !name) {
    ElMessage.warning('分類と項目名を入力してください。')
    return
  }
  itemSubmitting.value = true
  try {
    const payload = {
      ...itemForm.value,
      template: selectedTemplateId.value,
      category,
      name,
      quantity: itemForm.value.quantity || null,
    }
    const isEditing = Boolean(editingItemId.value)
    if (editingItemId.value) {
      await updateCaseChecklistTemplateItem(editingItemId.value, payload)
      ElMessage.success('更新しました。')
    } else {
      await createCaseChecklistTemplateItem(payload)
      ElMessage.success('追加しました。')
    }
    itemDialogVisible.value = false
    if (category && !categoryCandidates.value.includes(category)) {
      categoryCandidates.value = [...categoryCandidates.value, category]
    }
    if (isEditing) {
      await refreshCurrentTemplateItems()
    } else if (selectedTemplateId.value) {
      const lastPage = Math.max(1, Math.ceil((itemTotal.value + 1) / itemPageSize.value))
      await fetchTemplateItems(selectedTemplateId.value, lastPage)
    }
    await fetchTemplates(templateCurrentPage.value)
  } catch {
    ElMessage.error(editingItemId.value ? '項目の更新に失敗しました。' : '項目の追加に失敗しました。')
  } finally {
    itemSubmitting.value = false
  }
}

const fetchAllTemplateItemsForNotice = async () => {
  if (!selectedTemplateId.value) return []
  const rows: CaseChecklistTemplateItem[] = []
  let page = 1
  while (true) {
    const data = await listCaseChecklistTemplateItems({
      template: selectedTemplateId.value,
      page,
      page_size: 100,
      ordering: 'sort_order',
      is_active: true,
    })
    rows.push(...data.results)
    if (rows.length >= data.count || !data.results.length) break
    page += 1
  }
  return rows
    .filter((item) => item.is_active && item.is_visible_to_customer)
    .sort((left, right) => (left.sort_order || 0) - (right.sort_order || 0) || left.id - right.id)
}

const buildMaterialNoticeText = (items: CaseChecklistTemplateItem[]) => {
  const language = materialNoticeOptions.value.language
  const noticeType = materialNoticeOptions.value.noticeType
  const opening = language === 'zh'
    ? {
        initial: '感谢您的信任，并委托我们办理本次手续。\n\n关于本次申请，请您准备以下材料：',
        additional: '关于本次手续，还需要您补充准备以下材料：',
        reminder: '关于本次手续，以下材料尚未确认收到，请您准备完成后发送给我们：',
      }[noticeType]
    : {
        initial: 'この度は弊社へご依頼いただき、誠にありがとうございます。\n\n本件のお手続きにあたり、以下の資料をご準備ください。',
        additional: '本件のお手続きにあたり、追加で以下の資料をご準備ください。',
        reminder: '本件のお手続きにあたり、以下の未完了資料をご確認ください。',
      }[noticeType]
  const closing = language === 'zh'
    ? '材料准备完成后，请拍照或扫描发送给我们确认。\n如有不清楚的地方，请随时联系我们。'
    : 'ご準備ができましたら、写真またはスキャンデータをお送りください。\nご不明な点がございましたら、いつでもご連絡ください。'
  const body = items.map((item, index) => {
    const lines = [`${index + 1}. ${item.name}`]
    if (materialNoticeOptions.value.showPlace && item.acquisition_place) {
      lines.push(language === 'zh' ? `开具地点：${item.acquisition_place}` : `取得場所：${item.acquisition_place}`)
    }
    if (materialNoticeOptions.value.showRequiredDetails && item.required_details) {
      lines.push(language === 'zh' ? `具体要求：${item.required_details}` : `必要内容：${item.required_details}`)
    }
    if (materialNoticeOptions.value.showCustomerNote && item.customer_note) {
      lines.push(language === 'zh' ? `注意事项：${item.customer_note}` : `注意事項：${item.customer_note}`)
    }
    return lines.join('\n')
  }).join('\n\n')
  return [opening, body, closing].filter(Boolean).join('\n\n')
}

const openMaterialNoticeDialog = async () => {
  if (!selectedTemplateId.value) {
    ElMessage.warning('先にテンプレートを選択してください。')
    return
  }
  try {
    const items = await fetchAllTemplateItemsForNotice()
    if (!items.length) {
      ElMessage.warning('顧客向けに表示できる項目がありません。')
      return
    }
    materialNoticeText.value = buildMaterialNoticeText(items)
    materialNoticeDialogVisible.value = true
  } catch {
    ElMessage.error('材料案内の作成に失敗しました。')
  }
}

const refreshMaterialNoticeText = async () => {
  const items = await fetchAllTemplateItemsForNotice()
  materialNoticeText.value = buildMaterialNoticeText(items)
}

const copyMaterialNoticeText = async () => {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(materialNoticeText.value)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = materialNoticeText.value
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.focus()
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    ElMessage.success('コピーしました。')
  } catch {
    ElMessage.error('コピーに失敗しました。文案を手動で選択してください。')
  }
}

const setItemActive = async (item: CaseChecklistTemplateItem, isActive: boolean) => {
  if (!isActive) {
    try {
      await ElMessageBox.confirm(
        'この項目を無効にしますか？\n既存案件に追加済みの項目には影響しません。',
        '無効化確認',
        { confirmButtonText: '無効化', cancelButtonText: 'キャンセル', type: 'warning' },
      )
    } catch {
      return
    }
  }

  try {
    await updateCaseChecklistTemplateItem(item.id, { is_active: isActive })
    ElMessage.success(isActive ? '有効にしました。' : '無効にしました。')
    await refreshCurrentTemplateItems()
  } catch {
    ElMessage.error('項目状態の更新に失敗しました。')
  }
}

const handleItemActionCommand = (item: CaseChecklistTemplateItem, command: string) => {
  if (command === 'edit') {
    openEditItemDialog(item)
    return
  }
  if (command === 'move-up') {
    moveItem(item, -1)
    return
  }
  if (command === 'move-down') {
    moveItem(item, 1)
    return
  }
  if (command === 'deactivate') {
    setItemActive(item, false)
    return
  }
  if (command === 'activate') {
    setItemActive(item, true)
    return
  }
  if (command === 'delete') {
    deleteItem(item)
  }
}

const moveItem = async (item: CaseChecklistTemplateItem, direction: -1 | 1) => {
  try {
    const result = direction < 0
      ? await moveCaseChecklistTemplateItemUp(item.id)
      : await moveCaseChecklistTemplateItemDown(item.id)
    if (result.message) {
      if (result.success) {
        ElMessage.success(result.message)
      } else {
        ElMessage.info(result.message)
      }
    }
    await fetchTemplateItemPageByPosition(result.position)
  } catch {
    ElMessage.error('並び順の更新に失敗しました。')
  }
}

const deleteTemplate = async (template: CaseChecklistTemplate) => {
  try {
    await ElMessageBox.confirm(
      'このテンプレートを削除しますか？\nテンプレート内の項目も削除履歴へ移動します。\n既存案件に追加済みの項目には影響しません。',
      '削除確認',
      { confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning' },
    )
    await softDeleteCaseChecklistTemplate(template.id)
    ElMessage.success('削除しました。')
    if (selectedTemplateId.value === template.id) {
      selectedTemplateId.value = null
      templateItems.value = []
    }
    await fetchTemplates(templateCurrentPage.value)
    if (!templates.value.length && templateCurrentPage.value > 1) {
      await fetchTemplates(templateCurrentPage.value - 1)
    }
    await fetchDeletionHistory(deletionCurrentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('削除に失敗しました。')
    }
  }
}

const deleteItem = async (item: CaseChecklistTemplateItem) => {
  try {
    await ElMessageBox.confirm(
      'このテンプレート項目を削除しますか？\n既存案件に追加済みの項目には影響しません。',
      '削除確認',
      { confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning' },
    )
    await softDeleteCaseChecklistTemplateItem(item.id)
    ElMessage.success('削除しました。')
    await refreshCurrentTemplateItems()
    await fetchDeletionHistory(deletionCurrentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('削除に失敗しました。')
    }
  }
}

const restoreDeletedItem = async (row: CaseChecklistDeletionHistoryItem) => {
  try {
    if (row.object_type === 'template') {
      await restoreCaseChecklistTemplate(row.id)
    } else {
      await restoreCaseChecklistTemplateItem(row.id)
    }
    ElMessage.success('復元しました。')
    await fetchTemplates(templateCurrentPage.value)
    await fetchDeletionHistory(deletionCurrentPage.value)
    if (!deletionHistory.value.length && deletionCurrentPage.value > 1) {
      await fetchDeletionHistory(deletionCurrentPage.value - 1)
    }
    await refreshCurrentTemplateItems()
    await fetchItemOptions()
  } catch (error) {
    ElMessage.error('復元に失敗しました。所属テンプレートが削除されている場合は、先にテンプレートを復元してください。')
  }
}

const generateDemoData = async () => {
  try {
    await ElMessageBox.confirm(
      '標準の案件事項テンプレートを取り込みます。\n既存のテンプレートや案件データは削除されません。\n既に登録済みのテンプレートと項目は重複登録されません。',
      '標準テンプレート取込',
      {
        confirmButtonText: '取り込む',
        cancelButtonText: 'キャンセル',
        type: 'info',
      },
    )
  } catch {
    return
  }

  demoSeedSubmitting.value = true
  try {
    const result = await seedStandardCaseChecklistTemplates()
    selectedTemplateId.value = result.template_ids[0] || null
    templateCurrentPage.value = 1
    itemCurrentPage.value = 1
    await fetchItemOptions()
    await fetchTemplates(1)
    const skippedMessage = result.templates_skipped_deleted || result.template_items_skipped_deleted
      ? `、削除履歴内のためスキップ：テンプレート${result.templates_skipped_deleted}件・項目${result.template_items_skipped_deleted}件`
      : ''
    ElMessage.success(
      `${result.message} テンプレート新規：${result.templates_created}件、テンプレート更新：${result.templates_updated}件、`
      + `項目新規：${result.template_items_created}件、項目更新：${result.template_items_updated}件${skippedMessage}`,
    )
  } catch {
    ElMessage.error('標準テンプレートの取込に失敗しました。')
  } finally {
    demoSeedSubmitting.value = false
  }
}

onMounted(() => {
  fetchSettingData()
  fetchItemOptions()
  fetchTemplates()
  fetchDeletionHistory()
})
</script>

<template>
  <section class="page-section">
    <div class="page-header page-header-row">
      <div>
        <h1>案件・担当設定管理</h1>
        <p>案件業務で使用する案件種別、申請区分、案件進捗、Checklist、取得場所、準備者区分、担当者を管理します。</p>
        <p class="page-note">各設定の使用場所と影響範囲を確認しながら変更できます。</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="demoSeedSubmitting" @click="generateDemoData">標準テンプレート取込</el-button>
        <el-button type="primary" @click="openCreateTemplateDialog">新規テンプレート追加</el-button>
      </div>
    </div>

    <el-card shadow="never" class="settings-section-card">
      <template #header><h2>案件関連設定</h2></template>
      <el-tabs v-model="caseSettingTab" class="settings-secondary-tabs">
        <el-tab-pane label="案件種別" name="case-types">
          <el-alert type="info" show-icon :closable="false" class="usage-alert">
            <template #title>
              使用場所：{{ usageNotes.caseType.use.join(' / ') }}<br>
              影響範囲：{{ usageNotes.caseType.impact.join(' / ') }}
            </template>
          </el-alert>
          <div class="setting-card-header"><span>案件種別</span><el-button type="primary" @click="openSettingDialog('case-type')">新規追加</el-button></div>
          <el-table :data="caseTypes" stripe>
            <el-table-column prop="name" label="表示名称" min-width="180" />
            <el-table-column prop="code" label="内部code" min-width="160" />
            <el-table-column prop="number_abbreviation" label="案件番号略称" width="130" />
            <el-table-column prop="sort_order" label="順番" width="90" />
            <el-table-column label="状態" width="90"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '有効' : '無効' }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="90"><template #default="{ row }"><el-button text type="primary" @click="openSettingDialog('case-type', row)">編集</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="申請区分" name="application-categories">
          <el-alert type="info" show-icon :closable="false" class="usage-alert">
            <template #title>
              使用場所：{{ usageNotes.applicationCategory.use.join(' / ') }}<br>
              影響範囲：{{ usageNotes.applicationCategory.impact.join(' / ') }}
            </template>
          </el-alert>
          <div class="setting-card-header"><span>申請区分</span><el-button type="primary" @click="openSettingDialog('application-category')">新規追加</el-button></div>
          <el-table :data="applicationCategories" stripe>
            <el-table-column prop="name" label="表示名称" min-width="180" />
            <el-table-column prop="code" label="内部code" min-width="160" />
            <el-table-column prop="number_abbreviation" label="案件番号略称" width="130" />
            <el-table-column prop="sort_order" label="順番" width="90" />
            <el-table-column label="状態" width="90"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '有効' : '無効' }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="90"><template #default="{ row }"><el-button text type="primary" @click="openSettingDialog('application-category', row)">編集</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="案件進捗" name="case-status">
          <el-alert type="info" show-icon :closable="false" class="usage-alert">
            <template #title>
              使用場所：{{ usageNotes.status.use.join(' / ') }}<br>
              影響範囲：{{ usageNotes.status.impact.join(' / ') }}
            </template>
          </el-alert>
          <el-table :data="caseStatusSettings" stripe>
            <el-table-column prop="display_name" label="表示名" min-width="180" />
            <el-table-column prop="code" label="内部code" min-width="180" />
            <el-table-column prop="sort_order" label="順番" width="90" />
            <el-table-column label="表示" width="90"><template #default="{ row }"><el-tag :type="row.is_visible ? 'success' : 'info'">{{ row.is_visible ? '表示' : '非表示' }}</el-tag></template></el-table-column>
            <el-table-column label="操作" width="90"><template #default="{ row }"><el-button text type="primary" @click="openSettingDialog('status', row)">編集</el-button></template></el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="取得場所・準備者区分" name="presets">
          <el-alert type="info" show-icon :closable="false" class="usage-alert">
            <template #title>
              使用場所：{{ usageNotes.presets.use.join(' / ') }}<br>
              影響範囲：{{ usageNotes.presets.impact.join(' / ') }}
            </template>
          </el-alert>
          <div class="settings-two-column">
            <div>
              <div class="setting-card-header"><span>取得場所</span><el-button type="primary" @click="openSettingDialog('acquisition-place')">新規追加</el-button></div>
              <el-table :data="acquisitionPlacePresets" stripe>
                <el-table-column prop="name" label="名称" min-width="170" />
                <el-table-column prop="sort_order" label="順番" width="80" />
                <el-table-column label="状態" width="80"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '有効' : '無効' }}</el-tag></template></el-table-column>
                <el-table-column label="操作" width="90"><template #default="{ row }"><el-button text type="primary" @click="openSettingDialog('acquisition-place', row)">編集</el-button></template></el-table-column>
              </el-table>
            </div>
            <div>
              <div class="setting-card-header"><span>準備者区分</span><el-button type="primary" @click="openSettingDialog('responsible-party')">新規追加</el-button></div>
              <el-table :data="responsiblePartyPresets" stripe>
                <el-table-column prop="name" label="名称" min-width="150" />
                <el-table-column prop="code" label="code" min-width="120" />
                <el-table-column prop="sort_order" label="順番" width="80" />
                <el-table-column label="状態" width="80"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '有効' : '無効' }}</el-tag></template></el-table-column>
                <el-table-column label="操作" width="90"><template #default="{ row }"><el-button text type="primary" @click="openSettingDialog('responsible-party', row)">編集</el-button></template></el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-alert type="info" show-icon :closable="false" class="usage-alert">
      <template #title>
        Checklistテンプレート<br>
        使用場所：{{ usageNotes.checklist.use.join(' / ') }}<br>
        影響範囲：{{ usageNotes.checklist.impact.join(' / ') }}
      </template>
    </el-alert>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-input
          v-model="templateSearch"
          clearable
          placeholder="テンプレート名で検索"
          @keyup.enter="searchTemplates"
          @clear="searchTemplates"
        />
        <el-select v-model="templateActiveFilter" class="status-filter" @change="searchTemplates">
          <el-option label="すべて" value="" />
          <el-option label="有効" value="true" />
          <el-option label="無効" value="false" />
        </el-select>
        <el-button type="primary" @click="searchTemplates">検索</el-button>
      </div>
    </el-card>

    <div class="checklist-layout" v-loading="loading">
      <el-card shadow="never">
        <template #header>テンプレート一覧</template>
        <el-table :data="templates" stripe highlight-current-row row-key="id" @row-click="selectTemplate">
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column label="項目数" width="90">
            <template #default="{ row }">{{ row.item_count }}</template>
          </el-table-column>
          <el-table-column label="状態" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '有効' : '無効' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="更新日時" width="160">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" align="center">
            <template #default="{ row }">
              <el-dropdown trigger="click" @command="handleTemplateActionCommand(row, $event)">
                <el-button text type="primary" class="table-action-trigger" @click.stop>
                  操作
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">編集</el-dropdown-item>
                    <el-dropdown-item v-if="row.is_active" command="deactivate" divided>無効化</el-dropdown-item>
                    <el-dropdown-item v-else command="activate" divided>有効化</el-dropdown-item>
                    <el-dropdown-item command="delete" divided class="danger-item">削除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="!templates.length" class="empty-text">テンプレートがありません</p>
        <div v-if="templateTotal" class="table-footer">
          <el-pagination
            background
            v-model:current-page="templateCurrentPage"
            v-model:page-size="templatePageSize"
            :page-sizes="[20, 50, 100]"
            :total="templateTotal"
            layout="total, sizes, prev, pager, next"
            @current-change="handleTemplatePageChange"
            @size-change="handleTemplatePageSizeChange"
          />
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>{{ selectedTemplate?.name || 'テンプレート項目' }}</span>
            <div class="header-actions">
              <el-button :disabled="!selectedTemplateId" @click="openMaterialNoticeDialog">顧客向け材料案内</el-button>
              <el-button type="primary" :disabled="!selectedTemplateId" @click="openCreateItemDialog">項目追加</el-button>
            </div>
          </div>
        </template>
        <el-table :data="sortedItems" stripe row-key="id">
          <el-table-column label="順番" width="70">
            <template #default="{ $index }">{{ (itemCurrentPage - 1) * itemPageSize + $index + 1 }}</template>
          </el-table-column>
          <el-table-column prop="category" label="分類" min-width="110">
            <template #default="{ row }">{{ row.category || '-' }}</template>
          </el-table-column>
          <el-table-column prop="name" label="事項名" min-width="180" />
          <el-table-column label="タイプ" width="110">
            <template #default="{ row }">{{ getItemTypeLabel(row.item_type) }}</template>
          </el-table-column>
          <el-table-column label="手続先" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.acquisition_place || '-' }}</template>
          </el-table-column>
          <el-table-column label="必要内容" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ row.required_details || row.description || '-' }}</template>
          </el-table-column>
          <el-table-column label="顧客注意" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.customer_note || '-' }}</template>
          </el-table-column>
          <el-table-column label="重要" width="90">
            <template #default="{ row }">
              <el-tag :type="getImportanceOption(row.importance_level).type">
                {{ getImportanceLabel(row.importance_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="顧客表示" width="100">
            <template #default="{ row }">{{ row.is_visible_to_customer ? '表示' : '非表示' }}</template>
          </el-table-column>
          <el-table-column label="数量" width="90">
            <template #default="{ row }">
              {{ row.quantity ? `${row.quantity}${row.unit || ''}` : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="必須" width="80">
            <template #default="{ row }">{{ row.is_required ? '必須' : '任意' }}</template>
          </el-table-column>
          <el-table-column label="状態" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '有効' : '無効' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" align="center">
            <template #default="{ row }">
              <el-dropdown trigger="click" @command="handleItemActionCommand(row, $event)">
                <el-button text type="primary" class="table-action-trigger">
                  操作
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">編集</el-dropdown-item>
                    <el-dropdown-item command="move-up" :disabled="!row.can_move_up">上へ</el-dropdown-item>
                    <el-dropdown-item command="move-down" :disabled="!row.can_move_down">下へ</el-dropdown-item>
                    <el-dropdown-item v-if="row.is_active" command="deactivate" divided>無効化</el-dropdown-item>
                    <el-dropdown-item v-else command="activate" divided>有効化</el-dropdown-item>
                    <el-dropdown-item command="delete" divided class="danger-item">削除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="selectedTemplateId && !templateItems.length" class="empty-text">項目が登録されていません。</p>
        <p v-if="!selectedTemplateId" class="empty-text">テンプレートを選択してください</p>
        <div v-if="selectedTemplateId && itemTotal" class="table-footer">
          <el-pagination
            background
            v-model:current-page="itemCurrentPage"
            v-model:page-size="itemPageSize"
            :page-sizes="[20, 50, 100]"
            :total="itemTotal"
            layout="total, sizes, prev, pager, next"
            @current-change="handleItemPageChange"
            @size-change="handleItemPageSizeChange"
          />
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="deletion-history-summary-card">
      <div class="deletion-history-summary">
        <div>
          <h2>削除履歴</h2>
          <p>最近削除されたテンプレートと項目を確認・復元できます。</p>
        </div>
        <div class="deletion-history-meta">
          <span>削除件数：{{ deletionTotal }}</span>
          <span>最終削除：{{ latestDeletedAt ? formatDateTime(latestDeletedAt) : '-' }}</span>
        </div>
        <el-button
          plain
          :disabled="!deletionTotal"
          :loading="deletionHistoryLoading"
          @click="deletionHistoryDialogVisible = true"
        >
          履歴を確認
        </el-button>
      </div>
      <p v-if="!deletionTotal" class="empty-text compact-empty-text">削除履歴はありません。</p>
    </el-card>

    <el-card shadow="never" class="settings-section-card">
      <template #header><h2>担当者管理</h2></template>
      <el-alert type="info" show-icon :closable="false" class="usage-alert">
        <template #title>
          案件の担当者として選択する社員・スタッフを管理します。<br>
          使用場所：{{ usageNotes.employee.use.join(' / ') }}<br>
          影響範囲：{{ usageNotes.employee.impact.join(' / ') }}
        </template>
      </el-alert>
      <div class="setting-card-header"><span>担当者</span><el-button type="primary" @click="openSettingDialog('employee')">新規追加</el-button></div>
      <el-table :data="employees" stripe>
        <el-table-column prop="name" label="氏名" min-width="160" />
        <el-table-column prop="email" label="メール" min-width="220"><template #default="{ row }">{{ row.email || '-' }}</template></el-table-column>
        <el-table-column prop="phone" label="電話" min-width="150"><template #default="{ row }">{{ row.phone || '-' }}</template></el-table-column>
        <el-table-column label="有効状態" width="110"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '有効' : '無効' }}</el-tag></template></el-table-column>
        <el-table-column label="更新日時" min-width="160"><template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="{ row }"><el-button text type="primary" @click="openSettingDialog('employee', row)">編集</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="settingDialogVisible"
      title="設定編集"
      width="560px"
      @closed="resetSettingForm"
    >
      <el-form ref="settingFormRef" :model="settingForm" :rules="settingRules" label-position="top">
        <template v-if="settingDialogType === 'status'">
          <el-form-item label="内部code">
            <el-input v-model="settingForm.code" disabled />
          </el-form-item>
          <el-form-item label="表示名" prop="display_name">
            <el-input v-model="settingForm.display_name" />
          </el-form-item>
          <el-form-item label="表示順">
            <el-input-number v-model="settingForm.sort_order" :min="0" class="form-control" />
          </el-form-item>
          <el-form-item label="表示可否">
            <el-switch v-model="settingForm.is_visible" active-text="表示" inactive-text="非表示" />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="名称" prop="name">
            <el-input v-model="settingForm.name" />
          </el-form-item>
          <el-form-item v-if="['case-type', 'application-category', 'responsible-party'].includes(settingDialogType)" label="内部code">
            <el-input v-model="settingForm.code" :disabled="!!editingSettingId" placeholder="作成後は変更できません" />
          </el-form-item>
          <el-form-item v-if="['case-type', 'application-category'].includes(settingDialogType)" label="案件番号略称">
            <el-input v-model="settingForm.number_abbreviation" />
          </el-form-item>
          <el-form-item v-if="settingDialogType === 'employee'" label="メール">
            <el-input v-model="settingForm.email" />
          </el-form-item>
          <el-form-item v-if="settingDialogType === 'employee'" label="電話">
            <el-input v-model="settingForm.phone" />
          </el-form-item>
          <el-form-item v-if="settingDialogType !== 'employee'" label="表示順">
            <el-input-number v-model="settingForm.sort_order" :min="0" class="form-control" />
          </el-form-item>
          <el-form-item label="有効状態">
            <el-switch v-model="settingForm.is_active" active-text="有効" inactive-text="無効" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="settingDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="settingSubmitting" @click="submitSetting">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="templateDialogVisible"
      :title="editingTemplateId ? 'テンプレート編集' : 'テンプレート追加'"
      width="560px"
      @closed="resetTemplateForm"
    >
      <el-form ref="templateFormRef" :model="templateForm" :rules="templateRules" label-position="top">
        <el-form-item label="テンプレート名" prop="name">
          <el-input v-model="templateForm.name" />
        </el-form-item>
        <el-form-item label="説明" prop="description">
          <el-input v-model="templateForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="表示順" prop="sort_order">
            <el-input-number v-model="templateForm.sort_order" :min="1" :step="1" class="form-control" />
          </el-form-item>
          <el-form-item label="状態" prop="is_active">
            <el-switch v-model="templateForm.is_active" active-text="有効" inactive-text="無効" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="templateDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="templateSubmitting" @click="submitTemplate">
          {{ editingTemplateId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="itemDialogVisible"
      :title="editingItemId ? '項目編集' : '項目追加'"
      width="680px"
      @closed="resetItemForm"
    >
      <el-form ref="itemFormRef" :model="itemForm" :rules="itemRules" label-position="top">
        <h3 class="form-section-title">基本情報</h3>
        <div class="form-grid">
          <el-form-item label="分類" prop="category">
            <el-select
              v-model="itemForm.category"
              allow-create
              clearable
              default-first-option
              filterable
              placeholder="分類を選択または入力"
              class="form-control"
            >
              <el-option v-for="category in categoryOptions" :key="category" :label="category" :value="category" />
            </el-select>
          </el-form-item>
          <el-form-item label="事項名" prop="name">
            <el-autocomplete
              v-model="itemForm.name"
              :fetch-suggestions="queryItemNameSuggestions"
              clearable
              placeholder="事項名を入力"
              value-key="value"
              class="form-control"
            />
          </el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="種別" prop="item_type">
            <el-select v-model="itemForm.item_type" class="form-control">
              <el-option
                v-for="option in itemTypeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="数量" prop="quantity">
            <el-input-number v-model="itemForm.quantity" :min="1" class="form-control" />
          </el-form-item>
          <el-form-item label="単位" prop="unit">
            <el-input v-model="itemForm.unit" placeholder="通、份、部など" />
          </el-form-item>
        </div>
        <h3 class="form-section-title">办理情報</h3>
        <div class="form-grid">
          <el-form-item label="準備者／担当区分" prop="responsible_party">
            <el-select v-model="itemForm.responsible_party" class="form-control">
              <el-option
                v-for="option in responsiblePartyOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="手続先・取得場所" prop="acquisition_place">
            <el-input v-model="itemForm.acquisition_place" placeholder="大阪南税務署、本人準備など" />
          </el-form-item>
        </div>
        <el-form-item label="必要内容" prop="required_details">
          <el-input v-model="itemForm.required_details" type="textarea" :rows="3" />
        </el-form-item>
        <h3 class="form-section-title">顧客通知</h3>
        <el-form-item label="顧客向け注意事項" prop="customer_note">
          <el-input v-model="itemForm.customer_note" type="textarea" :rows="3" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="必須" prop="is_required">
            <el-switch v-model="itemForm.is_required" active-text="必須" inactive-text="任意" />
          </el-form-item>
          <el-form-item label="顧客表示" prop="is_visible_to_customer">
            <el-switch v-model="itemForm.is_visible_to_customer" active-text="表示" inactive-text="非表示" />
          </el-form-item>
          <el-form-item label="重要レベル" prop="importance_level">
            <el-select v-model="itemForm.importance_level" class="form-control">
              <el-option
                v-for="option in importanceLevelOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="状態" prop="is_active">
            <el-switch v-model="itemForm.is_active" active-text="有効" inactive-text="無効" />
          </el-form-item>
        </div>
        <h3 class="form-section-title">内部管理</h3>
        <el-form-item label="普通説明" prop="description">
          <el-input v-model="itemForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="内部備考" prop="internal_note">
          <el-input v-model="itemForm.internal_note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="itemSubmitting" @click="submitItem">
          {{ editingItemId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deletionHistoryDialogVisible" title="削除履歴" width="70%" class="deletion-history-dialog">
      <el-table v-loading="deletionHistoryLoading" :data="deletionHistory" stripe row-key="id" size="small">
        <el-table-column label="種別" width="130">
          <template #default="{ row }">{{ row.object_type === 'template' ? 'テンプレート' : 'テンプレート項目' }}</template>
        </el-table-column>
        <el-table-column prop="name" label="名称" min-width="180" />
        <el-table-column label="所属テンプレート" min-width="180">
          <template #default="{ row }">{{ row.template_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="削除日時" width="170">
          <template #default="{ row }">{{ formatDateTime(row.deleted_at) }}</template>
        </el-table-column>
        <el-table-column label="復元" width="90" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" :disabled="!row.can_restore" @click="restoreDeletedItem(row)">復元</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!deletionHistory.length" class="empty-text">削除履歴はありません。</p>
      <div v-if="deletionTotal" class="table-footer">
        <el-pagination
          background
          v-model:current-page="deletionCurrentPage"
          v-model:page-size="deletionPageSize"
          :page-sizes="[10, 20, 50]"
          :total="deletionTotal"
          layout="total, sizes, prev, pager, next"
          @current-change="handleDeletionPageChange"
          @size-change="handleDeletionPageSizeChange"
        />
      </div>
    </el-dialog>

    <el-dialog v-model="materialNoticeDialogVisible" title="顧客向け材料案内" width="760px" class="material-notice-dialog">
      <div class="notice-option-grid">
        <el-form-item label="文案タイプ">
          <el-select v-model="materialNoticeOptions.noticeType" class="form-control" @change="refreshMaterialNoticeText">
            <el-option label="初回材料案内" value="initial" />
            <el-option label="追加資料案内" value="additional" />
            <el-option label="未完了資料リマインド" value="reminder" />
          </el-select>
        </el-form-item>
        <el-form-item label="言語">
          <el-select v-model="materialNoticeOptions.language" class="form-control" @change="refreshMaterialNoticeText">
            <el-option label="中文" value="zh" />
            <el-option label="日本語" value="ja" />
          </el-select>
        </el-form-item>
      </div>
      <div class="notice-switches">
        <el-checkbox v-model="materialNoticeOptions.showPlace" @change="refreshMaterialNoticeText">取得場所</el-checkbox>
        <el-checkbox v-model="materialNoticeOptions.showRequiredDetails" @change="refreshMaterialNoticeText">必要内容</el-checkbox>
        <el-checkbox v-model="materialNoticeOptions.showCustomerNote" @change="refreshMaterialNoticeText">注意事項</el-checkbox>
      </div>
      <el-input v-model="materialNoticeText" type="textarea" :rows="18" />
      <template #footer>
        <el-button @click="materialNoticeDialogVisible = false">閉じる</el-button>
        <el-button @click="refreshMaterialNoticeText">自動生成に戻す</el-button>
        <el-button type="primary" @click="copyMaterialNoticeText">コピー</el-button>
      </template>
    </el-dialog>

  </section>
</template>

<style scoped>
.settings-section-card,
.usage-alert {
  margin-bottom: 16px;
}

.settings-section-card h2 {
  margin: 0;
  font-size: 18px;
}

.setting-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.settings-two-column {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.checklist-layout {
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(520px, 1.4fr);
  gap: 16px;
}

.deletion-history-summary-card {
  margin-top: 16px;
}

.deletion-history-summary {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto;
  align-items: center;
  gap: 16px;
}

.deletion-history-summary h2 {
  margin: 0 0 4px;
  font-size: 16px;
}

.deletion-history-summary p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.deletion-history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.compact-empty-text {
  margin: 8px 0 0;
}

.filter-row {
  display: flex;
  gap: 12px;
}

.status-filter {
  max-width: 140px;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.page-note {
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.table-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}

.form-section-title {
  margin: 16px 0 10px;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.notice-option-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.notice-switches {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  margin-bottom: 12px;
}

@media (max-width: 768px) {
  .deletion-history-summary {
    grid-template-columns: 1fr;
  }

  :deep(.deletion-history-dialog) {
    width: 95% !important;
  }

  :deep(.material-notice-dialog) {
    width: 95% !important;
  }

  .notice-option-grid {
    grid-template-columns: 1fr;
  }
}

</style>
