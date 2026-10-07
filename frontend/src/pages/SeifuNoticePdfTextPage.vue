<script setup lang="ts">
// 清風合格通知書（P5・固定テンプレート）。入力は宛名・許可番号・通知日だけ。
// 通知書番号・コース年数・在籍期間・座標・字体・背景はサーバーが決める（画面から変更できない）。
// 「PDF作成」はサーバーで作成・検証・保存まで成功したときだけ生成記録を返し、そのときだけダウンロードを出す。
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createSeifuNoticeRecord,
  deleteSeifuNoticeRecord,
  downloadSeifuNoticeGeneration,
  generateSeifuNoticePdf,
  getSeifuNoticeTemplateInfo,
  listSeifuNoticeRecords,
  previewSeifuNoticeRecordPdf,
  updateSeifuNoticeRecord,
} from '../api/accounting'
import type {
  SeifuNoticeGeneration,
  SeifuNoticePdfRecord,
  SeifuNoticeRecordPayload,
  SeifuNoticeTemplateInfo,
} from '../types/accounting'
import { formatDateTime } from '../utils/date'
import {
  RECIPIENT_NAME_MAX_LENGTH,
  defaultSeifuTitle,
  deriveNoticeNumber,
  formatFileSize,
  localToday,
  newRequestId,
  normalizePermitNumber,
  seifuErrorMessage,
  validateSeifuForm,
} from '../utils/seifuNotice'
import './accounting/accounting.css'

const records = ref<SeifuNoticePdfRecord[]>([])
const total = ref(0)
const listLoading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const generating = ref(false)
const downloadingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)
const duplicatingId = ref<number | null>(null)
const drawerVisible = ref(false)
const templateInfo = ref<SeifuNoticeTemplateInfo | null>(null)
const editingId = ref<number | null>(null)
const previewUrl = ref('')
const formError = ref('')
// 直近に成功した生成（この記録の）。成功したときだけダウンロードを表示する
const lastGeneration = ref<SeifuNoticeGeneration | null>(null)
// 1 回の「PDF作成」操作の ID。失敗して再試行するときは新しい ID にする
let pendingRequestId: string | null = null

const query = reactive({ page: 1, page_size: 20, search: '' })
const form = reactive<SeifuNoticeRecordPayload>({
  title: '', status: 'draft', recipient_name: '', permit_number: '', issue_date: '', note: '',
})

const noticeNumber = computed(() => deriveNoticeNumber(form.permit_number, templateInfo.value?.notice_number_suffix || 'A') || '-')
const ready = computed(() => Boolean(templateInfo.value?.font_available && !templateInfo.value?.template_error))
const busy = computed(() => saving.value || previewing.value || generating.value)
const templateStatus = computed(() => {
  if (!templateInfo.value) return { type: 'info' as const, text: '確認中' }
  if (templateInfo.value.template_error) return { type: 'danger' as const, text: templateInfo.value.template_error }
  if (!templateInfo.value.font_available) return { type: 'danger' as const, text: templateInfo.value.font_error || 'MS Mincho がありません' }
  return { type: 'success' as const, text: 'テンプレート・MS Mincho 確認済み' }
})

const revokePreview = () => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
}

const loadRecords = async () => {
  listLoading.value = true
  try {
    const data = await listSeifuNoticeRecords(query)
    records.value = data.results
    total.value = data.count
  } catch (error) {
    ElMessage.error(await seifuErrorMessage(error, '記録一覧の取得に失敗しました。'))
  } finally {
    listLoading.value = false
  }
}

const loadTemplate = async () => {
  try {
    templateInfo.value = await getSeifuNoticeTemplateInfo()
  } catch (error) {
    ElMessage.error(await seifuErrorMessage(error, 'テンプレート情報の取得に失敗しました。'))
  }
}

const resetForm = () => {
  editingId.value = null
  Object.assign(form, { title: '', status: 'draft', recipient_name: '', permit_number: '', issue_date: localToday(), note: '' })
  formError.value = ''
  lastGeneration.value = null
  pendingRequestId = null
  revokePreview()
}

