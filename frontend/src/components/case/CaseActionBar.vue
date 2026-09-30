<script setup lang="ts">
// 案件ワークスペースの Action Bar。独立ページは作らず Dialog / Drawer で完結させる。
// 権限は後端（BusinessAccessPolicy）が判定し、403 の場合はメッセージを表示するだけ。
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  completeCaseNextAction,
  endCaseWaiting,
  listCaseDocuments,
  receiveCaseChecklistItem,
  recordCasePaymentNote,
  setCaseNextAction,
  startCaseWaiting,
} from '../../api/cases'
import { createDocument } from '../../api/documents'
import RemoteStaffSelect from '../RemoteStaffSelect.vue'
import ResponsiveActionBar from '../layout/ResponsiveActionBar.vue'
import type { ActionItem } from '../layout/actions'
import http from '../../services/http'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'
import { CASE_WAITING_REASON_OPTIONS, DOCUMENT_CATEGORY_OPTIONS } from '../../types/api'
import type { DocumentCategory } from '../../types/api'
import type { Case, CaseChecklistItem, Document } from '../../types/api'

const props = defineProps<{
  caseDetail: Case
  checklistItems: CaseChecklistItem[]
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'record'): void
  (e: 'change-status', status: string): void
}>()

const auth = useAuthStore()
const caseId = computed(() => props.caseDetail.id)
const isWaiting = computed(() => props.caseDetail.work_status === 'waiting')
const isCompleted = computed(() => props.caseDetail.status === 'completed')
const isClosed = computed(() => ['completed', 'withdrawn', 'rejected'].includes(props.caseDetail.status))
const nextActionOpen = computed(() => props.caseDetail.next_action_state === 'open')
const pendingItems = computed(() => props.checklistItems.filter((item) => !item.is_completed))

const errorMessage = (error: unknown, fallback: string) => {
  const response = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
  if (response?.status === 403) return '権限がありません（担当外の案件は変更できません）。'
  const data = response?.data
  if (data && typeof data.detail === 'string') return data.detail
  if (data) {
    const first = Object.values(data)[0]
    if (Array.isArray(first) && typeof first[0] === 'string') return first[0]
  }
  return fallback
}

const run = async (action: () => Promise<unknown>, success: string, fallback: string) => {
  try {
    await action()
    ElMessage.success(success)
    emit('refresh')
    return true
  } catch (error) {
    ElMessage.error(errorMessage(error, fallback))
    return false
  }
}

// --- 次の対応 ---------------------------------------------------------------
const nextActionVisible = ref(false)
const nextActionSubmitting = ref(false)
const nextActionForm = reactive({ next_action: '', next_action_due_at: '' as string | null, assignee: null as number | null, blocked_reason: '' })
const openNextAction = () => {
  const c = props.caseDetail
  nextActionForm.next_action = nextActionOpen.value ? c.next_action : ''
  nextActionForm.next_action_due_at = nextActionOpen.value ? c.next_action_due_at : null
  nextActionForm.assignee = (nextActionOpen.value ? c.next_action_assignee : null) ?? auth.user?.employee_id ?? null
  nextActionForm.blocked_reason = nextActionOpen.value ? c.next_action_blocked_reason || '' : ''
  nextActionVisible.value = true
}
const submitNextAction = async () => {
  nextActionSubmitting.value = true
  const ok = await run(
    () => setCaseNextAction(caseId.value, { ...nextActionForm, next_action_due_at: nextActionForm.next_action_due_at || null }),
    '次の対応を設定しました。',
    '次の対応を設定できませんでした。',
  )
  nextActionSubmitting.value = false
  if (ok) nextActionVisible.value = false
}
const completeNextAction = async () => {
  try {
    await ElMessageBox.confirm(`「${props.caseDetail.next_action}」を完了にしますか？`, '次の対応を完了', { type: 'info' })
  } catch {
    return
  }
  await run(() => completeCaseNextAction(caseId.value), '次の対応を完了しました。', '完了にできませんでした。')
}

// --- 待機 -------------------------------------------------------------------
const waitingVisible = ref(false)
const waitingSubmitting = ref(false)
const waitingForm = reactive({ waiting_reason: 'customer_documents', waiting_until: null as string | null, waiting_note: '' })
const openWaiting = () => {
  waitingForm.waiting_reason = 'customer_documents'
  waitingForm.waiting_until = null
  waitingForm.waiting_note = ''
  waitingVisible.value = true
}
const submitWaiting = async () => {
  waitingSubmitting.value = true
  const ok = await run(() => startCaseWaiting(caseId.value, { ...waitingForm }), '待機にしました。', '待機にできませんでした。')
  waitingSubmitting.value = false
  if (ok) waitingVisible.value = false
}
const endWaiting = async () => {
  try {
    await ElMessageBox.confirm('待機を解除して対応中に戻しますか？', '待機解除', { type: 'info' })
  } catch {
    return
  }
  await run(() => endCaseWaiting(caseId.value), '待機を解除しました。', '待機を解除できませんでした。')
}

