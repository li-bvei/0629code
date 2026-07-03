<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  createAccountingIncomeSource,
  deleteAccountingIncomeSource,
  listAccountingIncomeSources,
} from '../../api/accounting'
import type { AccountingListParams, IncomeSource, IncomeSourcePayload } from '../../types/accounting'
import { formatDate } from '../../utils/date'
import { createTimestamp, exportRowsToExcel } from '../../utils/exportExcel'
import './accounting.css'

interface BatchIncomeSourceRow {
  lineNumber: number
  source_date: string
  source_target: string
  amount: string
  note: string
  errors: string[]
}

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const incomeSources = ref<IncomeSource[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filters = ref<AccountingListParams>({
  search: '',
  start_date: null,
  end_date: null,
})
const addDialogVisible = ref(false)
const addFormRef = ref<FormInstance>()
const submitting = ref(false)
const addForm = ref<IncomeSourcePayload>({
  source_date: '',
  source_target: '',
  amount: '',
  note: '',
  is_exported: false,
})
const batchDialogVisible = ref(false)
const batchText = ref('')
const batchRows = ref<BatchIncomeSourceRow[]>([])
const batchSubmitting = ref(false)
const exporting = ref(false)
const summary = ref({
  count: 0,
  totalAmount: 0,
})

const rules: FormRules<IncomeSourcePayload> = {
  source_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  amount: [{ required: true, message: '金額を入力してください。', trigger: 'blur' }],
}

const formatCurrency = (value: number | string) => `¥ ${Number(value || 0).toLocaleString()}`
const formatYen = (value: number | string) => `${Number(value || 0).toLocaleString()}円`
const validBatchRows = computed(() => batchRows.value.filter((row) => !row.errors.length))
const invalidBatchRows = computed(() => batchRows.value.filter((row) => row.errors.length))

const isValidDate = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

const fetchIncomeSources = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listAccountingIncomeSources({ ...filters.value, page })
    incomeSources.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = '収入来源の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const clearFilters = () => {
  filters.value = {
    search: '',
    start_date: null,
    end_date: null,
  }
  fetchIncomeSources(1)
  refreshIncomeSourceSummary()
}

const fetchAllIncomeSourcesForExport = async () => {
  const rows: IncomeSource[] = []
  let page = 1

  while (true) {
    const data = await listAccountingIncomeSources({ ...filters.value, page })
    rows.push(...data.results)
    if (rows.length >= data.count || !data.results.length) break
    page += 1
  }

  return rows
}

const refreshIncomeSourceSummary = async () => {
  try {
    const rows = await fetchAllIncomeSourcesForExport()
    summary.value = {
      count: rows.length,
      totalAmount: rows.reduce((total, row) => total + Number(row.amount || 0), 0),
    }
  } catch {
    summary.value = {
      count: 0,
      totalAmount: 0,
    }
  }
}

const searchIncomeSources = () => {
  fetchIncomeSources(1)
  refreshIncomeSourceSummary()
}

const exportIncomeSources = async () => {
  exporting.value = true
  try {
    const rows = await fetchAllIncomeSourcesForExport()
    if (!rows.length) {
      ElMessage.warning('出力対象のデータがありません')
      return
    }

    exportRowsToExcel(
      rows.map((row) => ({
        日付: row.source_date,
        対象: row.source_target,
        金額: Number(row.amount || 0),
        備考: row.note,
      })),
      '収入来源',
      `収入来源_${createTimestamp()}.xlsx`,
    )
  } catch {
    ElMessage.error('Excel出力に失敗しました。')
  } finally {
    exporting.value = false
  }
}

const openAddDialog = () => {
  addForm.value = {
    source_date: '',
    source_target: '',
    amount: '',
    note: '',
    is_exported: false,
  }
  addFormRef.value?.clearValidate()
  addDialogVisible.value = true
}