const openCreate = () => {
  resetForm()
  drawerVisible.value = true
}

const openEdit = async (row: SeifuNoticePdfRecord) => {
  resetForm()
  editingId.value = row.id
  Object.assign(form, {
    title: row.title, status: row.status, recipient_name: row.recipient_name || '',
    permit_number: row.permit_number || '', issue_date: row.issue_date || '', note: row.note || '',
  })
  lastGeneration.value = row.latest_generation
  drawerVisible.value = true
  if (!row.is_legacy && ready.value) await loadRecordPreview(row.id)
}

const buildPayload = (): SeifuNoticeRecordPayload => ({
  title: form.title.trim() || defaultSeifuTitle(form.recipient_name),
  status: form.status,
  recipient_name: form.recipient_name.trim(),
  permit_number: normalizePermitNumber(form.permit_number),
  issue_date: form.issue_date,
  note: form.note || '',
})

// 保存（入力は失敗しても消さない）。成功すると記録 ID を返す
const saveRecord = async (notify = true): Promise<number | null> => {
  formError.value = validateSeifuForm(form)
  if (formError.value) return null
  saving.value = true
  try {
    const saved = editingId.value
      ? await updateSeifuNoticeRecord(editingId.value, buildPayload())
      : await createSeifuNoticeRecord(buildPayload())
    editingId.value = saved.id
    form.title = saved.title
    form.permit_number = saved.permit_number || form.permit_number
    if (notify) ElMessage.success('保存しました。')
    await loadRecords()
    return saved.id
  } catch (error) {
    formError.value = await seifuErrorMessage(error, '保存に失敗しました。')
    return null
  } finally {
    saving.value = false
  }
}

const loadRecordPreview = async (id: number) => {
  previewing.value = true
  try {
    const blob = await previewSeifuNoticeRecordPdf(id)
    revokePreview()
    previewUrl.value = URL.createObjectURL(blob)
  } catch (error) {
    formError.value = await seifuErrorMessage(error, 'プレビューの作成に失敗しました。')
  } finally {
    previewing.value = false
  }
}

const previewCurrent = async () => {
  const id = await saveRecord(false)
  if (id) await loadRecordPreview(id)
}

const extractFilename = (value?: string) => {
  const encoded = value?.match(/filename\*=UTF-8''([^;]+)/)
  if (encoded?.[1]) return decodeURIComponent(encoded[1])
  return '清風合格通知書.pdf'
}

const saveBlob = (blob: Blob, disposition?: string) => {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = extractFilename(disposition)
  link.click()
  URL.revokeObjectURL(url)
}

const downloadGeneration = async (generation: SeifuNoticeGeneration) => {
  downloadingId.value = generation.id
  try {
    const result = await downloadSeifuNoticeGeneration(generation.id)
    saveBlob(result.blob, result.contentDisposition)
  } catch (error) {
    ElMessage.error({ message: await seifuErrorMessage(error, 'ダウンロードに失敗しました。'), duration: 6000 })
  } finally {
    downloadingId.value = null
  }
}

// PDF 作成：保存 → サーバーで作成・検証・保存 → 成功時だけダウンロードを表示
const generateCurrent = async () => {
  if (generating.value) return
  const id = await saveRecord(false)
  if (!id) return
  generating.value = true
  pendingRequestId ||= newRequestId()
  try {
    const generation = await generateSeifuNoticePdf(id, pendingRequestId)
    lastGeneration.value = generation
    pendingRequestId = null
    ElMessage.success('PDF を作成しました。「ダウンロード」から保存できます。')
    await loadRecords()
  } catch (error) {
    // 入力はそのまま。次の「PDF作成」は新しい操作として送る
    pendingRequestId = null
    formError.value = await seifuErrorMessage(error, 'PDF の作成に失敗しました。もう一度お試しください。')
  } finally {
    generating.value = false
  }
}

