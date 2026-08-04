<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  applyCaseChecklistTemplate,
  cancelCase,
  changeCaseRegistrationStatus,
  changeCaseStatus,
  createCaseChecklistItem,
  deleteCaseChecklistItem,
  getCase,
  listCaseApplicationCategories,
  listCaseChecklistItemNameSuggestions,
  listCaseChecklistItems,
  listCaseChecklistTemplates,
  listCaseTypeMasters,
  listChecklistItemPresets,
  previewRegenerateCaseNumber,
  regenerateCaseNumber,
  updateCase,
  updateCaseChecklistItem,
} from '../api/cases'
import { listCompanies } from '../api/companies'
import { listCustomers } from '../api/customers'
import { listEmployees } from '../api/employees'
import { createTimeline, listTimelines, updateTimeline } from '../api/timelines'
import type {
  Case,
  CaseApplicationCategory,
  CaseChecklistItem,
  CaseChecklistItemPayload,
  CaseChecklistItemType,
  CaseChecklistTemplate,
  CasePayload,
  CaseTypeMaster,
  ChecklistItemPreset,
  Company,
  Customer,
  Employee,
  ItemNameSuggestion,
  Timeline,
  TimelinePayload,
} from '../types/api'
import {
  caseRegistrationStatusOptions,
  caseStatusOptions,
  getCaseDisplayStatus,
  getCaseDisplayStatusTagType,
  getCaseRegistrationStatusLabel,
  getCaseRegistrationStatusTagType,
} from '../utils/caseStatus'
import { formatDate, formatDateTime } from '../utils/date'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const caseDetail = ref<Case | null>(null)
const timelines = ref<Timeline[]>([])
const checklistItems = ref<CaseChecklistItem[]>([])
const checklistTemplates = ref<CaseChecklistTemplate[]>([])
const checklistItemPresets = ref<ChecklistItemPreset[]>([])
const timelineSubmitting = ref(false)
const timelineDialogVisible = ref(false)
const editingTimelineId = ref<number | null>(null)
const timelineFormRef = ref<FormInstance>()
const progressUpdateDialogVisible = ref(false)
const progressUpdateSubmitting = ref(false)
const progressUpdateNoteVisible = ref(false)
const progressUpdateWarnings = ref<Array<{ code: string, message: string }>>([])
const progressHistoryCollapse = ref<string[]>([])
const correctionDialogVisible = ref(false)
const correctionSubmitting = ref(false)
const registrationStatusDialogVisible = ref(false)
const registrationStatusChanging = ref(false)
const registrationStatusWarnings = ref<Array<{ code: string, message: string }>>([])
const cancelSubmitting = ref(false)
const regeneratingCaseNumber = ref(false)
const cancelDialogVisible = ref(false)
const cancelFormRef = ref<FormInstance>()
const checklistItemSubmitting = ref(false)
const checklistItemDialogVisible = ref(false)
const editingChecklistItemId = ref<number | null>(null)
const checklistItemFormRef = ref<FormInstance>()
const applyTemplateDialogVisible = ref(false)
const selectedChecklistTemplateId = ref<number | null>(null)
const applyingChecklistTemplate = ref(false)
const customers = ref<Customer[]>([])
const companies = ref<Company[]>([])
const employees = ref<Employee[]>([])
const caseTypes = ref<CaseTypeMaster[]>([])
const applicationCategories = ref<CaseApplicationCategory[]>([])
const basicInfoDialogVisible = ref(false)
const basicInfoSubmitting = ref(false)
const basicInfoForm = ref<{
  case_type_master: number | null
  application_category: number | null
  customer: number | null
  company: number | null
  responsible_employee: number | null
}>({
  case_type_master: null,
  application_category: null,
  customer: null,
  company: null,
  responsible_employee: null,
})

const caseId = computed(() => Number(route.params.id))
const displayStatus = computed(() => getCaseDisplayStatus(caseDetail.value?.status))
const canCancelCase = computed(() => (
  caseDetail.value
  && !['withdrawn', 'completed'].includes(caseDetail.value.status)
))

const timelineTitleOptions = [
  '受任',
  '申請',
  '受付',
  '補正通知',
  '補正提出',
  '追加資料依頼',
  '追加資料提出',
  '許可通知',
  '不許可通知',
  '完了',
  '中止',
  'その他',
]

const checklistItemTypeOptions = [
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

const customerNoticeDialogVisible = ref(false)
const customerNoticeText = ref('')
const customerNoticeOptions = ref({
  noticeType: 'initial' as NoticeType,
  language: 'zh' as NoticeLanguage,
  onlyIncomplete: false,
})

const timelineForm = ref<TimelinePayload>({
  case: 0,
  occurred_at: null,
  title: '',
  content: '',
  is_visible_to_client: false,
})
const progressUpdateForm = ref({
  new_status: '',
  change_date: '',
  note: '',
  force: false,
  applied_at: null as string | null,
  application_receipt_number: '',
  additional_documents_requested_at: null as string | null,
  additional_documents_detail: '',
  additional_documents_due_at: null as string | null,
  additional_documents_submitted_at: null as string | null,
  result_notified_at: null as string | null,
  result_received_at: null as string | null,
  permission_number: '',
  result_note: '',
  withdrawn_at: null as string | null,
  completed_at: null as string | null,
})
const correctionForm = ref({
  consulted_at: null as string | null,
  accepted_at: null as string | null,
  document_collection_started_at: null as string | null,
  documents_completed_at: null as string | null,
  application_ready_at: null as string | null,
  applied_at: null as string | null,
  application_receipt_number: '',
  review_started_at: null as string | null,
  additional_documents_requested_at: null as string | null,
  additional_documents_detail: '',
  additional_documents_due_at: null as string | null,
  additional_documents_submitted_at: null as string | null,
  result_notified_at: null as string | null,
  result_received_at: null as string | null,
  permission_number: '',
  result_note: '',
  withdrawn_at: null as string | null,
  completed_at: null as string | null,
})
const registrationStatusForm = ref({
  new_status: '',
  change_date: '',
  note: '',
  force: false,
})
const cancelForm = ref({
  reason: '',
})
const checklistItemForm = ref<CaseChecklistItemPayload>({
  case: 0,
  source_template_item: null,
  category: '',
  name: '',
  item_type: 'document',
  quantity: null,
  unit: '',
  is_required: true,
  is_completed: false,
  completed_at: null,
  completed_by: null,
  note: '',
  responsible_party: '',
  acquisition_place: '',
  required_details: '',
  internal_note: '',
  customer_note: '',
  is_visible_to_customer: true,
  importance_level: 'normal',
  sort_order: 0,
})

const timelineRules: FormRules<TimelinePayload> = {
  title: [{ required: true, message: 'タイトルを入力してください。', trigger: 'blur' }],
}
const cancelRules: FormRules<typeof cancelForm.value> = {
  reason: [{ required: true, message: '中止理由を入力してください。', trigger: 'blur' }],
}
const checklistItemRules: FormRules<CaseChecklistItemPayload> = {
  name: [{ required: true, message: '項目名を入力してください。', trigger: 'blur' }],
  item_type: [{ required: true, message: '項目タイプを選択してください。', trigger: 'change' }],
}

const displayValue = (value?: string | null) => value || '-'
const getTodayDate = () => {
  const date = new Date()
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}

const getChecklistItemTypeLabel = (type: CaseChecklistItemType) => (
  checklistItemTypeOptions.find((option) => option.value === type)?.label || type
)

const getImportanceOption = (level: string) => (
  importanceLevelOptions.find((option) => option.value === level) || importanceLevelOptions[0]
)

const getImportanceLabel = (level: string) => getImportanceOption(level).label

const sortedTimelines = computed(() => (
  timelines.value
    .map((timeline, index) => ({ timeline, index }))
    .sort((left, right) => {
      const leftDate = left.timeline.occurred_at || left.timeline.created_at
      const rightDate = right.timeline.occurred_at || right.timeline.created_at
      if (leftDate && rightDate && leftDate !== rightDate) return rightDate.localeCompare(leftDate)
      if (leftDate && !rightDate) return -1
      if (!leftDate && rightDate) return 1
      return left.index - right.index
    })
    .map(({ timeline }) => timeline)
))

const sortedChecklistItems = computed(() => (
  [...checklistItems.value].sort((left, right) => {
    if ((left.sort_order || 0) !== (right.sort_order || 0)) {
      return (left.sort_order || 0) - (right.sort_order || 0)
    }
    return left.id - right.id
  })
))

const checklistGroups = computed(() => {
  const groups: Array<{ category: string, items: CaseChecklistItem[] }> = []
  sortedChecklistItems.value.forEach((item) => {
    const category = item.category || 'その他'
    let group = groups.find((row) => row.category === category)
    if (!group) {
      group = { category, items: [] }
      groups.push(group)
    }
    group.items.push(item)
  })
  return groups
})

const checklistProgressText = computed(() => {
  const total = checklistItems.value.length
  const completed = checklistItems.value.filter((item) => item.is_completed).length
  return `${completed} / ${total}`
})

const checklistProgressPercentage = computed(() => caseDetail.value?.required_items_progress_percent || 0)

const isAgencyHandledParty = (party: string) => (
  ['our_company', 'gyousei', 'tax_accountant'].includes(party)
)

const visibleNoticeItems = computed(() => (
  sortedChecklistItems.value.filter((item) => (
    item.is_visible_to_customer && (!customerNoticeOptions.value.onlyIncomplete || !item.is_completed)
  ))
))

const customerActionNoticeItems = computed(() => (
  visibleNoticeItems.value.filter((item) => !isAgencyHandledParty(item.responsible_party))
))

const agencyHandledNoticeItems = computed(() => (
  visibleNoticeItems.value.filter((item) => isAgencyHandledParty(item.responsible_party))
))

const fetchCaseDetail = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [caseData, timelineData, checklistData, templateData, presetData] = await Promise.all([
      getCase(caseId.value),
      listTimelines({ case: caseId.value }),
      listCaseChecklistItems({ case: caseId.value }),
      listCaseChecklistTemplates({ is_active: true }),
      listChecklistItemPresets({ is_active: true, ordering: 'sort_order' }),
    ])
    caseDetail.value = caseData
    timelines.value = timelineData.results
    checklistItems.value = checklistData.results
    checklistTemplates.value = templateData.results
    checklistItemPresets.value = presetData.results
  } catch {
    errorMessage.value = '案件詳細の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const fetchTimelines = async () => {
  const data = await listTimelines({ case: caseId.value })
  timelines.value = data.results
}