// --- 資料受領 ----------------------------------------------------------------
const receiveDrawerVisible = ref(false)
const receiveDialogVisible = ref(false)
const receiveSubmitting = ref(false)
const receiveTarget = ref<CaseChecklistItem | null>(null)
const receiveForm = reactive({ received_on: '' as string | null, document: null as number | null, complete: true, note: '' })
const caseDocuments = ref<Document[]>([])
const documentsLoading = ref(false)
const documentsError = ref('')
const loadDocuments = async () => {
  documentsLoading.value = true
  documentsError.value = ''
  try {
    caseDocuments.value = (await listCaseDocuments(caseId.value)).results
  } catch (error) {
    documentsError.value = errorMessage(error, 'ファイル一覧を取得できませんでした。')
  } finally {
    documentsLoading.value = false
  }
}
const openReceiveDrawer = async () => {
  receiveDrawerVisible.value = true
  await loadDocuments()
}
const openReceive = (item: CaseChecklistItem) => {
  receiveTarget.value = item
  receiveForm.received_on = new Date().toISOString().slice(0, 10)
  receiveForm.document = item.document ?? null
  receiveForm.complete = true
  receiveForm.note = ''
  receiveDialogVisible.value = true
}
const submitReceive = async () => {
  if (!receiveTarget.value) return
  receiveSubmitting.value = true
  const ok = await run(
    () => receiveCaseChecklistItem(receiveTarget.value!.id, { ...receiveForm }),
    '資料受領を記録しました。',
    '資料受領を記録できませんでした。',
  )
  receiveSubmitting.value = false
  if (ok) receiveDialogVisible.value = false
}

// --- ファイル ---------------------------------------------------------------
const filesDrawerVisible = ref(false)
const uploadForm = reactive({ title: '', file: null as File | null, category: 'other' as DocumentCategory, checklist_item: null as number | null })
const uploading = ref(false)
const apiBase = (http.defaults.baseURL || '/api/').replace(/\/$/, '')
const downloadUrl = (doc: Document) => `${apiBase}/documents/${doc.id}/download/`
const previewUrl = (doc: Document) => `${apiBase}/documents/${doc.id}/preview/`
const openFiles = async () => {
  filesDrawerVisible.value = true
  await loadDocuments()
}
const onFileSelected = (event: Event) => {
  const input = event.target as HTMLInputElement
  uploadForm.file = input.files?.[0] ?? null
  if (uploadForm.file && !uploadForm.title) uploadForm.title = uploadForm.file.name
}
const submitUpload = async () => {
  if (!uploadForm.file || !uploadForm.title.trim()) {
    ElMessage.warning('ファイルとタイトルを指定してください。')
    return
  }
  uploading.value = true
  const ok = await run(
    () => createDocument({
      case: caseId.value, title: uploadForm.title.trim(), file: uploadForm.file,
      category: uploadForm.category, checklist_item: uploadForm.checklist_item,
    }),
    'ファイルを登録しました。',
    'ファイルを登録できませんでした。',
  )
  uploading.value = false
  if (ok) {
    uploadForm.title = ''
    uploadForm.file = null
    uploadForm.checklist_item = null
    await loadDocuments()
  }
}

// --- 入金（案件経過への記録のみ。会計データは会計モジュールで登録） ----------------------
const paymentVisible = ref(false)
const paymentSubmitting = ref(false)
const paymentForm = reactive({ amount: '', received_on: '' as string | null, reference: '', note: '' })
const canOpenVouchers = computed(() => auth.can('accounting.use_voucher'))
const openPayment = () => {
  paymentForm.amount = ''
  paymentForm.received_on = new Date().toISOString().slice(0, 10)
  paymentForm.reference = ''
  paymentForm.note = ''
  paymentVisible.value = true
}
const submitPayment = async () => {
  paymentSubmitting.value = true
  const ok = await run(() => recordCasePaymentNote(caseId.value, { ...paymentForm }), '入金を案件経過に記録しました。', '入金を記録できませんでした。')
  paymentSubmitting.value = false
  if (ok) paymentVisible.value = false
}