const duplicateRecord = async (row: SeifuNoticePdfRecord) => {
  if (row.is_legacy) return ElMessage.warning('旧形式の記録はコピーできません。新規作成してください。')
  duplicatingId.value = row.id
  try {
    await createSeifuNoticeRecord({
      title: `${row.title} - コピー`, status: 'draft', recipient_name: row.recipient_name || '',
      permit_number: row.permit_number || '', issue_date: row.issue_date || '', note: row.note || '',
    })
    ElMessage.success('コピーしました。')
    await loadRecords()
  } catch (error) {
    ElMessage.error(await seifuErrorMessage(error, 'コピーに失敗しました。'))
  } finally {
    duplicatingId.value = null
  }
}

const deleteRecord = async (row: SeifuNoticePdfRecord) => {
  try {
    await ElMessageBox.confirm(`「${row.title}」を削除しますか？（作成済みの PDF の記録は残ります）`, '削除確認', { type: 'warning' })
  } catch { return }
  deletingId.value = row.id
  try {
    await deleteSeifuNoticeRecord(row.id)
    ElMessage.success('削除しました。')
    await loadRecords()
  } catch (error) {
    ElMessage.error(await seifuErrorMessage(error, '削除に失敗しました。'))
  } finally {
    deletingId.value = null
  }
}

onMounted(async () => {
  await Promise.all([loadRecords(), loadTemplate()])
})
onBeforeUnmount(revokePreview)
</script>

