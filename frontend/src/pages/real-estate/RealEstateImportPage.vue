<script setup lang="ts">
// LIST.xlsx / CSV の dry-run。取引は作らない（本取込は第 1 版では無い）。工作表1 だけを読み、强哥は読まない。
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadDryRunReport, getDryRun, listDryRuns, runDryRun } from '../../api/realEstate'
import type { DryRunHistoryRow, DryRunReport, DryRunRow } from '../../types/realEstate'
import { formatDateTime } from '../../utils/date'

const file = ref<File | null>(null)
const running = ref(false)
const report = ref<DryRunReport | null>(null)
const history = ref<DryRunHistoryRow[]>([])
const filter = ref<'all' | 'error' | 'to_complete' | 'duplicate' | 'ready'>('all')

const loadHistory = async () => {
  try {
    history.value = await listDryRuns()
  } catch {
    history.value = []
  }
}
const run = async () => {
  if (!file.value) return ElMessage.warning('ファイルを選択してください。')
  running.value = true
  try {
    report.value = await runDryRun(file.value)
    ElMessage.success('dry-run が完了しました（取引は作成していません）。')
    await loadHistory()
  } catch (error) {
    const r = (error as { response?: { status?: number; data?: { detail?: string } } })?.response
    ElMessage.error(r?.data?.detail || (r?.status === 403 ? 'この操作の権限がありません。' : 'dry-run に失敗しました。'))
  } finally {
    running.value = false
  }
}
const open = async (id: number) => {
  report.value = await getDryRun(id)
}
const downloadReport = async () => {
  if (!report.value) return
  const blob = await downloadDryRunReport(report.value.id)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `real_estate_dry_run_${report.value.id}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
const isDuplicate = (r: DryRunRow) => r.duplicate_in_file_rows.length > 0 || r.duplicate_existing.length > 0
const rows = computed(() => (report.value?.results ?? []).filter((r) => {
  if (filter.value === 'error') return r.errors.length > 0
  if (filter.value === 'to_complete') return r.to_complete.length > 0
  if (filter.value === 'duplicate') return isDuplicate(r)
  if (filter.value === 'ready') return !r.errors.length && !r.to_complete.length && !isDuplicate(r)
  return true
}))
const SUMMARY_LABELS: Record<string, string> = {
  rows: 'データ行', blank_rows_skipped: '空行（除外）', error_rows: '誤りのある行', to_complete_rows: '要補充の行',
  duplicate_in_file_rows: 'ファイル内重複', duplicate_existing_rows: '登録済みと重複', ready_rows: '問題なし',
}
const pickName = (c: { name: string }) => c.name
const pickNumber = (c: { number: string }) => c.number

onMounted(loadHistory)
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>不動産 LIST 取込（dry-run）</h1>
      <p class="sub">検証と報告だけを行い、取引は作成しません。XLSX は「工作表1」だけを読み込みます。本番環境では使用できません。</p>
    </div>
    <el-card shadow="never" class="mb">
      <div class="row">
        <input type="file" accept=".xlsx,.csv" @change="(e: Event) => (file = (e.target as HTMLInputElement).files?.[0] ?? null)" />
        <el-button type="primary" :loading="running" @click="run">dry-run を実行</el-button>
      </div>
    </el-card>

    <template v-if="report">
      <el-card shadow="never" class="mb">
        <template #header>
          <div class="row">
            <span>{{ report.file_name }}／{{ report.sheet }}</span>
            <el-tag v-if="report.previous_runs?.length" size="small">同じファイルの以前の実行：{{ report.previous_runs.join('、') }}</el-tag>
            <div class="grow" />
            <el-button size="small" @click="downloadReport">誤り・注記の報告（CSV）</el-button>
          </div>
        </template>
        <div class="summary">
          <div v-for="(value, key) in report.summary" :key="key" class="pill"><span>{{ SUMMARY_LABELS[key] || key }}</span><strong>{{ value }}</strong></div>
        </div>
        <el-alert v-if="report.missing_columns.length" type="warning" :closable="false" class="mt"
                  :title="`見つからない列：${report.missing_columns.join('、')}`" />
        <h4>列ごとの値（空・「-」・0・値）</h4>
        <el-table :data="Object.entries(report.column_stats).map(([k, v]) => ({ column: k, ...v }))" size="small" max-height="260">
          <el-table-column prop="column" label="列" min-width="160" />
          <el-table-column prop="empty" label="空" width="70" />
          <el-table-column prop="dash" label="-" width="70" />
          <el-table-column prop="zero" label="0" width="70" />
          <el-table-column prop="value" label="値" width="70" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <el-radio-group v-model="filter" size="small" class="mb">
          <el-radio-button value="all">すべて</el-radio-button>
          <el-radio-button value="error">誤り</el-radio-button>
          <el-radio-button value="to_complete">要補充</el-radio-button>
          <el-radio-button value="duplicate">重複</el-radio-button>
          <el-radio-button value="ready">問題なし</el-radio-button>
        </el-radio-group>
        <el-table :data="rows" size="small" border>
          <el-table-column label="行" width="60"><template #default="{ row }">{{ row.row_number }}</template></el-table-column>
          <el-table-column label="元の値" min-width="220">
            <template #default="{ row }">
              <div>{{ row.raw['客名'] }}／{{ row.raw['物件名'] }} {{ row.raw['部屋番号'] }}</div>
              <div class="sub">番号 {{ row.raw['番号'] || '-' }}・日期 {{ row.raw['日期'] || '-' }}・担当 {{ row.raw['担当者'] || '-' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="業務金額" min-width="230">
            <template #default="{ row }">
              <div class="sub">中介 {{ row.raw['中介费'] || '空' }}／広告 {{ row.raw['广告料'] || '空' }}／手数料 {{ row.raw['手续费'] || '空' }}</div>
            </template>
          </el-table-column>
          <el-table-column label="誤り・要補充・注記" min-width="260">
            <template #default="{ row }">
              <div v-for="e in row.errors" :key="e.column + e.message" class="err">{{ e.column }}：{{ e.message }}<span v-if="e.raw">（{{ e.raw }}）</span></div>
              <el-tag v-for="t in row.to_complete" :key="t" size="small" type="warning" class="tag">要補充：{{ t }}</el-tag>
              <div v-for="n in row.notes" :key="n.column + n.code" class="sub">{{ n.column }}：{{ n.message }}</div>
              <div v-if="row.duplicate_in_file_rows.length" class="err">ファイル内重複：{{ row.duplicate_in_file_rows.join('、') }} 行目</div>
              <div v-if="row.duplicate_existing.length" class="err">登録済み：{{ row.duplicate_existing.map(pickNumber).join('、') }}</div>
            </template>
          </el-table-column>
          <el-table-column label="候補（自動では結び付けない）" min-width="220">
            <template #default="{ row }">
              <div v-if="row.candidates.customer.length" class="sub">顧客：{{ row.candidates.customer.map(pickName).join('、') }}</div>
              <div v-if="row.candidates.management_company.length" class="sub">会社：{{ row.candidates.management_company.map(pickName).join('、') }}</div>
              <div v-if="row.candidates.property.length" class="sub">物件：{{ row.candidates.property.map(pickNumber).join('、') }}</div>
              <div v-if="row.candidates.responsible.length" class="sub">担当：{{ row.candidates.responsible.map(pickName).join('、') }}</div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-card shadow="never" class="mt">
      <template #header>実行履歴</template>
      <el-table :data="history" size="small" empty-text="まだ実行していません">
        <el-table-column label="日時" width="160"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column prop="file_name" label="ファイル" min-width="160" />
        <el-table-column prop="sheet" label="シート" width="100" />
        <el-table-column label="集計" min-width="260"><template #default="{ row }">行 {{ row.summary.rows }}・誤り {{ row.summary.error_rows }}・要補充 {{ row.summary.to_complete_rows }}・問題なし {{ row.summary.ready_rows }}</template></el-table-column>
        <el-table-column width="80"><template #default="{ row }"><el-button text size="small" @click="open(row.id)">開く</el-button></template></el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.row,
.summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.grow {
  flex: 1;
}

.pill {
  display: flex;
  flex-direction: column;
  padding: 6px 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  min-width: 110px;
}

.pill span,
.sub {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.err {
  color: var(--el-color-danger);
  font-size: 12px;
}

.tag {
  margin: 0 4px 2px 0;
}

.mt {
  margin-top: 12px;
}

.mb {
  margin-bottom: 12px;
}
</style>
