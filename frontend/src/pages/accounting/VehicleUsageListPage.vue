<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  createAccountingVehicleUsage,
  deleteAccountingVehicleUsage,
  listAccountingVehicleUsages,
} from '../../api/accounting'
import type { AccountingListParams, VehicleUsage, VehicleUsagePayload } from '../../types/accounting'
import { formatDate } from '../../utils/date'
import { createTimestamp, exportRowsToExcel } from '../../utils/exportExcel'
import './accounting.css'

interface BatchVehicleUsageRow {
  lineNumber: number
  usage_date: string
  place: string
  distance_km: string
  usage_target: string
  purpose: string
  note: string
  errors: string[]
}

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const vehicleUsages = ref<VehicleUsage[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filters = ref<AccountingListParams>({
  search: '',
  start_date: null,
  end_date: null,
  purpose: '',
})
const addDialogVisible = ref(false)
const addFormRef = ref<FormInstance>()
const submitting = ref(false)
const purposeOptions = ['客户拜访', '送资料', '跑役所', '银行手续', '看房', '购买物品', '公司业务', '其他']
const addForm = ref<VehicleUsagePayload>({
  usage_date: '',
  place: '',
  distance_km: '',
  usage_target: '',
  purpose: '',
  note: '',
  is_exported: false,
})
const batchDialogVisible = ref(false)
const batchText = ref('')
const batchRows = ref<BatchVehicleUsageRow[]>([])
const batchSubmitting = ref(false)
const exporting = ref(false)
const summary = ref({
  count: 0,
  totalDistance: 0,
})

const rules: FormRules<VehicleUsagePayload> = {
  usage_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  distance_km: [{ required: true, message: '走行距離を入力してください。', trigger: 'blur' }],
}

const formatDistance = (value: number | string) => `${Number(value || 0).toLocaleString()} km`
const formatDistanceTotal = (value: number | string) => `${Number(value || 0).toLocaleString()}km`
const validBatchRows = computed(() => batchRows.value.filter((row) => !row.errors.length))
const invalidBatchRows = computed(() => batchRows.value.filter((row) => row.errors.length))

const isValidDate = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

const fetchVehicleUsages = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listAccountingVehicleUsages({ ...filters.value, page })
    vehicleUsages.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = '用車記録の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const clearFilters = () => {
  filters.value = {
    search: '',
    start_date: null,
    end_date: null,
    purpose: '',
  }
  fetchVehicleUsages(1)
  refreshVehicleUsageSummary()
}

const fetchAllVehicleUsagesForExport = async () => {
  const rows: VehicleUsage[] = []
  let page = 1

  while (true) {
    const data = await listAccountingVehicleUsages({ ...filters.value, page })
    rows.push(...data.results)
    if (rows.length >= data.count || !data.results.length) break
    page += 1
  }

  return rows
}

const refreshVehicleUsageSummary = async () => {
  try {
    const rows = await fetchAllVehicleUsagesForExport()
    summary.value = {
      count: rows.length,
      totalDistance: rows.reduce((total, row) => total + Number(row.distance_km || 0), 0),
    }
  } catch {
    summary.value = {
      count: 0,
      totalDistance: 0,
    }
  }
}

const searchVehicleUsages = () => {
  fetchVehicleUsages(1)
  refreshVehicleUsageSummary()
}

const exportVehicleUsages = async () => {
  exporting.value = true
  try {
    const rows = await fetchAllVehicleUsagesForExport()
    if (!rows.length) {
      ElMessage.warning('出力対象のデータがありません')
      return
    }

    exportRowsToExcel(
      rows.map((row) => ({
        日付: row.usage_date,
        場所: row.place,
        走行距離: Number(row.distance_km || 0),
        利用対象: row.usage_target,
        用途: row.purpose,
        備考: row.note,
      })),
      '用車記録',
      `用車記録_${createTimestamp()}.xlsx`,
    )
  } catch {
    ElMessage.error('Excel出力に失敗しました。')
  } finally {
    exporting.value = false
  }
}

const openAddDialog = () => {
  addForm.value = {
    usage_date: '',
    place: '',
    distance_km: '',
    usage_target: '',
    purpose: '',
    note: '',
    is_exported: false,
  }
  addFormRef.value?.clearValidate()
  addDialogVisible.value = true
}