const fetchChecklistItems = async () => {
  const data = await listCaseChecklistItems({ case: caseId.value })
  checklistItems.value = data.results
  caseDetail.value = await getCase(caseId.value)
}

const resetTimelineForm = () => {
  editingTimelineId.value = null
  timelineForm.value = {
    case: caseId.value,
    occurred_at: getTodayDate(),
    title: '',
    content: '',
    is_visible_to_client: false,
  }
  timelineFormRef.value?.clearValidate()
}

const resetCancelForm = () => {
  cancelForm.value = {
    reason: '',
  }
  cancelFormRef.value?.clearValidate()
}

const resetChecklistItemForm = () => {
  const nextSortOrder = checklistItems.value.reduce((maxValue, item) => Math.max(maxValue, item.sort_order || 0), 0) + 10
  editingChecklistItemId.value = null
  checklistItemForm.value = {
    case: caseId.value,
    source_template_item: null,
    category: '',
    name: '',
    item_type: 'document',
    quantity: null,
    unit: '',
    is_required: true,
    is_completed: false,
    completed_at: null,
    completed_by: null,
    note: '',
    responsible_party: '',
    acquisition_place: '',
    required_details: '',
    internal_note: '',
    customer_note: '',
    is_visible_to_customer: true,
    importance_level: 'normal',
    sort_order: nextSortOrder,
  }
  checklistItemFormRef.value?.clearValidate()
}

const openCreateTimelineDialog = () => {
  resetTimelineForm()
  timelineDialogVisible.value = true
}

const openEditTimelineDialog = (timeline: Timeline) => {
  editingTimelineId.value = timeline.id
  timelineForm.value = {
    case: caseId.value,
    occurred_at: timeline.occurred_at,
    title: timeline.title,
    content: timeline.content,
    is_visible_to_client: timeline.is_visible_to_client,
  }
  timelineFormRef.value?.clearValidate()
  timelineDialogVisible.value = true
}

const openProgressUpdateDialog = (suggestedStatus?: string) => {
  if (!caseDetail.value) return
  progressUpdateWarnings.value = []
  progressUpdateNoteVisible.value = false
  const today = getTodayDate()
  progressUpdateForm.value = {
    new_status: suggestedStatus || caseDetail.value.status,
    change_date: today,
    note: '',
    force: false,
    applied_at: caseDetail.value.applied_at || today,
    application_receipt_number: caseDetail.value.application_receipt_number || '',
    additional_documents_requested_at: caseDetail.value.additional_documents_requested_at || today,
    additional_documents_detail: caseDetail.value.additional_documents_detail || '',
    additional_documents_due_at: caseDetail.value.additional_documents_due_at,
    additional_documents_submitted_at: caseDetail.value.additional_documents_submitted_at || today,
    result_notified_at: caseDetail.value.result_notified_at || today,
    result_received_at: caseDetail.value.result_received_at || today,
    permission_number: caseDetail.value.permission_number || '',
    result_note: caseDetail.value.result_note || '',
    withdrawn_at: caseDetail.value.withdrawn_at || today,
    completed_at: caseDetail.value.completed_at || today,
  }
  progressUpdateDialogVisible.value = true
}

const openCorrectionDialog = () => {
  if (!caseDetail.value) return
  correctionForm.value = {
    consulted_at: caseDetail.value.consulted_at,
    accepted_at: caseDetail.value.accepted_at,
    document_collection_started_at: caseDetail.value.document_collection_started_at,
    documents_completed_at: caseDetail.value.documents_completed_at,
    application_ready_at: caseDetail.value.application_ready_at,
    applied_at: caseDetail.value.applied_at,
    application_receipt_number: caseDetail.value.application_receipt_number || '',
    review_started_at: caseDetail.value.review_started_at,
    additional_documents_requested_at: caseDetail.value.additional_documents_requested_at,
    additional_documents_detail: caseDetail.value.additional_documents_detail || '',
    additional_documents_due_at: caseDetail.value.additional_documents_due_at,
    additional_documents_submitted_at: caseDetail.value.additional_documents_submitted_at,
    result_notified_at: caseDetail.value.result_notified_at,
    result_received_at: caseDetail.value.result_received_at,
    permission_number: caseDetail.value.permission_number || '',
    result_note: caseDetail.value.result_note || '',
    withdrawn_at: caseDetail.value.withdrawn_at,
    completed_at: caseDetail.value.completed_at,
  }
  correctionDialogVisible.value = true
}

const openRegistrationStatusDialog = () => {
  if (!caseDetail.value) return
  registrationStatusWarnings.value = []
  registrationStatusForm.value = {
    new_status: caseDetail.value.registration_status,
    change_date: getTodayDate(),
    note: '',
    force: false,
  }
  registrationStatusDialogVisible.value = true
}

const openCancelDialog = () => {
  if (!canCancelCase.value) return
  resetCancelForm()
  cancelDialogVisible.value = true
}

const confirmRegenerateCaseNumber = async () => {
  if (!caseDetail.value || regeneratingCaseNumber.value) return
  regeneratingCaseNumber.value = true
  try {
    const preview = await previewRegenerateCaseNumber(caseId.value)
    await ElMessageBox.confirm(
      `現在の案件番号：${preview.current_case_number}\n新しい案件番号：${preview.new_case_number}`,
      '案件番号を再生成',
      {
        confirmButtonText: '再生成',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    caseDetail.value = await regenerateCaseNumber(caseId.value)
    ElMessage.success('案件番号を再生成しました。')
    await fetchTimelines()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error?.response?.data?.detail || '案件番号の再生成に失敗しました。')
    }
  } finally {
    regeneratingCaseNumber.value = false
  }
}

const openCreateChecklistItemDialog = () => {
  resetChecklistItemForm()
  checklistItemDialogVisible.value = true
}

const queryChecklistItemNameSuggestions = async (
  query: string,
  callback: (suggestions: Array<{ value: string, presetId?: number }>) => void,
) => {
  try {
    const [presetsData, historySuggestions] = await Promise.all([
      listChecklistItemPresets({ search: query || undefined, is_active: true }),
      listCaseChecklistItemNameSuggestions({ q: query || undefined }),
    ])
    const presetOptions = presetsData.results.map((preset) => ({ value: preset.name, presetId: preset.id }))
    const presetNames = new Set(presetOptions.map((option) => option.value))
    const historyOptions = (historySuggestions as ItemNameSuggestion[])
      .filter((suggestion) => !presetNames.has(suggestion.value))
      .map((suggestion) => ({ value: suggestion.value }))
    callback([...presetOptions, ...historyOptions])
  } catch {
    callback([])
  }
}