<template>
  <section class="accounting-page seifu-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>清風合格通知書</h1>
          <p>宛名・許可番号・通知日を入力し、承認済みの固定レイアウトで PDF を作成します。</p>
        </div>
        <div class="accounting-toolbar">
          <el-tag :type="templateStatus.type">{{ templateStatus.text }}</el-tag>
          <el-button type="primary" :disabled="!ready" @click="openCreate">新規作成</el-button>
        </div>
      </div>
    </div>

    <el-alert
      v-if="templateInfo"
      :title="`${templateInfo.template_name}（コース年数 ${templateInfo.course_years} 年・在籍期間 ${templateInfo.enrollment_period} は固定）`"
      type="info"
      :closable="false"
      show-icon
      class="template-alert"
    />

    <el-card class="accounting-card" shadow="never">
      <div class="list-toolbar">
        <el-input v-model="query.search" clearable placeholder="記録名 / 備考" @keyup.enter="loadRecords" />
        <el-button @click="loadRecords">検索</el-button>
      </div>
      <el-table v-loading="listLoading" :data="records" row-key="id">
        <el-table-column label="記録名" min-width="190">
          <template #default="{ row }">
            {{ row.title }}
            <el-tag v-if="row.is_legacy" size="small" type="info">旧形式</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="recipient_name" label="宛名" min-width="130" />
        <el-table-column prop="permit_number" label="許可番号" min-width="110" />
        <el-table-column prop="notice_number" label="通知書番号" min-width="120" />
        <el-table-column prop="issue_date" label="通知日" width="110" />
        <el-table-column label="作成済み PDF" min-width="170">
          <template #default="{ row }">
            <el-button v-if="row.latest_generation" link type="primary" :loading="downloadingId === row.latest_generation.id"
                       @click="downloadGeneration(row.latest_generation)">
              ダウンロード（{{ formatDateTime(row.latest_generation.created_at) }}）
            </el-button>
            <span v-else class="muted">未作成</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="105" fixed="right">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button text type="primary">操作 <el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openEdit(row)">編集・PDF作成</el-dropdown-item>
                  <el-dropdown-item :disabled="duplicatingId === row.id || row.is_legacy" @click="duplicateRecord(row)">コピー</el-dropdown-item>
                  <el-dropdown-item divided :disabled="deletingId === row.id" @click="deleteRecord(row)">削除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="query.page" :page-size="query.page_size" :total="total" layout="prev, pager, next, total" @current-change="loadRecords" />
    </el-card>

    <el-drawer v-model="drawerVisible" :title="editingId ? '清風合格通知書を編集' : '清風合格通知書を作成'" size="min(1100px, 96vw)"
               :close-on-press-escape="false">
      <div class="drawer-grid">
        <el-form label-position="top" class="notice-form" @submit.prevent>
          <el-alert v-if="formError" :title="formError" type="error" show-icon :closable="false" class="form-alert" role="alert" />
          <el-form-item label="宛名" required>
            <el-input v-model="form.recipient_name" :maxlength="RECIPIENT_NAME_MAX_LENGTH" show-word-limit
                      placeholder="通知書に印字する氏名（「様」はテンプレートに印字済み）" />
          </el-form-item>
          <el-form-item label="許可番号" required>
            <el-input v-model="form.permit_number" maxlength="12" placeholder="例：99A0000"
                      @blur="form.permit_number = normalizePermitNumber(form.permit_number)" />
          </el-form-item>
          <el-form-item label="通知書番号（許可番号から自動）">
            <el-input :model-value="noticeNumber" disabled />
          </el-form-item>
          <el-form-item label="通知日" required>
            <el-date-picker v-model="form.issue_date" type="date" value-format="YYYY-MM-DD" format="YYYY/MM/DD" :clearable="false" />
          </el-form-item>
          <el-form-item label="コース（固定）">
            <el-input :model-value="`${templateInfo?.course_years || '2'}年コース`" disabled />
          </el-form-item>
          <el-form-item label="在籍期間（固定）">
            <el-input :model-value="templateInfo?.enrollment_period" disabled />
          </el-form-item>
          <el-form-item label="記録名">
            <el-input v-model="form.title" placeholder="空欄なら宛名から自動設定" />
          </el-form-item>
          <el-form-item label="状態">
            <el-select v-model="form.status"><el-option label="下書き" value="draft" /><el-option label="完了" value="completed" /></el-select>
          </el-form-item>
          <el-form-item label="備考（社内用・PDF には印字されません）"><el-input v-model="form.note" type="textarea" :rows="3" /></el-form-item>
          <div v-if="lastGeneration" class="generation-result" data-testid="seifu-generation">
            <div>
              <strong>作成済み PDF</strong>
              <span class="muted">{{ formatDateTime(lastGeneration.created_at) }}・{{ formatFileSize(lastGeneration.file_size) }}・通知書番号 {{ lastGeneration.notice_number }}</span>
            </div>
            <el-button type="success" :loading="downloadingId === lastGeneration.id" @click="downloadGeneration(lastGeneration)">ダウンロード</el-button>
          </div>
        </el-form>
        <div class="preview-panel" v-loading="previewing">
          <iframe v-if="previewUrl" :src="previewUrl" title="清風合格通知書プレビュー" />
          <el-empty v-else description="「プレビュー」で完成イメージを確認できます（保存・記録はしません）" />
        </div>
      </div>
      <template #footer>
        <el-button @click="drawerVisible = false">閉じる</el-button>
        <el-button :loading="saving" :disabled="busy && !saving" @click="saveRecord()">保存</el-button>
        <el-button :loading="previewing" :disabled="!ready || (busy && !previewing)" @click="previewCurrent">プレビュー</el-button>
        <el-button type="primary" :loading="generating" :disabled="!ready || (busy && !generating)" @click="generateCurrent">PDF作成</el-button>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.template-alert { margin-bottom: 16px; }
.list-toolbar { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 14px; }
.list-toolbar .el-input { width: min(320px, 100%); }
.el-pagination { justify-content: flex-end; margin-top: 16px; }
.drawer-grid { display: grid; grid-template-columns: minmax(300px, 380px) minmax(0, 1fr); gap: 20px; }
.notice-form { min-width: 0; }
.form-alert { margin-bottom: 12px; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 6px; }
.generation-result { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px;
  border: 1px solid var(--el-color-success-light-5); border-radius: 6px; background: var(--el-color-success-light-9); }
.preview-panel { min-height: 680px; border: 1px solid var(--el-border-color); border-radius: 8px; overflow: hidden; background: #f5f7fa; }
.preview-panel iframe { display: block; width: 100%; height: 760px; border: 0; background: white; }
@media (max-width: 800px) {
  .drawer-grid { grid-template-columns: 1fr; }
  .preview-panel, .preview-panel iframe { min-height: 520px; height: 520px; }
}
</style>