// --- 操作列（広い画面は全部ボタン、640px 未満は主な操作だけボタンで残りは「その他」） ---
const barActions = computed<ActionItem[]>(() => [
  { key: 'record', label: '対応記録', collapse: 'never', onClick: () => emit('record') },
  { key: 'receive', label: '資料受領', disabled: !pendingItems.value.length && !props.checklistItems.length, onClick: openReceiveDrawer },
  { key: 'files', label: 'ファイル', onClick: openFiles },
  { key: 'payment', label: '入金', onClick: openPayment },
  { key: 'next', label: nextActionOpen.value ? '次の対応を変更' : '次の対応', collapse: 'never', onClick: openNextAction },
  { key: 'next-done', label: '次の対応を完了', type: 'success', plain: true, hidden: !nextActionOpen.value, onClick: completeNextAction },
  { key: 'wait', label: '待機', hidden: isWaiting.value, disabled: isClosed.value, onClick: openWaiting },
  { key: 'wait-end', label: '待機解除', type: 'warning', plain: true, hidden: !isWaiting.value, onClick: endWaiting },
  { key: 'complete', label: '完了', type: 'primary', plain: true, hidden: isCompleted.value, onClick: () => emit('change-status', 'completed') },
  { key: 'reopen', label: '再開', plain: true, hidden: !isCompleted.value, onClick: () => emit('change-status', 'collecting_documents') },
])
</script>

