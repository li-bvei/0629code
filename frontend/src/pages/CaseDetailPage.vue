<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  applyCaseChecklistTemplate,
  cancelCase,
  createCaseChecklistItem,
  deleteCaseChecklistItem,
  getCase,
  listCaseChecklistItems,
  listCaseChecklistTemplates,
  updateCase,
  updateCaseChecklistItem,
} from '../api/cases'
import { listEmployees } from '../api/employees'
import { createTask, deleteTask, listTasks, updateTask } from '../api/tasks'
import { createTimeline, listTimelines, updateTimeline } from '../api/timelines'
import type {
  Case,
  CaseChecklistItem,
  CaseChecklistItemPayload,
  CaseChecklistItemType,
  CaseChecklistTemplate,
  Employee,
  Task,
  TaskPayload,
  Timeline,
  TimelinePayload,
} from '../types/api'
import { getCaseDisplayStatus, getCaseDisplayStatusTagType } from '../utils/caseStatus'
import { formatDate, formatDateTime } from '../utils/date'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const caseDetail = ref<Case | null>(null)
const employees = ref<Employee[]>([])
const tasks = ref<Task[]>([])
const timelines = ref<Timeline[]>([])
const checklistItems = ref<CaseChecklistItem[]>([])
const checklistTemplates = ref<CaseChecklistTemplate[]>([])
const taskSubmitting = ref(false)
const taskDialogVisible = ref(false)
const editingTaskId = ref<number | null>(null)
const editingTaskResponsibleEmployeeName = ref('')
const taskFormRef = ref<FormInstance>()
const timelineSubmitting = ref(false)
const timelineDialogVisible = ref(false)
const editingTimelineId = ref<number | null>(null)
const timelineFormRef = ref<FormInstance>()
const caseDateSubmitting = ref(false)
const caseDateDialogVisible = ref(false)
const cancelSubmitting = ref(false)
const cancelDialogVisible = ref(false)
const cancelFormRef = ref<FormInstance>()
const checklistItemSubmitting = ref(false)
const checklistItemDialogVisible = ref(false)
const editingChecklistItemId = ref<number | null>(null)
const checklistItemFormRef = ref<FormInstance>()
const applyTemplateDialogVisible = ref(false)
const selectedChecklistTemplateId = ref<number | null>(null)
const applyingChecklistTemplate = ref(false)

const caseId = computed(() => Number(route.params.id))
const displayStatus = computed(() => getCaseDisplayStatus(caseDetail.value))
const canCancelCase = computed(() => (
  caseDetail.value
  && !['完了', '中止', 'completed', 'closed'].includes(caseDetail.value.status)
))

const taskStatusOptions = [
  { label: '未開始', value: 'pending', type: 'info' },
  { label: '進行中', value: 'in_progress', type: 'warning' },
  { label: '完了', value: 'completed', type: 'success' },
  { label: '保留', value: 'paused', type: 'primary' },
  { label: '取消', value: 'cancelled', type: 'danger' },
] as const

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

const taskForm = ref<TaskPayload>({
  case: 0,
  title: '',
  description: '',
  responsible_employee: null,
  status: 'pending',
  sort_order: 0,
  planned_completion_date: null,
  completed_at: null,
})
const timelineForm = ref<TimelinePayload>({
  case: 0,
  occurred_at: null,
  title: '',
  content: '',
  is_visible_to_client: false,
})
const caseDateForm = ref({
  accepted_at: null as string | null,
  applied_at: null as string | null,
  result_notified_at: null as string | null,
  completed_at: null as string | null,
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
  sort_order: 0,
})

const taskRules: FormRules<TaskPayload> = {
  title: [{ required: true, message: 'タスク名を入力してください。', trigger: 'blur' }],
  status: [{ required: true, message: 'ステータスを選択してください。', trigger: 'change' }],
}
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

const getTaskStatusLabel = (status: string) => (
  taskStatusOptions.find((option) => option.value === status)?.label || status || '-'
)

const getTaskStatusTagType = (status: string) => (
  taskStatusOptions.find((option) => option.value === status)?.type || 'info'
)

const getChecklistItemTypeLabel = (type: CaseChecklistItemType) => (
  checklistItemTypeOptions.find((option) => option.value === type)?.label || type
)

