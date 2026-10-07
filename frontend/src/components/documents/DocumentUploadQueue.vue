<script setup lang="ts">
// 複数ファイルの登録（P2）。案件詳細と書類管理で共通の部品。
// 選択・ドラッグした複数ファイルを行列に並べ、1 件ずつ登録する（1 ファイル＝1 記録、権限・保存・監査も 1 件ずつ）。
// 進捗・状態・失敗理由を行ごとに表示し、失敗したものだけ再試行できる。上限は後端の値を使い、登録前に後端で一括確認する。
// P6：ファイルごとに「資料内容」（例：住民票）が必須。未入力の行があれば登録を始めず、行列と入力はそのまま残す。
// 保存されるファイル名「資料内容-顧客名.拡張子」の顧客名は後端が案件から決める（画面では指定しない）。
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { checkUploadBatch, createDocument, getUploadPolicy } from '../../api/documents'
import { DOCUMENT_CATEGORY_OPTIONS } from '../../types/api'
import type { CaseChecklistItem, DocumentCategory } from '../../types/api'
import {
  CONTENT_LABEL_SUGGESTIONS, DEFAULT_UPLOAD_POLICY, addFiles, contentLabelProblem, fillMissingLabels, formatBytes,
  isRetryable, markFailedForRetry, removeFinished, rowsMissingLabel, runQueue, summarizeQueue, uploadErrorText,
  type QueueItem, type UploadPolicy,
} from '../../utils/uploadQueue'

const props = defineProps<{
  caseId: number | null
  checklistItems?: CaseChecklistItem[]
}>()
const emit = defineEmits<{ (e: 'uploaded', count: number): void }>()

type Row = QueueItem<File> & { checklistItem?: number | null }

const policy = ref<UploadPolicy>(DEFAULT_UPLOAD_POLICY)
const queue = ref<Row[]>([])
const defaultCategory = ref<DocumentCategory>('other')
const running = ref(false)
const batchErrors = ref<string[]>([])
const dragging = ref(false)
const input = ref<HTMLInputElement>()

onMounted(async () => {
  try {
    policy.value = await getUploadPolicy()
  } catch {
    // 取得できなければ既定値で案内する（判定は後端が行う）
  }
})

const summary = computed(() => summarizeQueue(queue.value))
const retryable = computed(() => queue.value.filter((item) => isRetryable(item, policy.value)))
const canStart = computed(() => Boolean(props.caseId) && !running.value && summary.value.waiting > 0)
const limitText = computed(() => (
  `1 ファイル ${formatBytes(policy.value.max_file_bytes)} まで（ZIP は ${formatBytes(policy.value.zip_upload_max_bytes ?? policy.value.max_file_bytes)} まで）・一度に ${policy.value.batch_max_files} 件・合計 ${formatBytes(policy.value.batch_max_total_bytes)} まで`
))
const showLabelErrors = ref(false)  // 「登録を開始」を押した後だけ、未入力の行に理由を出す
const labelError = (row: Row) => (
  showLabelErrors.value && row.status === 'waiting' ? contentLabelProblem(row.contentLabel, policy.value) : ''
)
const bulkLabel = ref('')
const applyBulkLabel = () => {
  const label = bulkLabel.value.trim()
  if (!label) return
  queue.value = fillMissingLabels(queue.value, label) as Row[]
}
const suggestLabels = (query: string, callback: (items: { value: string }[]) => void) => {
  const text = (query || '').trim()
  callback(CONTENT_LABEL_SUGGESTIONS.filter((item) => !text || item.includes(text)).map((value) => ({ value })))
}

const add = (files: File[]) => {
  if (!files.length) return
  const result = addFiles(queue.value, files, policy.value, defaultCategory.value)
  queue.value = result.queue as Row[]
  batchErrors.value = result.errors
}

const onPick = (event: Event) => {
  const target = event.target as HTMLInputElement
  add(Array.from(target.files ?? []))
  target.value = ''  // 同じファイルを選び直せるように
}

const onDrop = (event: DragEvent) => {
  dragging.value = false
  if (running.value) return
  add(Array.from(event.dataTransfer?.files ?? []))
}

const update = (key: string, patch: Partial<Row>) => {
  queue.value = queue.value.map((item) => (item.key === key ? { ...item, ...patch } : item))
}