const handleChecklistItemNameSelect = (option: { value: string, presetId?: number }) => {
  if (!option.presetId) return
  const preset = checklistItemPresets.value.find((item) => item.id === option.presetId)
  if (!preset) return
  checklistItemForm.value.name = preset.name
  if (preset.category) checklistItemForm.value.category = preset.category
  if (preset.acquisition_place) checklistItemForm.value.acquisition_place = preset.acquisition_place
  if (preset.responsible_party) checklistItemForm.value.responsible_party = preset.responsible_party
  if (preset.required_details) checklistItemForm.value.required_details = preset.required_details
}

const openEditChecklistItemDialog = (item: CaseChecklistItem) => {
  editingChecklistItemId.value = item.id
  checklistItemForm.value = {
    case: caseId.value,
    source_template_item: item.source_template_item,
    category: item.category,
    name: item.name,
    item_type: item.item_type,
    quantity: item.quantity,
    unit: item.unit,
    is_required: item.is_required,
    is_completed: item.is_completed,
    completed_at: item.completed_at,
    completed_by: item.completed_by,
    note: item.note,
    responsible_party: item.responsible_party || '',
    acquisition_place: item.acquisition_place || '',
    required_details: item.required_details || '',
    internal_note: item.internal_note || '',
    customer_note: item.customer_note || '',
    is_visible_to_customer: item.is_visible_to_customer,
    importance_level: item.importance_level || 'normal',
    sort_order: item.sort_order,
  }
  checklistItemFormRef.value?.clearValidate()
  checklistItemDialogVisible.value = true
}

const openApplyTemplateDialog = () => {
  selectedChecklistTemplateId.value = checklistTemplates.value[0]?.id || null
  applyTemplateDialogVisible.value = true
}

const submitProgressUpdate = async () => {
  if (!caseDetail.value) return
  if (progressUpdateForm.value.force && !progressUpdateForm.value.note.trim()) {
    ElMessage.warning('強制変更する場合は備考を入力してください。')
    return
  }
  progressUpdateSubmitting.value = true
  try {
    await changeCaseStatus(caseId.value, {
      new_status: progressUpdateForm.value.new_status,
      change_date: progressUpdateForm.value.change_date,
      note: progressUpdateForm.value.note,
      force: progressUpdateForm.value.force,
      status_payload: {
        applied_at: progressUpdateForm.value.applied_at,
        application_receipt_number: progressUpdateForm.value.application_receipt_number,
        additional_documents_requested_at: progressUpdateForm.value.additional_documents_requested_at,
        additional_documents_detail: progressUpdateForm.value.additional_documents_detail,
        additional_documents_submitted_at: progressUpdateForm.value.additional_documents_submitted_at,
        result_received_at: progressUpdateForm.value.result_received_at,
        permission_number: progressUpdateForm.value.permission_number,
        result_note: progressUpdateForm.value.result_note,
        withdrawn_at: progressUpdateForm.value.withdrawn_at,
        completed_at: progressUpdateForm.value.completed_at,
      },
    })
    const orphanUpdates: Partial<CasePayload> = {}
    if (progressUpdateForm.value.result_notified_at !== caseDetail.value.result_notified_at) {
      orphanUpdates.result_notified_at = progressUpdateForm.value.result_notified_at || null
    }
    if (progressUpdateForm.value.additional_documents_due_at !== caseDetail.value.additional_documents_due_at) {
      orphanUpdates.additional_documents_due_at = progressUpdateForm.value.additional_documents_due_at || null
    }
    if (Object.keys(orphanUpdates).length) {
      await updateCase(caseId.value, orphanUpdates)
    }
    ElMessage.success('進捗を更新しました。')
    progressUpdateDialogVisible.value = false
    await Promise.all([fetchCaseDetail(), fetchTimelines()])
  } catch (error: any) {
    const data = error?.response?.data
    if (data?.warnings?.length) {
      progressUpdateWarnings.value = data.warnings
      progressUpdateForm.value.force = true
      ElMessage.warning('確認が必要な警告があります。')
    } else {
      ElMessage.error(data?.detail || '進捗の更新に失敗しました。')
    }
  } finally {
    progressUpdateSubmitting.value = false
  }
}

const progressFieldLabels: Record<string, string> = {
  consulted_at: '相談日',
  accepted_at: '受任日',
  document_collection_started_at: '資料待ち開始日',
  documents_completed_at: '書類作成中（必要資料完了日）',
  application_ready_at: '申請準備完了日',
  applied_at: '入管局受理日',
  application_receipt_number: '受付番号',
  review_started_at: '審査開始日',
  additional_documents_requested_at: '補正資料通知日',
  additional_documents_detail: '補正資料内容',
  additional_documents_due_at: '補正資料截止日',
  additional_documents_submitted_at: '補正資料提出日',
  result_notified_at: '通知日（許可/不許可）',
  result_received_at: '許可日 / 不許可日',
  permission_number: '許可番号',
  result_note: '結果備考',
  withdrawn_at: '取下げ日',
  completed_at: '完了日',
}

const buildCorrectionPayload = () => {
  const payload: Partial<CasePayload> = {}
  const changedLines: string[] = []
  if (!caseDetail.value) return { payload, changedLines }
  const current = caseDetail.value
  const form = correctionForm.value

  const trackDate = (key: keyof CasePayload, oldValue: string | null, newValue: string | null) => {
    const normalizedNew = newValue || null
    const normalizedOld = oldValue || null
    if (normalizedNew !== normalizedOld) {
      ;(payload as Record<string, unknown>)[key] = normalizedNew
      changedLines.push(`${progressFieldLabels[key]}：${normalizedOld || '-'} → ${normalizedNew || '-'}`)
    }
  }
  const trackText = (key: keyof CasePayload, oldValue: string, newValue: string) => {
    const normalizedNew = newValue || ''
    const normalizedOld = oldValue || ''
    if (normalizedNew !== normalizedOld) {
      ;(payload as Record<string, unknown>)[key] = normalizedNew
      changedLines.push(`${progressFieldLabels[key]}：${normalizedOld || '-'} → ${normalizedNew || '-'}`)
    }
  }

  trackDate('consulted_at', current.consulted_at, form.consulted_at)
  trackDate('accepted_at', current.accepted_at, form.accepted_at)
  trackDate('document_collection_started_at', current.document_collection_started_at, form.document_collection_started_at)
  trackDate('documents_completed_at', current.documents_completed_at, form.documents_completed_at)
  trackDate('application_ready_at', current.application_ready_at, form.application_ready_at)
  trackDate('applied_at', current.applied_at, form.applied_at)
  trackText('application_receipt_number', current.application_receipt_number, form.application_receipt_number)
  trackDate('review_started_at', current.review_started_at, form.review_started_at)
  trackDate('additional_documents_requested_at', current.additional_documents_requested_at, form.additional_documents_requested_at)
  trackText('additional_documents_detail', current.additional_documents_detail, form.additional_documents_detail)
  trackDate('additional_documents_due_at', current.additional_documents_due_at, form.additional_documents_due_at)
  trackDate('additional_documents_submitted_at', current.additional_documents_submitted_at, form.additional_documents_submitted_at)
  trackDate('result_notified_at', current.result_notified_at, form.result_notified_at)
  trackDate('result_received_at', current.result_received_at, form.result_received_at)
  trackText('permission_number', current.permission_number, form.permission_number)
  trackText('result_note', current.result_note, form.result_note)
  trackDate('withdrawn_at', current.withdrawn_at, form.withdrawn_at)
  trackDate('completed_at', current.completed_at, form.completed_at)

  return { payload, changedLines }
}

const submitCorrection = async () => {
  if (!caseDetail.value) return
  const { payload, changedLines } = buildCorrectionPayload()
  if (!changedLines.length) {
    ElMessage.info('変更がありません。')
    return
  }
  correctionSubmitting.value = true
  try {
    await updateCase(caseId.value, payload)
    await createTimeline({
      case: caseId.value,
      occurred_at: getTodayDate(),
      title: '進捗情報を修正',
      content: changedLines.join('\n'),
      is_visible_to_client: false,
    })
    ElMessage.success('過去の項目を修正しました。')
    correctionDialogVisible.value = false
    await Promise.all([fetchCaseDetail(), fetchTimelines()])
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '修正に失敗しました。')
  } finally {
    correctionSubmitting.value = false
  }
}