const isFinishedTask = (task: Task) => ['completed', 'cancelled'].includes(task.status)

const getTaskRowClassName = ({ row }: { row: Task }) => (isFinishedTask(row) ? 'task-row-finished' : '')

const sortedTasks = computed(() => (
  [...tasks.value].sort((left, right) => {
    const leftFinished = isFinishedTask(left) ? 1 : 0
    const rightFinished = isFinishedTask(right) ? 1 : 0
    if (leftFinished !== rightFinished) return leftFinished - rightFinished
    if ((left.sort_order || 0) !== (right.sort_order || 0)) {
      return (left.sort_order || 0) - (right.sort_order || 0)
    }
    return left.id - right.id
  })
))

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

const taskProgressText = computed(() => {
  const total = tasks.value.length
  const completed = tasks.value.filter((task) => task.status === 'completed').length
  return `${completed} / ${total}`
})

const checklistProgressText = computed(() => {
  const total = checklistItems.value.length
  const completed = checklistItems.value.filter((item) => item.is_completed).length
  return `${completed} / ${total}`
})

const checklistProgressPercentage = computed(() => {
  if (!checklistItems.value.length) return 0
  const completed = checklistItems.value.filter((item) => item.is_completed).length
  return Math.round((completed / checklistItems.value.length) * 100)
})

const nextTask = computed(() => sortedTasks.value.find((task) => !isFinishedTask(task)) || null)

const taskEmployeeOptions = computed(() => {
  const options = [...employees.value]
  const selectedEmployeeId = taskForm.value.responsible_employee
  if (
    selectedEmployeeId
    && !options.some((employee) => employee.id === selectedEmployeeId)
    && editingTaskResponsibleEmployeeName.value
  ) {
    options.push({
      id: selectedEmployeeId,
      name: `${editingTaskResponsibleEmployeeName.value}（無効）`,
      email: '',
      phone: '',
      is_active: false,
      created_at: '',
      updated_at: '',
    })
  }
  return options
})

const fetchCaseDetail = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [caseData, taskData, timelineData, employeeData, checklistData, templateData] = await Promise.all([
      getCase(caseId.value),
      listTasks({ case: caseId.value }),
      listTimelines({ case: caseId.value }),
      listEmployees({ is_active: true }),
      listCaseChecklistItems({ case: caseId.value }),
      listCaseChecklistTemplates({ is_active: true }),
    ])
    caseDetail.value = caseData
    tasks.value = taskData.results
    timelines.value = timelineData.results
    employees.value = employeeData.results
    checklistItems.value = checklistData.results
    checklistTemplates.value = templateData.results
  } catch {
    errorMessage.value = '案件詳細の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const fetchTasks = async () => {
  const data = await listTasks({ case: caseId.value })
  tasks.value = data.results
  caseDetail.value = await getCase(caseId.value)
}

const fetchTimelines = async () => {
  const data = await listTimelines({ case: caseId.value })
  timelines.value = data.results
}

const fetchChecklistItems = async () => {
  const data = await listCaseChecklistItems({ case: caseId.value })
  checklistItems.value = data.results
}

const resetTaskForm = () => {
  const nextSortOrder = tasks.value.reduce((maxValue, task) => Math.max(maxValue, task.sort_order || 0), 0) + 10
  editingTaskId.value = null
  editingTaskResponsibleEmployeeName.value = ''
  taskForm.value = {
    case: caseId.value,
    title: '',
    description: '',
    responsible_employee: caseDetail.value?.responsible_employee || null,
    status: 'pending',
    sort_order: nextSortOrder,
    planned_completion_date: null,
    completed_at: null,
  }
  taskFormRef.value?.clearValidate()
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
    sort_order: nextSortOrder,
  }
  checklistItemFormRef.value?.clearValidate()
}

const openCreateTaskDialog = () => {
  resetTaskForm()
  taskDialogVisible.value = true
}