const remove = (key: string) => {
  queue.value = queue.value.filter((item) => item.key !== key)
}

const start = async () => {
  if (!props.caseId || running.value) return
  const caseId = props.caseId
  const missing = rowsMissingLabel(queue.value, policy.value)
  if (missing.length) {
    // 何も登録せず、行列と入力はそのまま（入力すればそのまま登録できる）
    showLabelErrors.value = true
    batchErrors.value = [`資料内容が未入力・不正なファイルが ${missing.length} 件あります。各行の「資料内容」を入力してから登録してください。`]
    return
  }
  showLabelErrors.value = false
  running.value = true
  batchErrors.value = []
  try {
    const waiting = queue.value.filter((item) => item.status === 'waiting')
    // 登録前に後端で一括確認（件数・合計・1 件ごとの問題）。一覧全体の問題があれば何も登録しない。
    let check
    try {
      check = await checkUploadBatch(caseId, waiting.map((item) => ({ name: item.name, size: item.size })))
    } catch (error) {
      batchErrors.value = [uploadErrorText(error)]
      return
    }
    if (check.errors.length) {
      batchErrors.value = check.errors
      return
    }
    check.files.forEach((row) => {
      if (row.problem) update(waiting[row.index].key, { status: 'failed', error: row.problem })
    })
    const before = summary.value.success
    await runQueue(
      queue.value,
      (item, onProgress) => createDocument({
        case: caseId, title: item.name, file: item.file, category: item.category as DocumentCategory,
        checklist_item: (item as Row).checklistItem || null, content_label: item.contentLabel.trim(),
      }, onProgress),
      update,
    )
    const added = summary.value.success - before
    if (added) emit('uploaded', added)
    if (summary.value.failed) {
      ElMessage.warning(`${added} 件を登録しました。${summary.value.failed} 件は登録できませんでした（理由は一覧を確認）。`)
    } else if (added) {
      ElMessage.success(`${added} 件を登録しました。`)
    }
  } finally {
    running.value = false  // 失敗しても操作できない状態のまま残さない
  }
}

const retryFailed = async () => {
  queue.value = markFailedForRetry(queue.value, policy.value) as Row[]
  await start()
}

const retryOne = async (key: string) => {
  update(key, { status: 'waiting', progress: 0, error: '' })
  await start()
}

const clearFinished = () => {
  queue.value = removeFinished(queue.value) as Row[]
  batchErrors.value = []
}

const statusLabel: Record<string, { text: string; type: 'info' | 'primary' | 'success' | 'danger' }> = {
  waiting: { text: '待機', type: 'info' },
  uploading: { text: '登録中', type: 'primary' },
  success: { text: '成功', type: 'success' },
  failed: { text: '失敗', type: 'danger' },
}

defineExpose({ queue, add, start, retryFailed, summary, running })
</script>