const submitRegistrationStatusChange = async () => {
  if (!registrationStatusForm.value.new_status) {
    ElMessage.warning('新しい登録状態を選択してください。')
    return
  }
  if (registrationStatusForm.value.force && !registrationStatusForm.value.note.trim()) {
    ElMessage.warning('強制変更する場合は備考を入力してください。')
    return
  }
  registrationStatusChanging.value = true
  try {
    await changeCaseRegistrationStatus(caseId.value, {
      new_status: registrationStatusForm.value.new_status,
      change_date: registrationStatusForm.value.change_date,
      note: registrationStatusForm.value.note,
      force: registrationStatusForm.value.force,
    })
    ElMessage.success('登録状態を変更しました。')
    registrationStatusDialogVisible.value = false
    await Promise.all([fetchCaseDetail(), fetchTimelines()])
  } catch (error: any) {
    const data = error?.response?.data
    if (data?.warnings?.length) {
      registrationStatusWarnings.value = data.warnings
      registrationStatusForm.value.force = true
      ElMessage.warning('確認が必要な警告があります。')
    } else {
      ElMessage.error(data?.detail || '登録状態の変更に失敗しました。')
    }
  } finally {
    registrationStatusChanging.value = false
  }
}

const buildCustomerNoticeText = () => {
  const language = customerNoticeOptions.value.language
  const noticeType = customerNoticeOptions.value.noticeType
  const headerLines: string[] = []
  if (caseDetail.value?.customer_name) {
    headerLines.push(language === 'zh' ? `${caseDetail.value.customer_name} 您好：` : `${caseDetail.value.customer_name} 様`)
  }
  if (caseDetail.value?.case_type) {
    headerLines.push(language === 'zh' ? `案件类型：${caseDetail.value.case_type}` : `案件種別：${caseDetail.value.case_type}`)
  }
  if (caseDetail.value?.case_number) {
    headerLines.push(language === 'zh' ? `案件编号：${caseDetail.value.case_number}` : `案件番号：${caseDetail.value.case_number}`)
  }
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
  const body = customerActionNoticeItems.value.map((item, index) => {
    const lines = [`${index + 1}. ${item.name}`]
    if (item.acquisition_place) {
      lines.push(language === 'zh' ? `开具地点：${item.acquisition_place}` : `取得場所：${item.acquisition_place}`)
    }
    if (item.required_details) {
      lines.push(language === 'zh' ? `具体要求：${item.required_details}` : `必要内容：${item.required_details}`)
    }
    if (item.customer_note) {
      lines.push(language === 'zh' ? `注意事项：${item.customer_note}` : `注意事項：${item.customer_note}`)
    }
    return lines.join('\n')
  }).join('\n\n')
  const agencyItems = agencyHandledNoticeItems.value
  const agencySection = agencyItems.length
    ? [
        language === 'zh' ? '以下事项由我方（或税理士等）代为办理，您无需准备，仅供您了解进度：' : '以下の項目は弊社（または税理士等）が代行いたします。ご準備の必要はございませんが、進捗共有のためご案内します。',
        agencyItems.map((item, index) => {
          const partyLabel = responsiblePartyOptions.find((option) => option.value === item.responsible_party)?.label || ''
          const suffix = item.acquisition_place
            ? (language === 'zh' ? `（开具地点：${item.acquisition_place}／${partyLabel}）` : `（取得場所：${item.acquisition_place}／${partyLabel}）`)
            : (partyLabel ? `（${partyLabel}）` : '')
          return `${index + 1}. ${item.name}${suffix}`
        }).join('\n'),
      ].join('\n')
    : ''
  const closing = language === 'zh'
    ? '材料准备完成后，请拍照或扫描发送给我们确认。\n如有不清楚的地方，请随时联系我们。'
    : 'ご準備ができましたら、写真またはスキャンデータをお送りください。\nご不明な点がございましたら、いつでもご連絡ください。'
  return [headerLines.join('\n'), opening, body, agencySection, closing].filter(Boolean).join('\n\n')
}

const openCustomerNoticeDialog = () => {
  if (!visibleNoticeItems.value.length) {
    ElMessage.warning('顧客向けに表示できる案件事項がありません。')
    return
  }
  customerNoticeText.value = buildCustomerNoticeText()
  customerNoticeDialogVisible.value = true
}

const refreshCustomerNoticeText = () => {
  customerNoticeText.value = buildCustomerNoticeText()
}

const applyNoticeTypeDefaults = () => {
  customerNoticeOptions.value.onlyIncomplete = customerNoticeOptions.value.noticeType === 'reminder'
  refreshCustomerNoticeText()
}