const openEditTaskDialog = (task: Task) => {
  editingTaskId.value = task.id
  editingTaskResponsibleEmployeeName.value = task.responsible_employee_name || ''
  taskForm.value = {
    case: caseId.value,
    title: task.title,
    description: task.description,
    responsible_employee: task.responsible_employee,
    status: task.status,
    sort_order: task.sort_order,
    planned_completion_date: task.planned_completion_date || task.due_date,
    completed_at: task.completed_at,
  }
  taskFormRef.value?.clearValidate()
  taskDialogVisible.value = true
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

const openCaseDateDialog = () => {
  if (!caseDetail.value) return
  caseDateForm.value = {
    accepted_at: caseDetail.value.accepted_at,
    applied_at: caseDetail.value.applied_at,
    result_notified_at: caseDetail.value.result_notified_at,
    completed_at: caseDetail.value.completed_at,
  }
  caseDateDialogVisible.value = true
}

const openCancelDialog = () => {
  if (!canCancelCase.value) return
  resetCancelForm()
  cancelDialogVisible.value = true
}

const openCreateChecklistItemDialog = () => {
  resetChecklistItemForm()
  checklistItemDialogVisible.value = true
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
    sort_order: item.sort_order,
  }
  checklistItemFormRef.value?.clearValidate()
  checklistItemDialogVisible.value = true
}

const openApplyTemplateDialog = () => {
  selectedChecklistTemplateId.value = checklistTemplates.value[0]?.id || null
  applyTemplateDialogVisible.value = true
}

const submitTask = async () => {
  if (!taskFormRef.value) return

  const valid = await taskFormRef.value.validate().catch(() => false)
  if (!valid) return

  taskSubmitting.value = true
  try {
    const payload: TaskPayload = {
      ...taskForm.value,
      case: caseId.value,
      responsible_employee: taskForm.value.responsible_employee || null,
      planned_completion_date: taskForm.value.planned_completion_date || null,
      completed_at: taskForm.value.completed_at || null,
    }
    if (payload.status === 'completed' && !payload.completed_at) {
      payload.completed_at = getTodayDate()
    }
    if (payload.status !== 'completed') {
      payload.completed_at = null
    }

    if (editingTaskId.value) {
      await updateTask(editingTaskId.value, payload)
      ElMessage.success('タスクを更新しました。')
    } else {
      await createTask(payload)
      ElMessage.success('タスクを追加しました。')
    }
    taskDialogVisible.value = false
    await fetchTasks()
  } catch {
    ElMessage.error(editingTaskId.value ? 'タスクの更新に失敗しました。' : 'タスクの追加に失敗しました。')
  } finally {
    taskSubmitting.value = false
  }
}