<template>
  <div class="upload-queue">
    <div
      class="upload-drop"
      :class="{ 'is-dragging': dragging, 'is-disabled': !caseId }"
      role="button"
      tabindex="0"
      aria-label="ファイルを選択またはここにドラッグ"
      @click="caseId && !running && input?.click()"
      @keydown.enter.prevent="caseId && !running && input?.click()"
      @dragover.prevent="dragging = Boolean(caseId)"
      @dragleave.prevent="dragging = false"
      @drop.prevent="caseId && onDrop($event)"
    >
      <strong>{{ caseId ? 'ファイルをここにドラッグ、またはクリックして選択（複数可）' : '案件を選ぶとファイルを登録できます' }}</strong>
      <span>{{ limitText }}</span>
      <input ref="input" type="file" multiple hidden :disabled="!caseId || running" @change="onPick" />
    </div>

    <div class="upload-toolbar">
      <label class="upload-default">
        <span>追加するファイルの分類</span>
        <el-select v-model="defaultCategory" size="small" style="width: 150px">
          <el-option v-for="option in DOCUMENT_CATEGORY_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </label>
      <label v-if="queue.length" class="upload-default">
        <span>資料内容をまとめて入力（未入力の行だけ）</span>
        <el-autocomplete v-model="bulkLabel" :fetch-suggestions="suggestLabels" size="small" style="width: 150px"
                         placeholder="例：住民票" :disabled="running" @keyup.enter="applyBulkLabel" />
        <el-button size="small" :disabled="running || !bulkLabel.trim()" @click="applyBulkLabel">入れる</el-button>
      </label>
      <span v-if="queue.length" class="upload-summary">
        待機 {{ summary.waiting }}・登録中 {{ summary.uploading }}・成功 {{ summary.success }}・失敗 {{ summary.failed }}（{{ formatBytes(summary.totalBytes) }}）
      </span>
    </div>

    <el-alert v-for="message in batchErrors" :key="message" :title="message" type="error" :closable="false" show-icon class="upload-alert" />

    <el-table v-if="queue.length" :data="queue" size="small" row-key="key" class="upload-table">
      <el-table-column label="ファイル" min-width="180">
        <template #default="{ row }">
          <div class="upload-name" :title="row.name">{{ row.name }}</div>
          <div class="upload-sub">{{ formatBytes(row.size) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="資料内容（必須）" min-width="170">
        <template #default="{ row }">
          <el-autocomplete v-model="row.contentLabel" :fetch-suggestions="suggestLabels" size="small" placeholder="例：住民票"
                           :maxlength="policy.content_label_max_length ?? 60" aria-label="資料内容"
                           :disabled="running || row.status === 'uploading' || row.status === 'success'"
                           :class="{ 'is-label-error': Boolean(labelError(row)) }" />
          <div v-if="labelError(row)" class="upload-error" role="alert">{{ labelError(row) }}</div>
          <div v-else class="upload-sub">登録名：{{ row.contentLabel.trim() || '資料内容' }}-顧客名{{ row.name.includes('.') ? row.name.slice(row.name.lastIndexOf('.')).toLowerCase() : '' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="分類" width="140">
        <template #default="{ row }">
          <el-select v-model="row.category" size="small" :disabled="row.status === 'uploading' || row.status === 'success'">
            <el-option v-for="option in DOCUMENT_CATEGORY_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column v-if="checklistItems?.length" label="必要資料（任意）" width="150">
        <template #default="{ row }">
          <el-select v-model="row.checklistItem" size="small" clearable placeholder="関連付けない"
                     :disabled="row.status === 'uploading' || row.status === 'success'">
            <el-option v-for="item in checklistItems" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="状態" min-width="170">
        <template #default="{ row }">
          <el-tag size="small" :type="statusLabel[row.status].type">{{ statusLabel[row.status].text }}</el-tag>
          <el-progress v-if="row.status === 'uploading'" :percentage="row.progress" :stroke-width="6" class="upload-progress" />
          <div v-if="row.error" class="upload-error" role="alert">{{ row.error }}</div>
        </template>
      </el-table-column>
      <el-table-column label="" width="110" align="right">
        <template #default="{ row }">
          <el-button v-if="isRetryable(row, policy)" link type="primary" size="small" :disabled="running" @click="retryOne(row.key)">再試行</el-button>
          <el-button v-if="row.status !== 'uploading' && row.status !== 'success'" link size="small" :disabled="running" @click="remove(row.key)">外す</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="queue.length" class="upload-actions">
      <el-button type="primary" :loading="running" :disabled="!canStart" @click="start">
        登録を開始（{{ summary.waiting }} 件）
      </el-button>
      <el-button :disabled="running || !retryable.length" @click="retryFailed">失敗したファイルだけ再試行（{{ retryable.length }} 件）</el-button>
      <el-button text :disabled="running || !summary.success" @click="clearFinished">成功分を一覧から消す</el-button>
    </div>
  </div>
</template>

<style scoped>
.upload-queue {
  display: grid;
  gap: 10px;
}

.upload-drop {
  display: grid;
  gap: 4px;
  justify-items: center;
  padding: 18px 12px;
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-regular);
  text-align: center;
  cursor: pointer;
}

.upload-drop span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.upload-drop.is-dragging {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.upload-drop.is-disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.upload-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.upload-default {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.upload-summary {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.upload-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.is-label-error :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}

.upload-progress {
  margin-top: 4px;
}

.upload-error {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-color-danger);
}

.upload-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.upload-actions .el-button + .el-button {
  margin-left: 0;
}
</style>