const submitAddIncomeSource = async () => {
  if (!addFormRef.value) return
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createAccountingIncomeSource(addForm.value)
    ElMessage.success('収入来源を作成しました。')
    addDialogVisible.value = false
    await fetchIncomeSources(1)
    await refreshIncomeSourceSummary()
  } catch {
    ElMessage.error('収入来源の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const openBatchDialog = () => {
  batchText.value = ''
  batchRows.value = []
  batchDialogVisible.value = true
}

const parseBatchLine = (line: string, lineNumber: number): BatchIncomeSourceRow | null => {
  if (!line) return null

  const cells = line.includes('\t') ? line.split('\t') : line.split(',')
  const normalizedCells = cells.map((cell) => cell.trim())

  if (lineNumber === 1 && ['日期', '日付', 'source_date'].includes(normalizedCells[0])) {
    return null
  }

  const [sourceDate = '', sourceTarget = '', amount = '', note = ''] = normalizedCells
  const errors: string[] = []

  if (!sourceDate) {
    errors.push('日付が未入力です')
  } else if (!isValidDate(sourceDate)) {
    errors.push('日付形式が正しくありません')
  }
  if (!sourceTarget) {
    errors.push('対象が未入力です')
  }
  if (!amount) {
    errors.push('金額が未入力です')
  } else if (Number.isNaN(Number(amount))) {
    errors.push('金額は数字で入力してください')
  }

  return {
    lineNumber,
    source_date: sourceDate,
    source_target: sourceTarget,
    amount,
    note,
    errors,
  }
}

const previewBatch = () => {
  const rows = batchText.value
    .split(/\r?\n/)
    .map((line, index) => parseBatchLine(line.trim(), index + 1))
    .filter((row): row is BatchIncomeSourceRow => Boolean(row))

  batchRows.value = rows
  if (!rows.length) {
    ElMessage.warning('追加できる行がありません。')
    return
  }
  if (invalidBatchRows.value.length) {
    ElMessage.warning('エラーのある行があります。内容を確認してください。')
  }
}

const submitBatch = async () => {
  if (!batchRows.value.length) {
    previewBatch()
  }
  if (!batchRows.value.length) return
  if (invalidBatchRows.value.length) {
    ElMessage.warning('エラーのある行を修正してから追加してください。')
    return
  }

  batchSubmitting.value = true
  let successCount = 0
  let failedCount = 0

  for (const row of validBatchRows.value) {
    try {
      await createAccountingIncomeSource({
        source_date: row.source_date,
        source_target: row.source_target,
        amount: row.amount,
        note: row.note,
        is_exported: false,
      })
      successCount += 1
    } catch {
      failedCount += 1
    }
  }

  batchSubmitting.value = false
  ElMessage.success(`追加完了：成功 ${successCount} 件、失敗 ${failedCount} 件`)
  batchDialogVisible.value = false
  batchText.value = ''
  batchRows.value = []
  await fetchIncomeSources(1)
  await refreshIncomeSourceSummary()
}

const confirmDelete = async (incomeSource: IncomeSource) => {
  try {
    await ElMessageBox.confirm('この収入来源を削除します。よろしいですか？', '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingIncomeSource(incomeSource.id)
    ElMessage.success('収入来源を削除しました。')
    await fetchIncomeSources(currentPage.value)
    await refreshIncomeSourceSummary()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('収入来源の削除に失敗しました。')
    }
  }
}

onMounted(() => {
  fetchIncomeSources()
  refreshIncomeSourceSummary()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>収入来源</h1>
          <p>入金や資金来源を記録します</p>
        </div>
        <div class="accounting-toolbar">
          <el-button :loading="exporting" @click="exportIncomeSources">Excel出力</el-button>
          <el-button @click="openBatchDialog">批量追加</el-button>
          <el-button type="primary" @click="openAddDialog">新規追加</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="accounting-card">
      <div class="accounting-filter-card">
        <div class="accounting-filter-row">
          <el-input v-model="filters.search" placeholder="対象・備考で検索" clearable class="accounting-filter-search" />
          <el-date-picker
            v-model="filters.start_date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="開始日"
            class="accounting-filter-date"
          />
          <el-date-picker
            v-model="filters.end_date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="終了日"
            class="accounting-filter-date"
          />
          <div class="accounting-filter-actions">
            <el-button type="primary" @click="searchIncomeSources">検索</el-button>
            <el-button @click="clearFilters">クリア</el-button>
          </div>
        </div>
      </div>

      <div class="accounting-summary-strip">
        <div class="accounting-summary-pill">
          <span>対象件数</span>
          <strong>{{ summary.count.toLocaleString() }}件</strong>
        </div>
        <div class="accounting-summary-pill">
          <span>収入合計</span>
          <strong>{{ formatYen(summary.totalAmount) }}</strong>
        </div>
      </div>

      <el-table v-loading="loading" :data="incomeSources" stripe>
        <el-table-column label="日付" width="130">
          <template #default="{ row }">{{ formatDate(row.source_date) }}</template>
        </el-table-column>
        <el-table-column prop="source_target" label="対象" min-width="180" />
        <el-table-column label="金額" min-width="120" align="right" header-align="right">
          <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="note" label="備考" min-width="240" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="router.push(`/accounting/income-sources/${row.id}/edit`)">編集</el-button>
            <el-button text type="danger" @click="confirmDelete(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!loading && !incomeSources.length" class="empty-text">データがありません</p>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchIncomeSources"
        />
      </div>
    </el-card>

    <el-dialog v-model="addDialogVisible" title="収入来源を追加" width="640px">
      <el-form ref="addFormRef" :model="addForm" :rules="rules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="日付" prop="source_date">
            <el-date-picker
              v-model="addForm.source_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="対象" prop="source_target">
            <el-input v-model="addForm.source_target" />
          </el-form-item>
          <el-form-item label="金額" prop="amount">
            <el-input v-model="addForm.amount" inputmode="numeric" />
          </el-form-item>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full">
            <el-input v-model="addForm.note" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAddIncomeSource">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" title="収入来源を一括追加" width="860px" class="accounting-batch-dialog">
      <div class="accounting-batch-help">
        Excelからコピーして貼り付けできます。形式：日付・対象・金額・備考
        <code>2026-07-01	公司入金	50000	7月运营费用
2026-07-02,客户A,30000,案件预付款</code>
      </div>
      <el-input v-model="batchText" type="textarea" :rows="8" placeholder="Excel からコピーした内容を貼り付け" />
      <div class="accounting-batch-actions">
        <el-button @click="previewBatch">解析</el-button>
        <el-button
          type="primary"
          :disabled="!batchRows.length || Boolean(invalidBatchRows.length)"
          :loading="batchSubmitting"
          @click="submitBatch"
        >
          確認追加
        </el-button>
      </div>
      <el-table v-if="batchRows.length" :data="batchRows" max-height="320" stripe>
        <el-table-column prop="lineNumber" label="行番号" width="80" />
        <el-table-column prop="source_date" label="日付" width="120" />
        <el-table-column prop="source_target" label="対象" min-width="150" />
        <el-table-column prop="amount" label="金額" width="120" align="right" header-align="right" />
        <el-table-column prop="note" label="備考" min-width="180" show-overflow-tooltip />
        <el-table-column label="状態 / エラー" min-width="220">
          <template #default="{ row }">
            <el-tag v-if="row.errors.length" type="danger">{{ row.errors.join('、') }}</el-tag>
            <el-tag v-else type="success">追加可能</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="batchRows.length" class="help-text">
        追加可能：{{ validBatchRows.length }} 件 / エラー：{{ invalidBatchRows.length }} 件
      </p>
    </el-dialog>
  </section>
</template>