const confirmDeleteTask = async (task: Task) => {
  try {
    await ElMessageBox.confirm(
      `「${task.title}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteTask(task.id)
    ElMessage.success('タスクを削除しました。')
    await fetchTasks()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('タスクの削除に失敗しました。')
    }
  }
}

const updateTaskStatus = async (task: Task, status: TaskPayload['status']) => {
  try {
    await updateTask(task.id, {
      status,
      completed_at: status === 'completed' ? (task.completed_at || getTodayDate()) : null,
    })
    ElMessage.success(status === 'completed' ? 'タスクを完了しました。' : 'タスクを更新しました。')
    await fetchTasks()
  } catch {
    ElMessage.error('タスク状態の更新に失敗しました。')
  }
}

const moveTask = async (task: Task, direction: -1 | 1) => {
  const currentIndex = sortedTasks.value.findIndex((item) => item.id === task.id)
  const targetTask = sortedTasks.value[currentIndex + direction]
  if (!targetTask) return

  try {
    await Promise.all([
      updateTask(task.id, { sort_order: targetTask.sort_order }),
      updateTask(targetTask.id, { sort_order: task.sort_order }),
    ])
    await fetchTasks()
  } catch {
    ElMessage.error('並び順の更新に失敗しました。')
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
    await fetchChecklistItems()
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
    await fetchChecklistItems()
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
    await fetchChecklistItems()
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

const submitCaseDates = async () => {
  caseDateSubmitting.value = true
  try {
    await updateCase(caseId.value, {
      accepted_at: caseDateForm.value.accepted_at || null,
      applied_at: caseDateForm.value.applied_at || null,
      result_notified_at: caseDateForm.value.result_notified_at || null,
      completed_at: caseDateForm.value.completed_at || null,
    })
    caseDateDialogVisible.value = false
    caseDetail.value = await getCase(caseId.value)
    ElMessage.success('案件日付情報を更新しました')
  } catch {
    ElMessage.error('案件日付情報の更新に失敗しました。')
  } finally {
    caseDateSubmitting.value = false
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

onMounted(() => {
  fetchCaseDetail()
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
            <el-button v-if="canCancelCase" type="danger" @click="openCancelDialog">
              案件を中止する
            </el-button>
          </div>
        </template>
        <el-descriptions v-if="caseDetail" :column="2" border>
          <el-descriptions-item label="案件番号">{{ displayValue(caseDetail.case_number) }}</el-descriptions-item>
          <el-descriptions-item label="案件種別">{{ displayValue(caseDetail.case_type) }}</el-descriptions-item>
          <el-descriptions-item label="登録ステータス">{{ displayValue(caseDetail.status) }}</el-descriptions-item>
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
            <span>現在の状態</span>
            <el-button @click="openCaseDateDialog">日付を編集</el-button>
          </div>
        </template>
        <el-descriptions v-if="caseDetail" :column="2" border>
          <el-descriptions-item label="現在の進捗">
            <el-tag :type="getCaseDisplayStatusTagType(displayStatus)">
              {{ displayStatus }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="タスク進捗">{{ taskProgressText }}</el-descriptions-item>
          <el-descriptions-item label="次のタスク">
            {{ nextTask?.title || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="次の担当者">
            {{ nextTask?.responsible_employee_name || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="受任日">{{ formatDate(caseDetail.accepted_at) }}</el-descriptions-item>
          <el-descriptions-item label="申請日">{{ formatDate(caseDetail.applied_at) }}</el-descriptions-item>
          <el-descriptions-item label="結果通知日">{{ formatDate(caseDetail.result_notified_at) }}</el-descriptions-item>
          <el-descriptions-item label="完了日">{{ formatDate(caseDetail.completed_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>案件進捗・必要資料</span>
            <div class="header-actions">
              <el-button plain @click="openApplyTemplateDialog">テンプレートから追加</el-button>
              <el-button type="primary" @click="openCreateChecklistItemDialog">項目追加</el-button>
            </div>
          </div>
        </template>
        <div class="checklist-summary">
          <span>案件事項：{{ checklistProgressText }}</span>
          <span>完了率：{{ checklistProgressPercentage }}%</span>
        </div>
        <el-empty v-if="!checklistItems.length" description="案件事項がありません" />
        <div v-else class="checklist-groups">
          <section v-for="group in checklistGroups" :key="group.category" class="checklist-group">
            <h3>{{ group.category }}</h3>
            <div
              v-for="item in group.items"
              :key="item.id"
              class="checklist-item"
              :class="{ 'is-completed': item.is_completed }"
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
                  <el-tag v-if="item.is_completed" size="small" type="success">完了</el-tag>
                  <span v-else class="muted-text">未完了</span>
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
            <span>タスク一覧</span>
            <el-button type="primary" @click="openCreateTaskDialog">タスク追加</el-button>
          </div>
        </template>
        <el-table :data="sortedTasks" stripe row-key="id" :row-class-name="getTaskRowClassName">
          <el-table-column label="步骤" width="80">
            <template #default="{ $index }">{{ $index + 1 }}</template>
          </el-table-column>
          <el-table-column prop="title" label="タスク名" min-width="180" show-overflow-tooltip />
          <el-table-column label="担当者" min-width="120">
            <template #default="{ row }">{{ row.responsible_employee_name || '未指定' }}</template>
          </el-table-column>
          <el-table-column label="ステータス" width="110">
            <template #default="{ row }">
              <el-tag :type="getTaskStatusTagType(row.status)">
                {{ getTaskStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="予定完了日" width="130">
            <template #default="{ row }">{{ formatDate(row.planned_completion_date || row.due_date) }}</template>
          </el-table-column>
          <el-table-column label="完了日" width="130">
            <template #default="{ row }">{{ formatDate(row.completed_at) }}</template>
          </el-table-column>
          <el-table-column prop="description" label="備考" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ row.description || '-' }}</template>
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
                    <el-dropdown-item @click="openEditTaskDialog(row)">編集</el-dropdown-item>
                    <el-dropdown-item v-if="row.status !== 'completed'" @click="updateTaskStatus(row, 'completed')">
                      完了
                    </el-dropdown-item>
                    <el-dropdown-item @click="moveTask(row, -1)">上へ</el-dropdown-item>
                    <el-dropdown-item @click="moveTask(row, 1)">下へ</el-dropdown-item>
                    <el-dropdown-item v-if="row.status !== 'paused'" divided @click="updateTaskStatus(row, 'paused')">
                      保留
                    </el-dropdown-item>
                    <el-dropdown-item divided class="danger-item" @click="confirmDeleteTask(row)">削除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="!tasks.length" class="empty-text">まだタスクがありません</p>
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

    <el-dialog
      v-model="caseDateDialogVisible"
      title="案件日付情報を編集"
      width="560px"
    >
      <el-form :model="caseDateForm" label-position="top">
        <div class="form-grid">
          <el-form-item label="受任日">
            <el-date-picker
              v-model="caseDateForm.accepted_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="申請日">
            <el-date-picker
              v-model="caseDateForm.applied_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="結果通知日">
            <el-date-picker
              v-model="caseDateForm.result_notified_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="完了日">
            <el-date-picker
              v-model="caseDateForm.completed_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="caseDateDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="caseDateSubmitting" @click="submitCaseDates">保存</el-button>
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
          <el-input v-model="checklistItemForm.name" />
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
        <div class="form-grid">
          <el-form-item label="必須" prop="is_required">
            <el-switch v-model="checklistItemForm.is_required" active-text="必須" inactive-text="任意" />
          </el-form-item>
          <el-form-item label="完了" prop="is_completed">
            <el-switch v-model="checklistItemForm.is_completed" active-text="完了" inactive-text="未完了" />
          </el-form-item>
        </div>
        <el-form-item label="備考" prop="note">
          <el-input v-model="checklistItemForm.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="checklistItemDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="checklistItemSubmitting" @click="submitChecklistItem">
          {{ editingChecklistItemId ? '保存' : '追加' }}
        </el-button>
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
      v-model="taskDialogVisible"
      :title="editingTaskId ? 'タスク編集' : 'タスク追加'"
      width="680px"
      @closed="resetTaskForm"
    >
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskRules" label-position="top">
        <el-form-item label="タスク名" prop="title">
          <el-input v-model="taskForm.title" />
        </el-form-item>
        <el-form-item label="詳細内容 / 備考" prop="description">
          <el-input v-model="taskForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="担当者" prop="responsible_employee">
            <div class="inline-field-with-action">
              <el-select
                v-model="taskForm.responsible_employee"
                clearable
                filterable
                placeholder="未指定"
                class="form-control"
              >
                <el-option label="未指定" :value="null" />
                <el-option
                  v-for="employee in taskEmployeeOptions"
                  :key="employee.id"
                  :label="employee.name"
                  :value="employee.id"
                />
              </el-select>
              <el-button @click="router.push('/employees')">担当者管理</el-button>
            </div>
          </el-form-item>
          <el-form-item label="ステータス" prop="status">
            <el-select v-model="taskForm.status" placeholder="選択してください" class="form-control">
              <el-option
                v-for="status in taskStatusOptions"
                :key="status.value"
                :label="status.label"
                :value="status.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="表示順" prop="sort_order">
            <el-input-number v-model="taskForm.sort_order" :min="0" :step="10" class="form-control" />
          </el-form-item>
          <el-form-item label="予定完了日" prop="planned_completion_date">
            <el-date-picker
              v-model="taskForm.planned_completion_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="完了日" prop="completed_at">
            <el-date-picker
              v-model="taskForm.completed_at"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="taskDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="taskSubmitting" @click="submitTask">
          {{ editingTaskId ? '保存' : '追加' }}
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
:deep(.task-row-finished) {
  color: var(--el-text-color-secondary);
  text-decoration: line-through;
}

.inline-field-with-action {
  display: flex;
  gap: 8px;
  width: 100%;
}

.inline-field-with-action .form-control {
  flex: 1;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.checklist-summary {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
  font-weight: 600;
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
  padding: 10px 0;
  border-top: 1px solid var(--el-border-color-lighter);
}

.checklist-item.is-completed .checklist-item-title > span:first-child {
  color: var(--el-text-color-secondary);
  text-decoration: line-through;
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
</style>