<template>
  <ResponsiveActionBar class="case-action-bar" :actions="barActions" label="案件の操作" />

  <div v-if="isWaiting || nextActionOpen" class="case-work-state">
    <el-tag v-if="isWaiting" type="warning" effect="light">
      待機中：{{ caseDetail.waiting_reason_display }}（{{ caseDetail.waiting_days ?? 0 }}日経過<template v-if="caseDetail.waiting_until">・予定 {{ formatDate(caseDetail.waiting_until) }}</template>）
    </el-tag>
    <span v-if="nextActionOpen" class="case-work-next">
      次の対応：{{ caseDetail.next_action }}
      <template v-if="caseDetail.next_action_due_at">（期限 {{ formatDate(caseDetail.next_action_due_at) }}）</template>
      <template v-if="caseDetail.next_action_assignee_name">／担当 {{ caseDetail.next_action_assignee_name }}</template>
      <el-tag v-if="caseDetail.next_action_blocked_reason" size="small" type="danger" effect="plain">阻害：{{ caseDetail.next_action_blocked_reason }}</el-tag>
    </span>
  </div>

  <el-dialog v-model="nextActionVisible" title="次の対応" width="480px">
    <el-form label-position="top">
      <el-form-item label="内容" required>
        <el-input v-model="nextActionForm.next_action" type="textarea" :rows="2" maxlength="500" show-word-limit />
      </el-form-item>
      <el-form-item label="期限">
        <el-date-picker v-model="nextActionForm.next_action_due_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="担当者">
        <RemoteStaffSelect v-model="nextActionForm.assignee" />
        <div class="field-hint">案件を閲覧できる担当者だけを指定できます。</div>
      </el-form-item>
      <el-form-item label="阻害要因（任意）">
        <el-input v-model="nextActionForm.blocked_reason" placeholder="例：会社からの書類待ち" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="nextActionVisible = false">キャンセル</el-button>
      <el-button type="primary" :loading="nextActionSubmitting" @click="submitNextAction">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="waitingVisible" title="待機にする" width="440px">
    <el-form label-position="top">
      <el-form-item label="理由" required>
        <el-select v-model="waitingForm.waiting_reason" style="width: 100%">
          <el-option v-for="option in CASE_WAITING_REASON_OPTIONS" :key="option.value" :value="option.value" :label="option.label" />
        </el-select>
      </el-form-item>
      <el-form-item label="予定終了日">
        <el-date-picker v-model="waitingForm.waiting_until" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="メモ">
        <el-input v-model="waitingForm.waiting_note" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="waitingVisible = false">キャンセル</el-button>
      <el-button type="primary" :loading="waitingSubmitting" @click="submitWaiting">待機にする</el-button>
    </template>
  </el-dialog>

  <el-drawer v-model="receiveDrawerVisible" title="資料受領" size="520px">
    <p class="drawer-hint">受領した資料を選び、必要なら登録済みのファイルと関連付けます。</p>
    <el-empty v-if="!checklistItems.length" description="必要資料がありません" />
    <el-table v-else :data="checklistItems" size="small">
      <el-table-column prop="name" label="資料" min-width="160" />
      <el-table-column label="状態" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.is_completed" type="success" size="small">完了</el-tag>
          <el-tag v-else-if="row.received_at" type="warning" size="small">受領 {{ formatDate(row.received_at) }}</el-tag>
          <span v-else>未受領</span>
        </template>
      </el-table-column>
      <el-table-column label="ファイル" min-width="120">
        <template #default="{ row }">{{ row.document_title || '-' }}</template>
      </el-table-column>
      <el-table-column width="80">
        <template #default="{ row }">
          <el-button size="small" type="primary" text @click="openReceive(row)">受領</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-drawer>

  <el-dialog v-model="receiveDialogVisible" :title="`資料受領：${receiveTarget?.name ?? ''}`" width="460px">
    <el-form label-position="top">
      <el-form-item label="受領日">
        <el-date-picker v-model="receiveForm.received_on" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="関連ファイル（この案件の登録済みファイル）">
        <el-alert v-if="documentsError" :title="documentsError" type="error" :closable="false" />
        <el-select v-else v-model="receiveForm.document" clearable :loading="documentsLoading" placeholder="選択しない" style="width: 100%">
          <el-option v-for="doc in caseDocuments" :key="doc.id" :value="doc.id" :label="doc.title" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="receiveForm.complete">この項目を完了にする</el-checkbox>
      </el-form-item>
      <el-form-item label="備考">
        <el-input v-model="receiveForm.note" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="receiveDialogVisible = false">キャンセル</el-button>
      <el-button type="primary" :loading="receiveSubmitting" @click="submitReceive">記録</el-button>
    </template>
  </el-dialog>

  <el-drawer v-model="filesDrawerVisible" title="ファイル" size="560px">
    <el-alert v-if="documentsError" :title="documentsError" type="error" :closable="false" class="drawer-alert" />
    <el-table v-loading="documentsLoading" :data="caseDocuments" size="small" empty-text="ファイルはまだありません">
      <el-table-column label="タイトル" min-width="150">
        <template #default="{ row }">{{ row.title }}<div class="drawer-hint">{{ row.category_display }}</div></template>
      </el-table-column>
      <el-table-column prop="file_name" label="ファイル名" min-width="150" show-overflow-tooltip />
      <el-table-column label="" width="170">
        <template #default="{ row }">
          <template v-if="row.file_url">
            <el-link :href="previewUrl(row)" target="_blank" rel="noopener" type="primary">プレビュー</el-link>
            <el-divider direction="vertical" />
            <el-link :href="downloadUrl(row)" type="primary">ダウンロード</el-link>
          </template>
        </template>
      </el-table-column>
    </el-table>
    <el-divider />
    <el-form label-position="top" class="upload-form">
      <el-form-item label="ファイルを追加">
        <input type="file" @change="onFileSelected" />
      </el-form-item>
      <el-form-item label="タイトル">
        <el-input v-model="uploadForm.title" />
      </el-form-item>
      <el-form-item label="分類">
        <el-select v-model="uploadForm.category" style="width: 100%">
          <el-option v-for="option in DOCUMENT_CATEGORY_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="必要資料に関連付け（任意）">
        <el-select v-model="uploadForm.checklist_item" clearable placeholder="関連付けない" style="width: 100%">
          <el-option v-for="item in checklistItems" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <div class="field-hint">受領日の記録は「資料受領」で行います。PDF・画像・Office 文書など（20MB まで）。</div>
      </el-form-item>
      <el-button type="primary" :loading="uploading" @click="submitUpload">登録</el-button>
    </el-form>
  </el-drawer>

  <el-dialog v-model="paymentVisible" title="入金" width="460px">
    <el-alert
      type="info"
      :closable="false"
      title="ここでは案件の経過に「入金を確認した」ことだけを記録します。会計データ（請求書・領収書・収入）は会計モジュールで登録してください。"
      class="drawer-alert"
    />
    <p v-if="canOpenVouchers"><router-link class="text-link" to="/vouchers/invoices">請求書・領収書を開く</router-link></p>
    <el-form label-position="top">
      <el-form-item label="入金日">
        <el-date-picker v-model="paymentForm.received_on" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
      </el-form-item>
      <el-form-item label="金額（円、任意）">
        <el-input v-model="paymentForm.amount" inputmode="numeric" />
      </el-form-item>
      <el-form-item label="会計側の参照（任意）">
        <el-input v-model="paymentForm.reference" placeholder="例：請求書番号" />
      </el-form-item>
      <el-form-item label="備考">
        <el-input v-model="paymentForm.note" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="paymentVisible = false">キャンセル</el-button>
      <el-button type="primary" :loading="paymentSubmitting" @click="submitPayment">記録</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.case-action-bar {
  margin: 12px 0 4px;
}

.case-work-state {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  margin: 4px 0 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.case-work-next {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.drawer-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.drawer-alert {
  margin-bottom: 12px;
}

.upload-form {
  max-width: 420px;
}
</style>