const copyCustomerNoticeText = async () => {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(customerNoticeText.value)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = customerNoticeText.value
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

const submitChecklistItem = async () => {
  if (!checklistItemFormRef.value) return

  const valid = await checklistItemFormRef.value.validate().catch(() => false)
  if (!valid) return

  checklistItemSubmitting.value = true
  try {
    const payload: CaseChecklistItemPayload = {
      ...checklistItemForm.value,
      case: caseId.value,
      quantity: checklistItemForm.value.quantity || null,
      completed_at: checklistItemForm.value.is_completed ? (checklistItemForm.value.completed_at || new Date().toISOString()) : null,
      completed_by: checklistItemForm.value.is_completed ? (checklistItemForm.value.completed_by || null) : null,
    }
    if (editingChecklistItemId.value) {
      await updateCaseChecklistItem(editingChecklistItemId.value, payload)
      ElMessage.success('案件事項を更新しました。')
    } else {
      await createCaseChecklistItem(payload)
      ElMessage.success('案件事項を追加しました。')
    }
    checklistItemDialogVisible.value = false
    await Promise.all([fetchChecklistItems(), fetchCaseDetail()])
  } catch {
    ElMessage.error(editingChecklistItemId.value ? '案件事項の更新に失敗しました。' : '案件事項の追加に失敗しました。')
  } finally {
    checklistItemSubmitting.value = false
  }
}

const toggleChecklistItemCompleted = async (item: CaseChecklistItem) => {
  try {
    const isCompleted = !item.is_completed
    await updateCaseChecklistItem(item.id, {
      is_completed: isCompleted,
      completed_at: isCompleted ? new Date().toISOString() : null,
      completed_by: isCompleted ? (caseDetail.value?.responsible_employee || null) : null,
    })
    ElMessage.success(isCompleted ? '案件事項を完了しました。' : '案件事項を未完了に戻しました。')
    await Promise.all([fetchChecklistItems(), fetchCaseDetail()])
  } catch {
    ElMessage.error('案件事項の更新に失敗しました。')
  }
}

const confirmDeleteChecklistItem = async (item: CaseChecklistItem) => {
  try {
    await ElMessageBox.confirm(
      'この案件項目を削除しますか？\n削除後は元に戻せません。',
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteCaseChecklistItem(item.id)
    ElMessage.success('削除しました。')
    await Promise.all([fetchChecklistItems(), fetchCaseDetail()])
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('案件事項の削除に失敗しました。')
    }
  }
}

const moveChecklistItem = async (item: CaseChecklistItem, direction: -1 | 1) => {
  const currentIndex = sortedChecklistItems.value.findIndex((row) => row.id === item.id)
  const target = sortedChecklistItems.value[currentIndex + direction]
  if (!target) return

  try {
    await Promise.all([
      updateCaseChecklistItem(item.id, { sort_order: target.sort_order }),
      updateCaseChecklistItem(target.id, { sort_order: item.sort_order }),
    ])
    await fetchChecklistItems()
  } catch {
    ElMessage.error('並び順の更新に失敗しました。')
  }
}

const handleChecklistItemActionCommand = (item: CaseChecklistItem, command: string) => {
  if (command === 'edit') {
    openEditChecklistItemDialog(item)
    return
  }
  if (command === 'move-up') {
    moveChecklistItem(item, -1)
    return
  }
  if (command === 'move-down') {
    moveChecklistItem(item, 1)
    return
  }
  if (command === 'delete') {
    confirmDeleteChecklistItem(item)
  }
}

const submitApplyTemplate = async () => {
  if (!selectedChecklistTemplateId.value) {
    ElMessage.warning('テンプレートを選択してください。')
    return
  }

  applyingChecklistTemplate.value = true
  try {
    await applyCaseChecklistTemplate(caseId.value, selectedChecklistTemplateId.value)
    ElMessage.success('テンプレート項目を追加しました。')
    applyTemplateDialogVisible.value = false
    await fetchChecklistItems()
  } catch {
    ElMessage.error('テンプレート項目の追加に失敗しました。')
  } finally {
    applyingChecklistTemplate.value = false
  }
}

const submitTimeline = async () => {
  if (!timelineFormRef.value) return

  const valid = await timelineFormRef.value.validate().catch(() => false)
  if (!valid) return

  timelineSubmitting.value = true
  try {
    if (editingTimelineId.value) {
      await updateTimeline(editingTimelineId.value, {
        occurred_at: timelineForm.value.occurred_at || null,
        title: timelineForm.value.title,
        content: timelineForm.value.content,
        is_visible_to_client: timelineForm.value.is_visible_to_client,
      })
      ElMessage.success('進捗記録を更新しました')
    } else {
      await createTimeline({
        ...timelineForm.value,
        case: caseId.value,
      })
      ElMessage.success('記録を追加しました。')
    }
    timelineDialogVisible.value = false
    await fetchTimelines()
  } catch {
    ElMessage.error(editingTimelineId.value ? '進捗記録の更新に失敗しました。' : '記録の追加に失敗しました。')
  } finally {
    timelineSubmitting.value = false
  }
}

const submitCancelCase = async () => {
  if (!cancelFormRef.value || !canCancelCase.value) return

  const valid = await cancelFormRef.value.validate().catch(() => false)
  if (!valid) return

  cancelSubmitting.value = true
  try {
    await cancelCase(caseId.value, cancelForm.value.reason)
    ElMessage.success('案件を中止しました')
    cancelDialogVisible.value = false
    caseDetail.value = await getCase(caseId.value)
    await fetchTimelines()
  } catch {
    ElMessage.error('案件の中止に失敗しました。')
  } finally {
    cancelSubmitting.value = false
  }
}

const fetchBasicInfoOptions = async () => {
  const [customerData, companyData, employeeData, caseTypeData, applicationCategoryData] = await Promise.all([
    listCustomers(),
    listCompanies(),
    listEmployees({ is_active: true }),
    listCaseTypeMasters({ is_active: true, ordering: 'sort_order' }),
    listCaseApplicationCategories({ is_active: true, ordering: 'sort_order' }),
  ])
  customers.value = customerData.results
  companies.value = companyData.results
  employees.value = employeeData.results
  caseTypes.value = caseTypeData.results
  applicationCategories.value = applicationCategoryData.results
}

const openBasicInfoDialog = () => {
  if (!caseDetail.value) return
  basicInfoForm.value = {
    case_type_master: caseDetail.value.case_type_master,
    application_category: caseDetail.value.application_category,
    customer: caseDetail.value.customer,
    company: caseDetail.value.company,
    responsible_employee: caseDetail.value.responsible_employee,
  }
  basicInfoDialogVisible.value = true
}

const basicInfoFieldLabels: Record<string, string> = {
  case_type_master: '案件種別',
  application_category: '申請区分',
  customer: '顧客',
  company: '会社',
  responsible_employee: '担当者',
}

const submitBasicInfo = async () => {
  if (!caseDetail.value) return
  const current = caseDetail.value
  const form = basicInfoForm.value
  const payload: Partial<CasePayload> = {}
  const changedLines: string[] = []

  const trackRef = (
    key: 'case_type_master' | 'application_category' | 'customer' | 'company' | 'responsible_employee',
    oldValue: number | null,
    newValue: number | null,
    options: { id: number, name: string }[],
  ) => {
    if ((newValue || null) === (oldValue || null)) return
    payload[key] = newValue
    const oldLabel = options.find((option) => option.id === oldValue)?.name || '-'
    const newLabel = options.find((option) => option.id === newValue)?.name || '-'
    changedLines.push(`${basicInfoFieldLabels[key]}：${oldLabel} → ${newLabel}`)
  }

  trackRef('case_type_master', current.case_type_master, form.case_type_master, caseTypes.value)
  trackRef('application_category', current.application_category, form.application_category, applicationCategories.value)
  trackRef('customer', current.customer, form.customer, customers.value)
  trackRef('company', current.company, form.company, companies.value)
  trackRef('responsible_employee', current.responsible_employee, form.responsible_employee, employees.value)

  if (!changedLines.length) {
    ElMessage.info('変更がありません。')
    return
  }

  basicInfoSubmitting.value = true
  try {
    await updateCase(caseId.value, payload)
    await createTimeline({
      case: caseId.value,
      occurred_at: getTodayDate(),
      title: '案件基本情報を修正',
      content: changedLines.join('\n'),
      is_visible_to_client: false,
    })
    ElMessage.success('案件基本情報を更新しました。')
    basicInfoDialogVisible.value = false
    await Promise.all([fetchCaseDetail(), fetchTimelines()])
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '更新に失敗しました。')
  } finally {
    basicInfoSubmitting.value = false
  }
}

