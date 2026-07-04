<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules, UploadFile, UploadUserFile } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { cancelCase, getCase, updateCase } from '../api/cases'
import { createDocument, deleteDocument, listDocuments, updateDocument } from '../api/documents'
import { createReminder, deleteReminder, listReminders, updateReminder } from '../api/reminders'
import { createTask, deleteTask, listTasks, updateTask } from '../api/tasks'
import { createTimeline, listTimelines, updateTimeline } from '../api/timelines'
import type {
  Case,
  Document,
  DocumentPayload,
  Reminder,
  ReminderPayload,
  Task,
  TaskPayload,
  Timeline,
  TimelinePayload,
} from '../types/api'
import { getCaseDisplayStatus, getCaseDisplayStatusTagType } from '../utils/caseStatus'
import { formatDate, formatDateTime } from '../utils/date'
import { getReminderDisplay } from '../utils/reminder'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const caseDetail = ref<Case | null>(null)
const tasks = ref<Task[]>([])
const reminders = ref<Reminder[]>([])
const timelines = ref<Timeline[]>([])
const documents = ref<Document[]>([])
const taskSubmitting = ref(false)
const taskDialogVisible = ref(false)
const editingTaskId = ref<number | null>(null)
const taskFormRef = ref<FormInstance>()
const reminderSubmitting = ref(false)
const reminderDialogVisible = ref(false)
const editingReminderId = ref<number | null>(null)
const reminderFormRef = ref<FormInstance>()
const timelineSubmitting = ref(false)
const timelineDialogVisible = ref(false)
const editingTimelineId = ref<number | null>(null)
const timelineFormRef = ref<FormInstance>()
const documentSubmitting = ref(false)
const documentDialogVisible = ref(false)
const editingDocumentId = ref<number | null>(null)
const documentFormRef = ref<FormInstance>()
const caseDateSubmitting = ref(false)
const caseDateDialogVisible = ref(false)
const cancelSubmitting = ref(false)
const cancelDialogVisible = ref(false)
const cancelFormRef = ref<FormInstance>()
const cancelForm = ref({
  reason: '',
})
const taskForm = ref<TaskPayload>({
  case: 0,
  title: '',
  description: '',
  status: '',
  due_date: null,
})
const reminderForm = ref<ReminderPayload>({
  case: 0,
  title: '',
  remind_at: '',
  note: '',
  is_done: false,
})
const timelineForm = ref<TimelinePayload>({
  case: 0,
  occurred_at: null,
  title: '',
  content: '',
  is_visible_to_client: false,
})
const documentForm = ref<DocumentPayload>({
  case: 0,
  title: '',
  file: null,
  source: 'internal',
  is_visible_to_client: false,
})
const documentFileList = ref<UploadUserFile[]>([])
const caseDateForm = ref({
  accepted_at: null as string | null,
  applied_at: null as string | null,
  result_notified_at: null as string | null,
  completed_at: null as string | null,
})

const caseId = computed(() => Number(route.params.id))
const canCancelCase = computed(() => (
  caseDetail.value
  && !['完了', '中止', 'completed'].includes(caseDetail.value.status)
))
const displayStatus = computed(() => getCaseDisplayStatus(caseDetail.value))