const submitAddVehicleUsage = async () => {
  if (!addFormRef.value) return
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createAccountingVehicleUsage(addForm.value)
    ElMessage.success('用車記録を作成しました。')
    addDialogVisible.value = false
    await fetchVehicleUsages(1)
    await refreshVehicleUsageSummary()
  } catch {
    ElMessage.error('用車記録の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const openBatchDialog = () => {
  batchText.value = ''
  batchRows.value = []
  batchDialogVisible.value = true
}

const parseBatchLine = (line: string, lineNumber: number): BatchVehicleUsageRow | null => {
  if (!line) return null

  const cells = line.includes('\t') ? line.split('\t') : line.split(',')
  const normalizedCells = cells.map((cell) => cell.trim())

  if (lineNumber === 1 && ['日期', '日付', 'usage_date'].includes(normalizedCells[0])) {
    return null
  }

  const [usageDate = '', place = '', distanceKm = '', usageTarget = '', purpose = '', note = ''] = normalizedCells
  const errors: string[] = []

  if (!usageDate) {
    errors.push('日付が未入力です')
  } else if (!isValidDate(usageDate)) {
    errors.push('日付形式が正しくありません')
  }
  if (!place) {
    errors.push('場所が未入力です')
  }
  if (!distanceKm) {
    errors.push('走行距離が未入力です')
  } else if (Number.isNaN(Number(distanceKm))) {
    errors.push('走行距離は数字で入力してください')
  }
  if (!usageTarget) {
    errors.push('対象が未入力です')
  }

  return {
    lineNumber,
    usage_date: usageDate,
    place,
    distance_km: distanceKm,
    usage_target: usageTarget,
    purpose,
    note,
    errors,
  }
}

const previewBatch = () => {
  const rows = batchText.value
    .split(/\r?\n/)
    .map((line, index) => parseBatchLine(line.trim(), index + 1))
    .filter((row): row is BatchVehicleUsageRow => Boolean(row))

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
      await createAccountingVehicleUsage({
        usage_date: row.usage_date,
        place: row.place,
        distance_km: row.distance_km,
        usage_target: row.usage_target,
        purpose: row.purpose,
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
  await fetchVehicleUsages(1)
  await refreshVehicleUsageSummary()
}

const confirmDelete = async (vehicleUsage: VehicleUsage) => {
  try {
    await ElMessageBox.confirm('この用車記録を削除します。よろしいですか？', '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingVehicleUsage(vehicleUsage.id)
    ElMessage.success('用車記録を削除しました。')
    await fetchVehicleUsages(currentPage.value)
    await refreshVehicleUsageSummary()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('用車記録の削除に失敗しました。')
    }
  }
}

onMounted(() => {
  fetchVehicleUsages()
  refreshVehicleUsageSummary()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>用車記録</h1>
          <p>業務で利用した移動距離と用途を記録します</p>
        </div>
        <div class="accounting-toolbar">
          <el-button :loading="exporting" @click="exportVehicleUsages">Excel出力</el-button>
          <el-button @click="openBatchDialog">批量追加</el-button>
          <el-button type="primary" @click="openAddDialog">新規追加</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="accounting-card">
      <div class="accounting-filter-card">
        <div class="accounting-filter-row">
          <el-input v-model="filters.search" placeholder="場所・対象・備考で検索" clearable class="accounting-filter-search" />
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
          <el-select v-model="filters.purpose" clearable placeholder="用途" class="accounting-filter-select">
            <el-option v-for="purpose in purposeOptions" :key="purpose" :label="purpose" :value="purpose" />
          </el-select>
          <div class="accounting-filter-actions">
            <el-button type="primary" @click="searchVehicleUsages">検索</el-button>
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
          <span>走行距離合計</span>
          <strong>{{ formatDistanceTotal(summary.totalDistance) }}</strong>
        </div>
      </div>

      <el-table v-loading="loading" :data="vehicleUsages" stripe>
        <el-table-column label="日付" width="130">
          <template #default="{ row }">{{ formatDate(row.usage_date) }}</template>
        </el-table-column>
        <el-table-column prop="place" label="場所" min-width="150" />
        <el-table-column label="走行距離" width="130" align="right" header-align="right">
          <template #default="{ row }">{{ formatDistance(row.distance_km) }}</template>
        </el-table-column>
        <el-table-column prop="usage_target" label="利用対象" min-width="160" />
        <el-table-column prop="purpose" label="用途" min-width="140" />
        <el-table-column prop="note" label="備考" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="router.push(`/accounting/vehicle-usages/${row.id}/edit`)">編集</el-button>
            <el-button text type="danger" @click="confirmDelete(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!loading && !vehicleUsages.length" class="empty-text">データがありません</p>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchVehicleUsages"
        />
      </div>
    </el-card>

    <el-dialog v-model="addDialogVisible" title="用車記録を追加" width="720px">
      <el-form ref="addFormRef" :model="addForm" :rules="rules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="日付" prop="usage_date">
            <el-date-picker
              v-model="addForm.usage_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="場所" prop="place">
            <el-input v-model="addForm.place" />
          </el-form-item>
          <el-form-item label="走行距離" prop="distance_km">
            <el-input v-model="addForm.distance_km" inputmode="decimal" />
          </el-form-item>
          <el-form-item label="利用対象" prop="usage_target">
            <el-input v-model="addForm.usage_target" />
          </el-form-item>
          <el-form-item label="用途" prop="purpose">
            <el-select v-model="addForm.purpose" clearable placeholder="選択してください" class="form-control">
              <el-option v-for="purpose in purposeOptions" :key="purpose" :label="purpose" :value="purpose" />
            </el-select>
          </el-form-item>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full">
            <el-input v-model="addForm.note" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAddVehicleUsage">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" title="用車記録を一括追加" width="920px" class="accounting-batch-dialog">
      <div class="accounting-batch-help">
        Excelからコピーして貼り付けできます。形式：日付・場所・走行距離・利用対象・用途・備考
        <code>2026-07-01	大阪入管	12.5	王先生	入管同行	往返
2026-07-02,役所,8,公司内部,资料取得,住民票取得</code>
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
        <el-table-column prop="usage_date" label="日付" width="120" />
        <el-table-column prop="place" label="場所" min-width="140" />
        <el-table-column prop="distance_km" label="走行距離" width="120" align="right" header-align="right" />
        <el-table-column prop="usage_target" label="利用対象" min-width="150" />
        <el-table-column prop="purpose" label="用途" min-width="130" />
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
