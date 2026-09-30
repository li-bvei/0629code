<script setup lang="ts">
// 書類管理：本システム内のファイルだけを扱う（Google Drive とは連携しない）。
// 閲覧・操作の範囲は後端が案件の権限で決める。ダウンロード・プレビューは受保護 API のみ。
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { archiveDocument, getDocumentHistory, listDocuments, restoreDocument, updateDocument } from '../api/documents'
import http from '../services/http'
import { DOCUMENT_CATEGORY_OPTIONS } from '../types/api'
import type { Document, DocumentReplacement } from '../types/api'
import { formatDateTime } from '../utils/date'
import TableRowActions from '../components/layout/TableRowActions.vue'
import type { ActionItem } from '../components/layout/actions'

const apiBase = (http.defaults.baseURL || '/api/').replace(/\/$/, '')
const downloadUrl = (doc: Document) => `${apiBase}/documents/${doc.id}/download/`
const previewUrl = (doc: Document) => `${apiBase}/documents/${doc.id}/preview/`

const loading = ref(false)
const errorMessage = ref('')
const documents = ref<Document[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filters = reactive({ category: '', archived: '' })

const errorText = (error: unknown, fallback: string) => {
  const response = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
  if (response?.status === 403) return 'この操作の権限がありません（担当外の案件）。'
  const data = response?.data
  if (data && typeof data.detail === 'string') return data.detail
  const first = data ? Object.values(data)[0] : null
  return Array.isArray(first) && typeof first[0] === 'string' ? first[0] : fallback
}

const fetchDocuments = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listDocuments({
      page,
      category: filters.category || undefined,
      archived: filters.archived || undefined,
    })
    documents.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = 'データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const checklistNames = (doc: Document) => (doc.checklist_items ?? []).map((item) => item.name).join('、')

const formatSize = (size: number | null) => {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const archive = async (doc: Document) => {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('アーカイブの理由（任意）。ファイルは削除されず、一覧の既定表示から外れます。', 'アーカイブ', {
      inputPlaceholder: '例：古い版', confirmButtonText: 'アーカイブ', cancelButtonText: 'キャンセル',
    })
    reason = result.value || ''
  } catch {
    return
  }
  try {
    await archiveDocument(doc.id, reason)
    ElMessage.success('アーカイブしました。')
    await fetchDocuments()
  } catch (error) {
    ElMessage.error(errorText(error, 'アーカイブできませんでした。'))
  }
}

const restore = async (doc: Document) => {
  try {
    await restoreDocument(doc.id)
    ElMessage.success('復元しました。')
    await fetchDocuments()
  } catch (error) {
    ElMessage.error(errorText(error, '復元できませんでした。'))
  }
}

// --- 差し替え（旧ファイルは削除せず履歴に残す） ---
const replaceVisible = ref(false)
const replaceTarget = ref<Document | null>(null)
const replaceForm = reactive({ file: null as File | null, reason: '' })
const replacing = ref(false)
const openReplace = (doc: Document) => {
  replaceTarget.value = doc
  replaceForm.file = null
  replaceForm.reason = ''
  replaceVisible.value = true
}
const submitReplace = async () => {
  if (!replaceTarget.value || !replaceForm.file) return ElMessage.warning('ファイルを選択してください。')
  replacing.value = true
  try {
    await updateDocument(replaceTarget.value.id, {
      case: replaceTarget.value.case, title: replaceTarget.value.title, file: replaceForm.file,
      replace_reason: replaceForm.reason, source: replaceTarget.value.source,
      is_visible_to_client: replaceTarget.value.is_visible_to_client,
    })
    ElMessage.success('差し替えました。')
    replaceVisible.value = false
    await fetchDocuments()
  } catch (error) {
    ElMessage.error(errorText(error, '差し替えできませんでした。'))
  } finally {
    replacing.value = false
  }
}

// --- 差し替え履歴 ---
const historyVisible = ref(false)
const history = ref<DocumentReplacement[]>([])
const openHistory = async (doc: Document) => {
  try {
    history.value = await getDocumentHistory(doc.id)
    historyVisible.value = true
  } catch (error) {
    ElMessage.error(errorText(error, '履歴を取得できませんでした。'))
  }
}

onMounted(() => {
  fetchDocuments()
})

// 行の操作：差し替えだけボタンで出し、履歴・アーカイブ／復元は「その他」へ（操作列の幅を抑える）
const rowActions = (doc: Document): ActionItem[] => [
  { key: 'replace', label: '差し替え', onClick: () => openReplace(doc) },
  { key: 'history', label: doc.replacement_count ? `履歴（${doc.replacement_count}）` : '履歴', onClick: () => openHistory(doc) },
  { key: 'archive', label: 'アーカイブ', hidden: doc.is_archived, onClick: () => archive(doc) },
  { key: 'restore', label: '復元', hidden: !doc.is_archived, onClick: () => restore(doc) },
]
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>書類管理</h1>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never">
      <div class="document-filters">
        <el-select v-model="filters.category" clearable placeholder="分類" class="document-filter" @change="fetchDocuments(1)">
          <el-option v-for="option in DOCUMENT_CATEGORY_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-select v-model="filters.archived" class="document-filter" @change="fetchDocuments(1)">
          <el-option label="通常のファイル" value="" />
          <el-option label="アーカイブ済みのみ" value="only" />
          <el-option label="すべて" value="all" />
        </el-select>
      </div>
      <el-table v-loading="loading" :data="documents" stripe>
        <el-table-column label="案件番号" min-width="150">
          <template #default="{ row }"><router-link class="text-link" :to="`/cases/${row.case}`">{{ row.case_number }}</router-link></template>
        </el-table-column>
        <el-table-column label="タイトル" min-width="180">
          <template #default="{ row }">
            {{ row.title }}
            <el-tag v-if="row.is_archived" size="small" type="info">アーカイブ</el-tag>
            <div v-if="row.checklist_items?.length" class="sub">必要資料：{{ checklistNames(row) }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="category_display" label="分類" width="120" />
        <el-table-column prop="file_name" label="元のファイル名" min-width="180" show-overflow-tooltip />
        <el-table-column label="サイズ" width="90">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column prop="uploaded_by_name" label="登録者" width="100" />
        <el-table-column label="更新日時" min-width="150">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="ファイル" width="170">
          <template #default="{ row }">
            <template v-if="row.file_url">
              <el-link :href="previewUrl(row)" target="_blank" rel="noopener" type="primary">プレビュー</el-link>
              <el-divider direction="vertical" />
              <el-link :href="downloadUrl(row)" type="primary">ダウンロード</el-link>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <TableRowActions :actions="rowActions(row)" />
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchDocuments"
        />
      </div>
    </el-card>

    <el-dialog v-model="replaceVisible" :title="`差し替え：${replaceTarget?.title ?? ''}`" width="440px">
      <p class="sub">差し替え前のファイルは削除されず、履歴に記録されます（画面から旧ファイルは開けません）。</p>
      <el-form label-position="top">
        <el-form-item label="新しいファイル">
          <input type="file" @change="(e: Event) => (replaceForm.file = (e.target as HTMLInputElement).files?.[0] ?? null)" />
        </el-form-item>
        <el-form-item label="理由（任意）">
          <el-input v-model="replaceForm.reason" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="replaceVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="replacing" @click="submitReplace">差し替え</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="historyVisible" title="差し替え履歴" width="640px">
      <el-table :data="history" size="small" empty-text="差し替えの履歴はありません">
        <el-table-column label="日時" width="160"><template #default="{ row }">{{ formatDateTime(row.replaced_at) }}</template></el-table-column>
        <el-table-column prop="previous_file_name" label="差し替え前のファイル" min-width="180" />
        <el-table-column label="サイズ" width="90"><template #default="{ row }">{{ formatSize(row.previous_size) }}</template></el-table-column>
        <el-table-column prop="replaced_by_name" label="実行者" width="100" />
        <el-table-column prop="reason" label="理由" min-width="120" />
      </el-table>
    </el-dialog>
  </section>
</template>

<style scoped>
.document-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.document-filter {
  width: 180px;
}

@media (max-width: 639px) {
  .document-filter {
    width: 100%;
  }
}

.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