const displayValue = (value?: string | null) => value || '-'
const formatBoolean = (value: boolean) => (value ? 'はい' : 'いいえ')
const getTodayDate = () => {
  const date = new Date()
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}
const sortedTimelines = computed(() => (
  timelines.value
    .map((timeline, index) => ({ timeline, index }))
    .sort((left, right) => {
      const leftDate = left.timeline.occurred_at || left.timeline.created_at
      const rightDate = right.timeline.occurred_at || right.timeline.created_at
      if (leftDate && rightDate && leftDate !== rightDate) {
        return rightDate.localeCompare(leftDate)
      }
      if (leftDate && !rightDate) return -1
      if (!leftDate && rightDate) return 1
      return left.index - right.index
    })
    .map(({ timeline }) => timeline)
))
const formatFileSize = (value?: number | null) => {
  if (!value) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

const taskStatusOptions = [
  '未対応',
  '対応中',
  '完了',
  '保留',
]

const reminderTitleOptions = [
  '在留期限3ヶ月前',
  '在留期限2ヶ月前',
  '在留期限1ヶ月前',
  '在留期限2週間前',
  '補正提出期限',
  '申請予定日',
  '入管予約日',
  '決算月2ヶ月前',
  '決算月1ヶ月前',
  '決算月当月',
  '納税証明書取得予定',
  '年金加入確認日',
  '許可更新期限',
  '契約更新期限',
  'その他',
]

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

const documentSourceOptions = [
  { label: '内部アップロード', value: 'internal' },
  { label: '顧客アップロード', value: 'client' },
  { label: 'システム生成', value: 'system' },
]

const formatDocumentSource = (source?: string | null) => {
  const option = documentSourceOptions.find((item) => item.value === source)
  return option?.label || '-'
}

const taskRules: FormRules<TaskPayload> = {
  title: [{ required: true, message: 'タイトルを入力してください。', trigger: 'blur' }],
  status: [{ required: true, message: 'ステータスを選択してください。', trigger: 'change' }],
}

const reminderRules: FormRules<ReminderPayload> = {
  title: [{ required: true, message: 'タイトルを入力してください。', trigger: 'blur' }],
  remind_at: [{ required: true, message: '通知日時を入力してください。', trigger: 'change' }],
}

const timelineRules: FormRules<TimelinePayload> = {
  title: [{ required: true, message: 'タイトルを入力してください。', trigger: 'blur' }],
}

const documentRules: FormRules<DocumentPayload> = {
  title: [{ required: true, message: 'タイトルを入力してください。', trigger: 'blur' }],
}

const cancelRules: FormRules<typeof cancelForm.value> = {
  reason: [{ required: true, message: '中止理由を入力してください。', trigger: 'blur' }],
}

const fetchCaseDetail = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [caseData, taskData, reminderData, timelineData, documentData] = await Promise.all([
      getCase(caseId.value),
      listTasks({ case: caseId.value }),
      listReminders({ case: caseId.value }),
      listTimelines({ case: caseId.value }),
      listDocuments({ case: caseId.value }),
    ])
    caseDetail.value = caseData
    tasks.value = taskData.results
    reminders.value = reminderData.results
    timelines.value = timelineData.results
    documents.value = documentData.results
  } catch {
    errorMessage.value = '案件詳細の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const fetchTasks = async () => {
  const data = await listTasks({ case: caseId.value })
  tasks.value = data.results
}

const fetchReminders = async () => {
  const data = await listReminders({ case: caseId.value })
  reminders.value = data.results
}

const fetchTimelines = async () => {
  const data = await listTimelines({ case: caseId.value })
  timelines.value = data.results
}

const fetchDocuments = async () => {
  const data = await listDocuments({ case: caseId.value })
  documents.value = data.results
}

const fetchCaseAndTimelines = async () => {
  const [caseData, timelineData] = await Promise.all([
    getCase(caseId.value),
    listTimelines({ case: caseId.value }),
  ])
  caseDetail.value = caseData
  timelines.value = timelineData.results
}

const resetTaskForm = () => {
  editingTaskId.value = null
  taskForm.value = {
    case: caseId.value,
    title: '',
    description: '',
    status: '',
    due_date: null,
  }
  taskFormRef.value?.clearValidate()
}