onMounted(() => {
  fetchCaseDetail()
  fetchBasicInfoOptions()
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>案件詳細</h1>
      <el-button @click="router.back()">戻る</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <div v-loading="loading" class="detail-grid">
      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>案件基本情報</span>
            <div class="card-header-actions">
              <el-button @click="openBasicInfoDialog">編集</el-button>
              <el-button :loading="regeneratingCaseNumber" @click="confirmRegenerateCaseNumber">
                案件番号を再生成
              </el-button>
              <el-button v-if="canCancelCase" type="danger" @click="openCancelDialog">
                案件を中止する
              </el-button>
            </div>
          </div>
        </template>
        <el-descriptions v-if="caseDetail" :column="2" border>
          <el-descriptions-item label="案件番号">{{ displayValue(caseDetail.case_number) }}</el-descriptions-item>
          <el-descriptions-item label="案件種別">{{ displayValue(caseDetail.case_type_master_name) }}</el-descriptions-item>
          <el-descriptions-item label="申請区分">{{ displayValue(caseDetail.application_category_name) }}</el-descriptions-item>
          <el-descriptions-item label="登録ステータス">
            <el-tag :type="getCaseRegistrationStatusTagType(caseDetail.registration_status)" effect="plain">
              {{ getCaseRegistrationStatusLabel(caseDetail.registration_status) }}
            </el-tag>
            <el-button text type="primary" @click="openRegistrationStatusDialog">登録状態変更</el-button>
          </el-descriptions-item>
          <el-descriptions-item label="顧客名">{{ displayValue(caseDetail.customer_name) }}</el-descriptions-item>
          <el-descriptions-item label="会社名">{{ displayValue(caseDetail.company_name) }}</el-descriptions-item>
          <el-descriptions-item label="担当者">
            {{ displayValue(caseDetail.responsible_employee_name) }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>現在の進捗</span>
            <div class="header-actions">
              <el-button type="primary" @click="openProgressUpdateDialog()">進捗を更新</el-button>
            </div>
          </div>
        </template>
        <el-descriptions v-if="caseDetail" :column="2" border>
          <el-descriptions-item label="現在の進捗">
            <el-tag :type="getCaseDisplayStatusTagType(caseDetail.status)">
              {{ displayStatus }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="最新進捗日">{{ formatDate(caseDetail.progress_started_at) }}</el-descriptions-item>
        </el-descriptions>
        <el-collapse v-if="caseDetail" v-model="progressHistoryCollapse" class="progress-history-collapse">
          <el-collapse-item title="進捗履歴" name="history">
            <el-descriptions :column="2" border>
              <el-descriptions-item v-if="caseDetail.consulted_at" label="相談日">{{ formatDate(caseDetail.consulted_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.accepted_at" label="受任日">{{ formatDate(caseDetail.accepted_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.document_collection_started_at" label="資料待ち開始日">{{ formatDate(caseDetail.document_collection_started_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.documents_completed_at" label="書類作成中（必要資料完了日）">{{ formatDate(caseDetail.documents_completed_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.application_ready_at" label="申請準備完了日">{{ formatDate(caseDetail.application_ready_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.applied_at" label="入管局受理日">{{ formatDate(caseDetail.applied_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.application_receipt_number" label="受付番号">{{ caseDetail.application_receipt_number }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.review_started_at" label="審査開始日">{{ formatDate(caseDetail.review_started_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.additional_documents_requested_at" label="補正資料通知日">{{ formatDate(caseDetail.additional_documents_requested_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.additional_documents_detail" label="補正資料内容" :span="2">{{ caseDetail.additional_documents_detail }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.additional_documents_due_at" label="補正資料截止日">{{ formatDate(caseDetail.additional_documents_due_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.additional_documents_submitted_at" label="補正資料提出日">{{ formatDate(caseDetail.additional_documents_submitted_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.result_notified_at" label="通知日（許可/不許可）">{{ formatDate(caseDetail.result_notified_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.result_received_at" :label="caseDetail.status === 'rejected' ? '不許可日' : '許可日'">{{ formatDate(caseDetail.result_received_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.permission_number" label="許可番号">{{ caseDetail.permission_number }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.result_note" label="結果備考" :span="2">{{ caseDetail.result_note }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.withdrawn_at" label="取下げ日">{{ formatDate(caseDetail.withdrawn_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.completed_at" label="完了日">{{ formatDate(caseDetail.completed_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.review_duration_days !== null" label="審査期間">{{ caseDetail.review_duration_days }}日</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.days_until_additional_request !== null" label="追加資料依頼まで">{{ caseDetail.days_until_additional_request }}日</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.additional_documents_duration_days !== null" label="追加資料対応期間">{{ caseDetail.additional_documents_duration_days }}日</el-descriptions-item>
              <el-descriptions-item v-if="caseDetail.total_processing_days !== null" label="案件処理期間">{{ caseDetail.total_processing_days }}日</el-descriptions-item>
            </el-descriptions>
            <div class="progress-correction-link">
              <el-button text size="small" @click="openCorrectionDialog">過去の項目を修正</el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>案件進捗・必要資料</span>
            <div class="header-actions">
              <el-button plain @click="openCustomerNoticeDialog">顧客通知文案</el-button>
              <el-button plain @click="openApplyTemplateDialog">テンプレートから追加</el-button>
              <el-button type="primary" @click="openCreateChecklistItemDialog">項目追加</el-button>
            </div>
          </div>
        </template>
        <div class="checklist-summary">
          <span>案件事項：{{ checklistProgressText }}</span>
          <span>完了率：{{ checklistProgressPercentage }}%</span>
          <span>必須事項：{{ caseDetail?.required_items_completed || 0 }} / {{ caseDetail?.required_items_total || 0 }} 完了</span>
        </div>
        <el-progress
          v-if="caseDetail?.required_items_total"
          :percentage="caseDetail.required_items_progress_percent"
          class="checklist-required-progress"
        />
        <el-alert
          v-if="caseDetail?.suggested_case_status && caseDetail?.suggestion_message"
          :title="caseDetail.suggestion_message"
          type="success"
          show-icon
          class="checklist-suggestion-alert"
        >
          <template #default>
            <el-button size="small" type="primary" @click="openProgressUpdateDialog(caseDetail?.suggested_case_status)">
              状態を変更
            </el-button>
          </template>
        </el-alert>
        <el-empty v-if="!checklistItems.length" description="案件事項がありません" />
        <div v-else class="checklist-groups">
          <section v-for="group in checklistGroups" :key="group.category" class="checklist-group">
            <h3>{{ group.category }}</h3>
            <div
              v-for="item in group.items"
              :key="item.id"
              class="checklist-item"
              :class="[`importance-${item.importance_level || 'normal'}`, { 'is-completed': item.is_completed }]"
            >
              <el-checkbox
                :model-value="item.is_completed"
                @change="toggleChecklistItemCompleted(item)"
              />
              <div class="checklist-item-main">
                <div class="checklist-item-title">
                  <span>{{ item.name }}</span>
                  <span v-if="item.quantity" class="checklist-quantity">
                    {{ item.quantity }}{{ item.unit }}
                  </span>
                  <el-tag v-if="item.is_required" size="small" type="danger">必須</el-tag>
                  <el-tag size="small" type="info">{{ getChecklistItemTypeLabel(item.item_type) }}</el-tag>
                  <el-tag size="small" :type="getImportanceOption(item.importance_level).type">
                    {{ getImportanceLabel(item.importance_level) }}
                  </el-tag>
                  <el-tag v-if="item.is_completed" size="small" type="success">完了</el-tag>
                  <span v-else class="muted-text">未完了</span>
                </div>
                <div class="checklist-detail-grid">
                  <span v-if="item.acquisition_place">手続先：{{ item.acquisition_place }}</span>
                  <span v-if="item.responsible_party">
                    準備者：{{ responsiblePartyOptions.find((option) => option.value === item.responsible_party)?.label || item.responsible_party }}
                  </span>
                </div>
                <div v-if="item.required_details" class="checklist-note-box normal">
                  <strong>必要内容</strong>
                  <p>{{ item.required_details }}</p>
                </div>
                <div v-if="item.customer_note" class="checklist-note-box" :class="item.importance_level === 'warning' ? 'warning' : 'important'">
                  <strong>{{ item.importance_level === 'warning' ? '要注意' : '顧客向け注意事項' }}</strong>
                  <p>{{ item.customer_note }}</p>
                </div>
                <div v-if="item.internal_note" class="checklist-note-box internal">
                  <strong>内部備考</strong>
                  <p>{{ item.internal_note }}</p>
                </div>
                <div class="checklist-item-meta">
                  <span v-if="item.completed_at">完了日時：{{ formatDateTime(item.completed_at) }}</span>
                  <span v-if="item.completed_by_name">完了者：{{ item.completed_by_name }}</span>
                  <span v-if="item.note">備考：{{ item.note }}</span>
                </div>
              </div>
              <div class="checklist-item-actions">
                <el-dropdown trigger="click" @command="handleChecklistItemActionCommand(item, $event)">
                  <el-button text type="primary" class="table-action-trigger">
                    操作
                    <el-icon><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">編集</el-dropdown-item>
                      <el-dropdown-item command="move-up">上へ</el-dropdown-item>
                      <el-dropdown-item command="move-down">下へ</el-dropdown-item>
                      <el-dropdown-item command="delete" divided class="danger-item">削除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </section>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>進捗記録</span>
            <el-button type="primary" @click="openCreateTimelineDialog">記録追加</el-button>
          </div>
        </template>
        <el-table :data="sortedTimelines" stripe>
          <el-table-column label="発生日" width="130">
            <template #default="{ row }">{{ formatDate(row.occurred_at) }}</template>
          </el-table-column>
          <el-table-column prop="title" label="タイトル" min-width="180" />
          <el-table-column prop="content" label="内容" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">{{ displayValue(row.content) }}</template>
          </el-table-column>
          <el-table-column label="作成日時" min-width="160">
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" @click="openEditTimelineDialog(row)">編集</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="!timelines.length" class="empty-text">該当データなし</p>
      </el-card>
    </div>

    <el-dialog v-model="progressUpdateDialogVisible" title="進捗を更新" width="480px">
      <el-form :model="progressUpdateForm" label-position="top">
        <el-form-item label="現在の進捗">
          <el-input :model-value="getCaseDisplayStatus(caseDetail?.status)" disabled />
        </el-form-item>
        <el-form-item label="新しい進捗">
          <el-select v-model="progressUpdateForm.new_status" class="form-control">
            <el-option
              v-for="option in caseStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="progressUpdateForm.new_status !== caseDetail?.status" label="変更日">
          <el-date-picker
            v-model="progressUpdateForm.change_date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            class="form-control"
          />
        </el-form-item>
        <template v-if="progressUpdateForm.new_status === 'applied'">
          <el-form-item label="入管局受理日">
            <el-date-picker v-model="progressUpdateForm.applied_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="受付番号">
            <el-input v-model="progressUpdateForm.application_receipt_number" />
          </el-form-item>
        </template>
        <template v-if="progressUpdateForm.new_status === 'additional_documents'">
          <el-form-item label="補正資料通知日">
            <el-date-picker v-model="progressUpdateForm.additional_documents_requested_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="補正資料内容">
            <el-input v-model="progressUpdateForm.additional_documents_detail" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="補正資料截止日">
            <el-date-picker v-model="progressUpdateForm.additional_documents_due_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
        </template>
        <el-form-item v-if="progressUpdateForm.new_status === 'additional_documents_submitted'" label="補正資料提出日">
          <el-date-picker v-model="progressUpdateForm.additional_documents_submitted_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
        </el-form-item>
        <template v-if="progressUpdateForm.new_status === 'approved' || progressUpdateForm.new_status === 'rejected'">
          <el-form-item label="通知日">
            <el-date-picker v-model="progressUpdateForm.result_notified_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item :label="progressUpdateForm.new_status === 'approved' ? '許可日' : '不許可日'">
            <el-date-picker v-model="progressUpdateForm.result_received_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item v-if="progressUpdateForm.new_status === 'approved'" label="許可番号">
            <el-input v-model="progressUpdateForm.permission_number" />
          </el-form-item>
          <el-form-item label="結果備考">
            <el-input v-model="progressUpdateForm.result_note" type="textarea" :rows="2" />
          </el-form-item>
        </template>
        <el-form-item v-if="progressUpdateForm.new_status === 'withdrawn'" label="取下げ日">
          <el-date-picker v-model="progressUpdateForm.withdrawn_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
        </el-form-item>
        <el-form-item v-if="progressUpdateForm.new_status === 'completed'" label="完了日">
          <el-date-picker v-model="progressUpdateForm.completed_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
        </el-form-item>
        <el-alert
          v-if="progressUpdateWarnings.length"
          type="warning"
          show-icon
          :closable="false"
          class="status-warning-alert"
        >
          <template #title>確認が必要です</template>
          <ul class="status-warning-list">
            <li v-for="warning in progressUpdateWarnings" :key="warning.code">{{ warning.message }}</li>
          </ul>
        </el-alert>
        <el-button
          v-if="!progressUpdateNoteVisible"
          text
          size="small"
          class="note-toggle-button"
          @click="progressUpdateNoteVisible = true"
        >
          備考を追加
        </el-button>
        <el-form-item v-else label="備考">
          <el-input v-model="progressUpdateForm.note" type="textarea" :rows="2" />
        </el-form-item>
        <el-checkbox v-if="progressUpdateWarnings.length" v-model="progressUpdateForm.force">警告を確認して強制変更する</el-checkbox>
      </el-form>
      <template #footer>
        <el-button @click="progressUpdateDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="progressUpdateSubmitting" @click="submitProgressUpdate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="correctionDialogVisible" title="過去の項目を修正" width="640px">
      <p class="dialog-note">
        進捗状態は変更されません。日付や番号の記入ミスを直接修正する場合に使用してください。変更内容は進捗記録に自動で残ります。
      </p>
      <el-form :model="correctionForm" label-position="top">
        <h3 class="form-section-title">相談〜書類準備</h3>
        <div class="form-grid">
          <el-form-item label="相談日">
            <el-date-picker v-model="correctionForm.consulted_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="受任日">
            <el-date-picker v-model="correctionForm.accepted_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="資料待ち開始日">
            <el-date-picker v-model="correctionForm.document_collection_started_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="書類作成中（必要資料完了日）">
            <el-date-picker v-model="correctionForm.documents_completed_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="申請準備完了日">
            <el-date-picker v-model="correctionForm.application_ready_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
        </div>
        <h3 class="form-section-title">申請〜審査</h3>
        <div class="form-grid">
          <el-form-item label="入管局受理日">
            <el-date-picker v-model="correctionForm.applied_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="受付番号">
            <el-input v-model="correctionForm.application_receipt_number" />
          </el-form-item>
          <el-form-item label="審査開始日">
            <el-date-picker v-model="correctionForm.review_started_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
        </div>
        <h3 class="form-section-title">補正資料</h3>
        <div class="form-grid">
          <el-form-item label="補正資料通知日">
            <el-date-picker v-model="correctionForm.additional_documents_requested_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="補正資料截止日">
            <el-date-picker v-model="correctionForm.additional_documents_due_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="補正資料提出日">
            <el-date-picker v-model="correctionForm.additional_documents_submitted_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
        </div>
        <el-form-item label="補正資料内容">
          <el-input v-model="correctionForm.additional_documents_detail" type="textarea" :rows="2" />
        </el-form-item>
        <h3 class="form-section-title">結果〜完了</h3>
        <div class="form-grid">
          <el-form-item label="通知日（許可/不許可）">
            <el-date-picker v-model="correctionForm.result_notified_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="許可日 / 不許可日">
            <el-date-picker v-model="correctionForm.result_received_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="許可番号">
            <el-input v-model="correctionForm.permission_number" />
          </el-form-item>
          <el-form-item label="取下げ日">
            <el-date-picker v-model="correctionForm.withdrawn_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
          <el-form-item label="完了日">
            <el-date-picker v-model="correctionForm.completed_at" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" />
          </el-form-item>
        </div>
        <el-form-item label="結果備考">
          <el-input v-model="correctionForm.result_note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="correctionDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="correctionSubmitting" @click="submitCorrection">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="basicInfoDialogVisible" title="案件基本情報を編集" width="520px">
      <el-form :model="basicInfoForm" label-position="top">
        <el-form-item label="案件種別">
          <el-select v-model="basicInfoForm.case_type_master" filterable placeholder="選択してください" class="form-control">
            <el-option v-for="caseType in caseTypes" :key="caseType.id" :label="caseType.name" :value="caseType.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="申請区分">
          <el-select v-model="basicInfoForm.application_category" filterable placeholder="選択してください" class="form-control">
            <el-option v-for="category in applicationCategories" :key="category.id" :label="category.name" :value="category.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="顧客">
          <el-select v-model="basicInfoForm.customer" filterable placeholder="選択してください" class="form-control">
            <el-option v-for="customer in customers" :key="customer.id" :label="customer.name" :value="customer.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="会社">
          <el-select v-model="basicInfoForm.company" clearable filterable placeholder="選択してください" class="form-control">
            <el-option v-for="company in companies" :key="company.id" :label="company.name" :value="company.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="担当者">
          <el-select v-model="basicInfoForm.responsible_employee" clearable filterable placeholder="選択してください" class="form-control">
            <el-option label="未設定" :value="null" />
            <el-option v-for="employee in employees" :key="employee.id" :label="employee.name" :value="employee.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="basicInfoDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="basicInfoSubmitting" @click="submitBasicInfo">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="registrationStatusDialogVisible" title="登録状態変更" width="560px">
      <el-form :model="registrationStatusForm" label-position="top">
        <el-form-item label="現在の登録状態">
          <el-input :model-value="getCaseRegistrationStatusLabel(caseDetail?.registration_status)" disabled />
        </el-form-item>
        <el-form-item label="新しい登録状態">
          <el-select v-model="registrationStatusForm.new_status" class="form-control">
            <el-option
              v-for="option in caseRegistrationStatusOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="変更日">
          <el-date-picker
            v-model="registrationStatusForm.change_date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            class="form-control"
          />
        </el-form-item>
        <el-alert
          v-if="registrationStatusWarnings.length"
          type="warning"
          show-icon
          :closable="false"
          class="status-warning-alert"
        >
          <template #title>確認が必要です</template>
          <ul class="status-warning-list">
            <li v-for="warning in registrationStatusWarnings" :key="warning.code">{{ warning.message }}</li>
          </ul>
        </el-alert>
        <el-form-item label="備考">
          <el-input v-model="registrationStatusForm.note" type="textarea" :rows="3" />
        </el-form-item>
        <el-checkbox v-if="registrationStatusWarnings.length" v-model="registrationStatusForm.force">
          警告を確認して強制変更する
        </el-checkbox>
      </el-form>
      <template #footer>
        <el-button @click="registrationStatusDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="registrationStatusChanging" @click="submitRegistrationStatusChange">変更</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="checklistItemDialogVisible"
      :title="editingChecklistItemId ? '案件事項編集' : '案件事項追加'"
      width="680px"
      @closed="resetChecklistItemForm"
    >
      <el-form
        ref="checklistItemFormRef"
        :model="checklistItemForm"
        :rules="checklistItemRules"
        label-position="top"
      >
        <h3 class="form-section-title">基本情報</h3>
        <div class="form-grid">
          <el-form-item label="分類" prop="category">
            <el-input v-model="checklistItemForm.category" placeholder="本人資料、会社資料など" />
          </el-form-item>
          <el-form-item label="項目タイプ" prop="item_type">
            <el-select v-model="checklistItemForm.item_type" class="form-control">
              <el-option
                v-for="option in checklistItemTypeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="項目名" prop="name">
          <el-autocomplete
            v-model="checklistItemForm.name"
            :fetch-suggestions="queryChecklistItemNameSuggestions"
            clearable
            placeholder="事項名を入力"
            value-key="value"
            class="form-control"
            @select="handleChecklistItemNameSelect"
          />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="数量" prop="quantity">
            <el-input-number v-model="checklistItemForm.quantity" :min="1" class="form-control" />
          </el-form-item>
          <el-form-item label="単位" prop="unit">
            <el-input v-model="checklistItemForm.unit" placeholder="通、份、部など" />
          </el-form-item>
          <el-form-item label="表示順" prop="sort_order">
            <el-input-number v-model="checklistItemForm.sort_order" :min="0" :step="10" class="form-control" />
          </el-form-item>
        </div>
        <h3 class="form-section-title">办理情報</h3>
        <div class="form-grid">
          <el-form-item label="準備者／担当区分" prop="responsible_party">
            <el-select v-model="checklistItemForm.responsible_party" class="form-control">
              <el-option
                v-for="option in responsiblePartyOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="手続先・取得場所" prop="acquisition_place">
            <el-input v-model="checklistItemForm.acquisition_place" placeholder="大阪南税務署、本人準備など" />
          </el-form-item>
        </div>
        <el-form-item label="必要内容" prop="required_details">
          <el-input v-model="checklistItemForm.required_details" type="textarea" :rows="3" />
        </el-form-item>
        <h3 class="form-section-title">顧客通知</h3>
        <el-form-item label="顧客向け注意事項" prop="customer_note">
          <el-input v-model="checklistItemForm.customer_note" type="textarea" :rows="3" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="必須" prop="is_required">
            <el-switch v-model="checklistItemForm.is_required" active-text="必須" inactive-text="任意" />
          </el-form-item>
          <el-form-item label="完了" prop="is_completed">
            <el-switch v-model="checklistItemForm.is_completed" active-text="完了" inactive-text="未完了" />
          </el-form-item>
          <el-form-item label="顧客表示" prop="is_visible_to_customer">
            <el-switch v-model="checklistItemForm.is_visible_to_customer" active-text="表示" inactive-text="非表示" />
          </el-form-item>
          <el-form-item label="重要レベル" prop="importance_level">
            <el-select v-model="checklistItemForm.importance_level" class="form-control">
              <el-option
                v-for="option in importanceLevelOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
        </div>
        <h3 class="form-section-title">内部管理</h3>
        <el-form-item label="普通備考" prop="note">
          <el-input v-model="checklistItemForm.note" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="内部備考" prop="internal_note">
          <el-input v-model="checklistItemForm.internal_note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="checklistItemDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="checklistItemSubmitting" @click="submitChecklistItem">
          {{ editingChecklistItemId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="customerNoticeDialogVisible" title="顧客通知文案" width="780px" class="material-notice-dialog">
      <div class="notice-option-grid">
        <el-form-item label="文案タイプ">
          <el-select v-model="customerNoticeOptions.noticeType" class="form-control" @change="applyNoticeTypeDefaults">
            <el-option label="初回材料案内" value="initial" />
            <el-option label="追加資料案内" value="additional" />
            <el-option label="未完了資料リマインド" value="reminder" />
          </el-select>
        </el-form-item>
        <el-form-item label="言語">
          <el-select v-model="customerNoticeOptions.language" class="form-control" @change="refreshCustomerNoticeText">
            <el-option label="中文" value="zh" />
            <el-option label="日本語" value="ja" />
          </el-select>
        </el-form-item>
      </div>
      <div class="notice-switches">
        <el-checkbox v-model="customerNoticeOptions.onlyIncomplete" @change="refreshCustomerNoticeText">未完了のみ</el-checkbox>
      </div>
      <el-input v-model="customerNoticeText" type="textarea" :rows="18" />
      <template #footer>
        <el-button @click="customerNoticeDialogVisible = false">閉じる</el-button>
        <el-button @click="refreshCustomerNoticeText">自動生成に戻す</el-button>
        <el-button type="primary" @click="copyCustomerNoticeText">コピー</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="applyTemplateDialogVisible" title="テンプレートから追加" width="520px">
      <p class="dialog-note">
        このテンプレートの有効項目を案件に追加します。既存項目は削除されません。
      </p>
      <el-select
        v-model="selectedChecklistTemplateId"
        filterable
        placeholder="テンプレートを選択してください"
        class="form-control"
      >
        <el-option
          v-for="template in checklistTemplates"
          :key="template.id"
          :label="template.name"
          :value="template.id"
        />
      </el-select>
      <template #footer>
        <el-button @click="applyTemplateDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="applyingChecklistTemplate" @click="submitApplyTemplate">
          追加
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="timelineDialogVisible"
      :title="editingTimelineId ? '進捗記録編集' : '記録追加'"
      width="560px"
      @closed="resetTimelineForm"
    >
      <el-form ref="timelineFormRef" :model="timelineForm" :rules="timelineRules" label-position="top">
        <el-form-item label="発生日" prop="occurred_at">
          <el-date-picker
            v-model="timelineForm.occurred_at"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="YYYY-MM-DD"
            class="form-control"
          />
        </el-form-item>
        <el-form-item label="タイトル" prop="title">
          <el-select
            v-model="timelineForm.title"
            allow-create
            clearable
            filterable
            placeholder="選択または入力してください"
            class="form-control"
          >
            <el-option
              v-for="title in timelineTitleOptions"
              :key="title"
              :label="title"
              :value="title"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="timelineForm.content" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="timelineDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="timelineSubmitting" @click="submitTimeline">
          {{ editingTimelineId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="cancelDialogVisible"
      title="案件を中止する"
      width="520px"
      @closed="resetCancelForm"
    >
      <el-form ref="cancelFormRef" :model="cancelForm" :rules="cancelRules" label-position="top">
        <el-form-item label="中止理由" prop="reason">
          <el-input v-model="cancelForm.reason" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="cancelDialogVisible = false">キャンセル</el-button>
        <el-button type="danger" :loading="cancelSubmitting" @click="submitCancelCase">確認</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.header-actions {
  display: flex;
  gap: 8px;
}

.progress-correction-link {
  margin-top: 8px;
  text-align: right;
}

.note-toggle-button {
  margin-bottom: 8px;
}

.progress-history-collapse {
  margin-top: 12px;
}

.checklist-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.checklist-required-progress {
  margin-bottom: 12px;
}

.checklist-suggestion-alert {
  margin-bottom: 12px;
}

.status-warning-alert {
  margin-bottom: 12px;
}

.status-warning-list {
  padding-left: 18px;
  margin: 6px 0 0;
}

.checklist-groups {
  display: grid;
  gap: 16px;
}

.checklist-group h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.checklist-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: flex-start;
  padding: 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  border-left: 4px solid transparent;
  border-radius: 8px;
  background: #f8fbfd;
}

.checklist-item.importance-important {
  border-left-color: #e6a23c;
  background: #fff8e8;
}

.checklist-item.importance-warning {
  border-left-color: #f56c6c;
  background: #fff1f0;
}

.checklist-item.is-completed .checklist-item-title > span:first-child {
  color: var(--el-text-color-secondary);
  text-decoration: line-through;
}

.checklist-item.is-completed {
  opacity: 0.72;
}

.checklist-item-title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.checklist-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.checklist-detail-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.checklist-note-box {
  padding: 8px 10px;
  margin-top: 8px;
  border-radius: 6px;
  line-height: 1.55;
}

.checklist-note-box strong {
  display: block;
  margin-bottom: 4px;
}

.checklist-note-box p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  white-space: pre-line;
}

.checklist-note-box.normal {
  background: #eef6fb;
}

.checklist-note-box.important {
  border-left: 3px solid #e6a23c;
  background: #fff8e8;
}

.checklist-note-box.warning {
  border-left: 3px solid #f56c6c;
  background: #fff1f0;
}

.checklist-note-box.internal {
  background: #f4f4f5;
  color: var(--el-text-color-secondary);
}

.checklist-item-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px;
}

.checklist-quantity,
.muted-text {
  color: var(--el-text-color-secondary);
}

.dialog-note {
  margin-top: 0;
  color: var(--el-text-color-secondary);
}

.form-section-title {
  margin: 16px 0 10px;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.card-header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
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

@media (max-width: 760px) {
  :deep(.material-notice-dialog) {
    width: 95% !important;
  }

  .notice-option-grid {
    grid-template-columns: 1fr;
  }

  .checklist-item {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .checklist-item-actions {
    grid-column: 2;
  }
}
</style>