const resetReminderForm = () => {
  editingReminderId.value = null
  reminderForm.value = {
    case: caseId.value,
    title: '',
    remind_at: '',
    note: '',
    is_done: false,
  }
  reminderFormRef.value?.clearValidate()
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

const resetDocumentForm = () => {
  editingDocumentId.value = null
  documentForm.value = {
    case: caseId.value,
    title: '',
    file: null,
    source: 'internal',
    is_visible_to_client: false,
  }
  documentFileList.value = []
  documentFormRef.value?.clearValidate()
}

const resetCancelForm = () => {
  cancelForm.value = {
    reason: '',
  }
  cancelFormRef.value?.clearValidate()
}

const openCreateTaskDialog = () => {
  resetTaskForm()
  taskDialogVisible.value = true
}

const openCreateReminderDialog = () => {
  resetReminderForm()
  reminderDialogVisible.value = true
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

const openCreateDocumentDialog = () => {
  resetDocumentForm()
  documentDialogVisible.value = true
}

const openCancelDialog = () => {
  if (!canCancelCase.value) return
  resetCancelForm()
  cancelDialogVisible.value = true
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

const openEditTaskDialog = (task: Task) => {
  editingTaskId.value = task.id
  taskForm.value = {
    case: caseId.value,
    title: task.title,
    description: task.description,
    status: task.status,
    due_date: task.due_date,
  }
  taskFormRef.value?.clearValidate()
  taskDialogVisible.value = true
}

const openEditReminderDialog = (reminder: Reminder) => {
  editingReminderId.value = reminder.id
  reminderForm.value = {
    case: caseId.value,
    title: reminder.title,
    remind_at: reminder.remind_at,
    note: reminder.note,
    is_done: reminder.is_done,
  }
  reminderFormRef.value?.clearValidate()
  reminderDialogVisible.value = true
}

const openEditDocumentDialog = (documentItem: Document) => {
  editingDocumentId.value = documentItem.id
  documentForm.value = {
    case: caseId.value,
    title: documentItem.title,
    file: null,
    source: documentItem.source,
    is_visible_to_client: documentItem.is_visible_to_client,
  }
  documentFileList.value = documentItem.file_name
    ? [{ name: documentItem.file_name, url: documentItem.file_url || undefined }]
    : []
  documentFormRef.value?.clearValidate()
  documentDialogVisible.value = true
}

const submitTask = async () => {
  if (!taskFormRef.value) return

  const valid = await taskFormRef.value.validate().catch(() => false)
  if (!valid) return

  taskSubmitting.value = true
  try {
    const payload = {
      ...taskForm.value,
      case: caseId.value,
      due_date: taskForm.value.due_date || null,
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

const submitReminder = async () => {
  if (!reminderFormRef.value) return

  const valid = await reminderFormRef.value.validate().catch(() => false)
  if (!valid) return

  reminderSubmitting.value = true
  try {
    const payload = {
      ...reminderForm.value,
      case: caseId.value,
    }
    if (editingReminderId.value) {
      await updateReminder(editingReminderId.value, payload)
      ElMessage.success('その他リマインダーを更新しました。')
    } else {
      await createReminder(payload)
      ElMessage.success('その他リマインダーを追加しました。')
    }
    reminderDialogVisible.value = false
    await fetchReminders()
  } catch {
    ElMessage.error(
      editingReminderId.value
        ? 'その他リマインダーの更新に失敗しました。'
        : 'その他リマインダーの追加に失敗しました。',
    )
  } finally {
    reminderSubmitting.value = false
  }
}

const confirmDeleteReminder = async (reminder: Reminder) => {
  try {
    await ElMessageBox.confirm(
      `「${reminder.title}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteReminder(reminder.id)
    ElMessage.success('その他リマインダーを削除しました。')
    await fetchReminders()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('その他リマインダーの削除に失敗しました。')
    }
  }
}

const toggleReminderDone = async (reminder: Reminder) => {
  try {
    await updateReminder(reminder.id, { is_done: !reminder.is_done })
    ElMessage.success(reminder.is_done ? '未完了に戻しました。' : '完了にしました。')
    await fetchReminders()
  } catch {
    ElMessage.error('完了状態の更新に失敗しました。')
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

const submitDocument = async () => {
  if (!documentFormRef.value) return

  const valid = await documentFormRef.value.validate().catch(() => false)
  if (!valid) return
  if (!editingDocumentId.value && !documentForm.value.file) {
    ElMessage.error('ファイルを選択してください。')
    return
  }

  documentSubmitting.value = true
  try {
    const payload = {
      ...documentForm.value,
      case: caseId.value,
    }
    if (editingDocumentId.value) {
      await updateDocument(editingDocumentId.value, payload)
      ElMessage.success('書類を更新しました。')
    } else {
      await createDocument(payload)
      ElMessage.success('書類を追加しました。')
    }
    documentDialogVisible.value = false
    await fetchDocuments()
  } catch {
    ElMessage.error(editingDocumentId.value ? '書類の更新に失敗しました。' : '書類の追加に失敗しました。')
  } finally {
    documentSubmitting.value = false
  }
}

const handleDocumentFileChange = (uploadFile: UploadFile) => {
  documentForm.value.file = uploadFile.raw || null
  documentFileList.value = uploadFile.raw
    ? [{ name: uploadFile.name, raw: uploadFile.raw }]
    : []
}

const handleDocumentFileRemove = () => {
  documentForm.value.file = null
  documentFileList.value = []
}

const downloadDocument = (documentItem: Document) => {
  if (!documentItem.file_url) return
  window.open(documentItem.file_url, '_blank', 'noopener')
}

const confirmDeleteDocument = async (documentItem: Document) => {
  try {
    await ElMessageBox.confirm(
      `「${documentItem.title}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteDocument(documentItem.id)
    ElMessage.success('書類を削除しました。')
    await fetchDocuments()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('書類の削除に失敗しました。')
    }
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
    await fetchCaseAndTimelines()
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
            <span>案件進捗</span>
            <el-button @click="openCaseDateDialog">日付を編集</el-button>
          </div>
        </template>
        <el-descriptions v-if="caseDetail" :column="2" border>
          <el-descriptions-item label="現在の進捗">
            <el-tag :type="getCaseDisplayStatusTagType(displayStatus)">
              {{ displayStatus }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="受任日">
            {{ formatDate(caseDetail.accepted_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="申請日">
            {{ formatDate(caseDetail.applied_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="結果通知日">
            {{ formatDate(caseDetail.result_notified_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="完了日">
            {{ formatDate(caseDetail.completed_at) }}
          </el-descriptions-item>
        </el-descriptions>
        <p class="help-text">
          現在の進捗は案件日付情報をもとに自動表示しています。補正・追加資料対応中も、完了までは「申請中」として表示されます。
        </p>
      </el-card>

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
          <el-descriptions-item label="案件番号">
            {{ displayValue(caseDetail.case_number) }}
          </el-descriptions-item>
          <el-descriptions-item label="案件種別">
            {{ displayValue(caseDetail.case_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="登録ステータス">
            {{ displayValue(caseDetail.status) }}
          </el-descriptions-item>
          <el-descriptions-item label="顧客名">
            {{ displayValue(caseDetail.customer_name) }}
          </el-descriptions-item>
          <el-descriptions-item label="会社名">
            {{ displayValue(caseDetail.company_name) }}
          </el-descriptions-item>
          <el-descriptions-item label="担当者">
            {{ displayValue(caseDetail.responsible_employee_name) }}
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <template v-if="false">
        <el-card shadow="never">
          <template #header>
            <div class="card-header-row">
              <span>その他リマインダー</span>
              <div class="card-actions">
                <el-button type="primary" @click="openCreateReminderDialog">
                  リマインダー追加
                </el-button>
              </div>
            </div>
          </template>
          <el-table :data="reminders" stripe>
            <el-table-column label="対象" min-width="160">
              <template #default="{ row }">{{ getReminderDisplay(row).target }}</template>
            </el-table-column>
            <el-table-column label="期限種別" min-width="130">
              <template #default="{ row }">{{ getReminderDisplay(row).deadlineType }}</template>
            </el-table-column>
            <el-table-column label="基準日 / 到期日" min-width="130">
              <template #default="{ row }">{{ getReminderDisplay(row).baseDate }}</template>
            </el-table-column>
            <el-table-column label="通知日時" min-width="160">
              <template #default="{ row }">{{ getReminderDisplay(row).notifyAt }}</template>
            </el-table-column>
            <el-table-column label="残り日数" min-width="150">
              <template #default="{ row }">
                <el-tag :type="row.is_done ? 'info' : 'warning'">
                  {{ getReminderDisplay(row).remainingText }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="完了状態" width="110">
              <template #default="{ row }">{{ getReminderDisplay(row).status }}</template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" @click="openEditReminderDialog(row)">編集</el-button>
                <el-button text type="danger" @click="confirmDeleteReminder(row)">削除</el-button>
                <el-button text type="primary" @click="toggleReminderDone(row)">
                  {{ row.is_done ? '未完了' : '完了' }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <p v-if="!reminders.length" class="empty-text">該当データなし</p>
        </el-card>
      </template>

      <el-card shadow="never">
        <template #header>
          <div class="card-header-row">
            <span>書類</span>
            <el-button type="primary" @click="openCreateDocumentDialog">書類追加</el-button>
          </div>
        </template>
        <el-table :data="documents" stripe>
          <el-table-column prop="title" label="タイトル" min-width="180" />
          <el-table-column prop="file_name" label="ファイル名" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ displayValue(row.file_name) }}</template>
          </el-table-column>
          <el-table-column label="ファイルサイズ" width="130">
            <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column prop="content_type" label="種類" min-width="160">
            <template #default="{ row }">{{ displayValue(row.content_type) }}</template>
          </el-table-column>
          <el-table-column label="來源" width="150">
            <template #default="{ row }">{{ formatDocumentSource(row.source) }}</template>
          </el-table-column>
          <el-table-column label="顧客表示" width="110">
            <template #default="{ row }">{{ formatBoolean(row.is_visible_to_client) }}</template>
          </el-table-column>
          <el-table-column label="更新日時" min-width="160">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.file_url"
                text
                type="primary"
                @click="downloadDocument(row)"
              >
                ダウンロード
              </el-button>
              <el-button text type="primary" @click="openEditDocumentDialog(row)">編集</el-button>
              <el-button text type="danger" @click="confirmDeleteDocument(row)">削除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="!documents.length" class="empty-text">該当データなし</p>
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
          <el-table-column label="顧客表示" width="110">
            <template #default="{ row }">{{ formatBoolean(row.is_visible_to_client) }}</template>
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

      <template v-if="false">
        <el-card shadow="never">
          <template #header>
            <div class="card-header-row">
              <span>内部タスク</span>
              <el-button type="primary" @click="openCreateTaskDialog">タスク追加</el-button>
            </div>
          </template>
          <el-table :data="tasks" stripe>
            <el-table-column prop="title" label="タイトル" min-width="180" />
            <el-table-column prop="status" label="ステータス" width="130" />
            <el-table-column label="期限" width="130">
              <template #default="{ row }">{{ formatDate(row.due_date) }}</template>
            </el-table-column>
            <el-table-column label="更新日時" min-width="160">
              <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" @click="openEditTaskDialog(row)">編集</el-button>
                <el-button text type="danger" @click="confirmDeleteTask(row)">削除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <p v-if="!tasks.length" class="empty-text">該当データなし</p>
        </el-card>
      </template>

      <el-card shadow="never" class="placeholder-card">
        <template #header>申請書作成</template>
        <p>準備中</p>
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
        <el-button type="primary" :loading="caseDateSubmitting" @click="submitCaseDates">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="taskDialogVisible"
      :title="editingTaskId ? 'タスク編集' : 'タスク追加'"
      width="560px"
      @closed="resetTaskForm"
    >
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskRules" label-position="top">
        <el-form-item label="タイトル" prop="title">
          <el-input v-model="taskForm.title" />
        </el-form-item>
        <el-form-item label="内容" prop="description">
          <el-input v-model="taskForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="ステータス" prop="status">
            <el-select v-model="taskForm.status" placeholder="選択してください" class="form-control">
              <el-option
                v-for="status in taskStatusOptions"
                :key="status"
                :label="status"
                :value="status"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="期限" prop="due_date">
            <el-date-picker
              v-model="taskForm.due_date"
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
      v-model="reminderDialogVisible"
      :title="editingReminderId ? 'その他リマインダー編集' : 'その他リマインダー追加'"
      width="560px"
      @closed="resetReminderForm"
    >
      <el-form ref="reminderFormRef" :model="reminderForm" :rules="reminderRules" label-position="top">
        <el-form-item label="タイトル" prop="title">
          <el-select
            v-model="reminderForm.title"
            allow-create
            clearable
            filterable
            placeholder="選択または入力してください"
            class="form-control"
          >
            <el-option
              v-for="title in reminderTitleOptions"
              :key="title"
              :label="title"
              :value="title"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="通知日時" prop="remind_at">
          <el-date-picker
            v-model="reminderForm.remind_at"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="YYYY-MM-DD HH:mm"
            class="form-control"
          />
        </el-form-item>
        <el-form-item label="備考" prop="note">
          <el-input v-model="reminderForm.note" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="完了状態" prop="is_done">
          <el-switch v-model="reminderForm.is_done" active-text="完了" inactive-text="未完了" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="reminderDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="reminderSubmitting" @click="submitReminder">
          {{ editingReminderId ? '保存' : '追加' }}
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
        <el-form-item label="顧客表示" prop="is_visible_to_client">
          <el-switch v-model="timelineForm.is_visible_to_client" active-text="表示" inactive-text="非表示" />
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
      v-model="documentDialogVisible"
      :title="editingDocumentId ? '書類編集' : '書類追加'"
      width="640px"
      @closed="resetDocumentForm"
    >
      <el-form ref="documentFormRef" :model="documentForm" :rules="documentRules" label-position="top">
        <el-form-item label="タイトル" prop="title">
          <el-input v-model="documentForm.title" />
        </el-form-item>
        <el-form-item label="ファイル">
          <el-upload
            v-model:file-list="documentFileList"
            :auto-upload="false"
            :limit="1"
            :on-change="handleDocumentFileChange"
            :on-remove="handleDocumentFileRemove"
          >
            <el-button>ファイルを選択</el-button>
            <template #tip>
              <div class="upload-tip">PDF、画像、Excel、Word 等資料をアップロードできます。</div>
            </template>
          </el-upload>
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="來源" prop="source">
            <el-select v-model="documentForm.source" placeholder="選択してください" class="form-control">
              <el-option
                v-for="option in documentSourceOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="顧客表示" prop="is_visible_to_client">
            <el-switch v-model="documentForm.is_visible_to_client" active-text="表示" inactive-text="非表示" />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="documentDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="documentSubmitting" @click="submitDocument">
          {{ editingDocumentId ? '保存' : '追加' }}
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
        <el-button type="danger" :loading="cancelSubmitting" @click="submitCancelCase">
          確認
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
