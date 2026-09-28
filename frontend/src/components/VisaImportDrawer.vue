<script setup lang="ts">
// 返签 visa 表の CSV/XLSX 一括取込：アップロード → シート・列の対応付け → プレビュー・逐行検証
// → 作成（有効行のみ／全件成功時のみ）→ 結果・誤りレポート・PDF ZIP。誤り行は修正して再試行できる。
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../services/http'

interface FieldDef { key: string; label: string; type: string; required: boolean }
interface ParsedRow { row_number: number; cells: Record<string, string>; cell_types: Record<string, string> }
interface RowIssue { field: string; label?: string; raw?: string; message: string; code?: string }
interface PreviewRow {
  row_number: number
  values: Record<string, string | null>
  raw: Record<string, string>
  errors: RowIssue[]
  warnings: RowIssue[]
  already_created?: boolean
}
interface RowResult { status: 'created' | 'error' | 'skipped_duplicate'; application_id?: number; errors?: RowIssue[] }

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; imported: [] }>()
const visible = computed({ get: () => props.modelValue, set: (v: boolean) => emit('update:modelValue', v) })

const step = ref(0)
const busy = ref(false)
const file = ref<File | null>(null)
const encoding = ref('')
const sheet = ref('')
const parsed = reactive({
  batchId: 0, headers: [] as string[], rows: [] as ParsedRow[], mapping: {} as Record<string, string>,
  fields: [] as FieldDef[], sheets: [] as string[], encoding: '', blankRows: 0, duplicateFile: false,
})
const shared = reactive<Record<string, string>>({})
const preview = ref<PreviewRow[]>([])
const mode = ref<'valid_only' | 'all_or_nothing'>('valid_only')
const skipDuplicates = ref(true)
const commitResult = ref<{ success_count: number; error_count: number; skipped_count: number; status: string; results: Record<string, RowResult> } | null>(null)
let requestId = ''

const errorText = (error: unknown, fallback: string) => {
  const response = (error as { response?: { status?: number; data?: { detail?: string } } })?.response
  if (response?.status === 403) return 'この機能を使う権限がありません。'
  return response?.data?.detail || fallback
}
const reset = () => {
  step.value = 0
  file.value = null
  preview.value = []
  commitResult.value = null
  Object.keys(shared).forEach((key) => delete shared[key])
}
const apiBase = (http.defaults.baseURL || '/api/').replace(/\/$/, '')
const templateUrl = `${apiBase}/accounting/visa-imports/template/`

const onFile = (event: Event) => {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null
  sheet.value = ''
}

const upload = async () => {
  if (!file.value) return ElMessage.warning('ファイルを選択してください。')
  busy.value = true
  try {
    const form = new FormData()
    form.append('file', file.value)
    if (sheet.value) form.append('sheet', sheet.value)
    if (encoding.value) form.append('encoding', encoding.value)
    const { data } = await http.post('/accounting/visa-imports/parse/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    Object.assign(parsed, {
      batchId: data.batch_id, headers: data.headers, rows: data.rows, mapping: { ...data.mapping },
      fields: data.fields, sheets: data.sheets, encoding: data.encoding, blankRows: data.blank_rows_skipped,
      duplicateFile: data.duplicate_file,
    })
    sheet.value = data.sheet_name || ''
    requestId = crypto.randomUUID()
    step.value = 1
  } catch (error) {
    ElMessage.error(errorText(error, 'ファイルを読み込めませんでした。'))
  } finally {
    busy.value = false
  }
}

const runPreview = async () => {
  busy.value = true
  try {
    const { data } = await http.post(`/accounting/visa-imports/${parsed.batchId}/preview/`, {
      mapping: parsed.mapping, rows: parsed.rows, shared,
    })
    preview.value = data.results
    step.value = 2
  } catch (error) {
    ElMessage.error(errorText(error, 'プレビューを作成できませんでした。'))
  } finally {
    busy.value = false
  }
}

const counts = computed(() => ({
  valid: preview.value.filter((r) => !r.errors.length && !r.already_created).length,
  errors: preview.value.filter((r) => r.errors.length).length,
  duplicates: preview.value.filter((r) => r.warnings.some((w) => w.code === 'duplicate_existing')).length,
  done: preview.value.filter((r) => r.already_created).length,
}))

// 誤り行の元の値をその場で修正できるよう、対応付けた列だけ入力欄を出す
const mappedHeaders = computed(() => parsed.headers.filter((h) => parsed.mapping[h]))
const rowByNumber = (rowNumber: number) => parsed.rows.find((r) => r.row_number === rowNumber)

const commit = async () => {
  busy.value = true
  try {
    const { data } = await http.post(`/accounting/visa-imports/${parsed.batchId}/commit/`, {
      mapping: parsed.mapping, rows: parsed.rows, shared, mode: mode.value,
      skip_duplicates: skipDuplicates.value, request_id: requestId,
    })
    commitResult.value = data
    step.value = 3
    emit('imported')
  } catch (error) {
    const data = (error as { response?: { data?: {
      results?: Record<string, RowResult>; success_count?: number; error_count?: number; skipped_count?: number; status?: string
    } } })?.response?.data
    if (data?.results) {
      // 「すべて正しい場合だけ作成」で誤りがあった場合：何も作られていないので結果だけ示す
      commitResult.value = {
        success_count: data.success_count ?? 0, error_count: data.error_count ?? 0,
        skipped_count: data.skipped_count ?? 0, status: data.status ?? 'parsed', results: data.results,
      }
    }
    ElMessage.error(errorText(error, '作成できませんでした。'))
  } finally {
    busy.value = false
  }
}

const retryErrors = async () => {
  // 修正した行で再検証し、未作成の行だけを再度作成する（作成済みの行は後端が重複作成しない）
  requestId = crypto.randomUUID()
  await runPreview()
}

const download = async (path: string, fallbackName: string, method: 'get' | 'post' = 'get') => {
  try {
    const response = method === 'get'
      ? await http.get(path, { responseType: 'blob' })
      : await http.post(path, {}, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data as Blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fallbackName
    link.click()
    URL.revokeObjectURL(url)
    if (response.headers['x-failure-count'] && Number(response.headers['x-failure-count']) > 0) {
      ElMessage.warning(`PDF を作成できなかった申請が ${response.headers['x-failure-count']} 件あります（ZIP 内の 結果.txt を確認）。`)
    }
  } catch (error) {
    ElMessage.error(errorText(error, 'ダウンロードできませんでした。'))
  }
}
const statusLabel: Record<string, string> = { created: '作成済み', error: '誤り', skipped_duplicate: '重複のためスキップ' }
const resultRows = computed(() =>
  Object.entries(commitResult.value?.results ?? {}).map(([row, value]) => ({ row: Number(row), ...value }))
    .sort((a, b) => a.row - b.row),
)
</script>

<template>
  <el-drawer v-model="visible" title="CSV / Excel から一括作成" size="92%" @closed="reset">
    <el-steps :active="step" finish-status="success" simple class="import-steps">
      <el-step title="ファイル" />
      <el-step title="列の対応付け" />
      <el-step title="プレビュー" />
      <el-step title="結果" />
    </el-steps>

    <section v-if="step === 0" class="import-section">
      <p>標準テンプレート（CSV）を使うと列が自動で対応付けられます。<a class="text-link" :href="templateUrl">テンプレートをダウンロード</a></p>
      <el-form label-position="top" class="narrow">
        <el-form-item label="ファイル（.csv / .xlsx、500 行・5MB まで）">
          <input type="file" accept=".csv,.xlsx,.tsv,.txt" @change="onFile" />
        </el-form-item>
        <el-form-item label="文字コード（CSV のみ・通常は自動）">
          <el-select v-model="encoding" clearable placeholder="自動判定">
            <el-option label="UTF-8" value="utf-8-sig" />
            <el-option label="Shift_JIS（Excel 日本語）" value="cp932" />
            <el-option label="GB18030（中国語）" value="gb18030" />
          </el-select>
        </el-form-item>
        <el-button type="primary" :loading="busy" @click="upload">読み込む</el-button>
      </el-form>
    </section>

    <section v-else-if="step === 1" class="import-section">
      <el-alert v-if="parsed.duplicateFile" type="warning" :closable="false" show-icon
        title="同じ内容のファイルが以前にも取り込まれています。重複作成に注意してください。" class="gap" />
      <p class="muted">{{ parsed.rows.length }} 行を読み込みました（空行 {{ parsed.blankRows }} 行を除外<template v-if="parsed.encoding">、文字コード {{ parsed.encoding }}</template>）。</p>
      <div v-if="parsed.sheets.length > 1" class="gap">
        シート：
        <el-select v-model="sheet" style="width: 200px" @change="upload">
          <el-option v-for="name in parsed.sheets" :key="name" :label="name" :value="name" />
        </el-select>
      </div>
      <el-table :data="parsed.headers.map((h) => ({ header: h }))" size="small" class="gap">
        <el-table-column prop="header" label="ファイルの列" min-width="160" />
        <el-table-column label="取込先の項目" min-width="220">
          <template #default="{ row }">
            <el-select v-model="parsed.mapping[row.header]" clearable placeholder="取り込まない" style="width: 100%">
              <el-option v-for="f in parsed.fields" :key="f.key" :label="f.label + (f.required ? '（必須）' : '')" :value="f.key" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="1 行目の値" min-width="180">
          <template #default="{ row }">{{ parsed.rows[0]?.cells[row.header] ?? '' }}</template>
        </el-table-column>
      </el-table>
      <details class="gap">
        <summary>全行共通の項目（行の値が空のときに使う。例：在日保証人）</summary>
        <div class="shared-grid">
          <el-input v-for="key in ['guarantor_name', 'guarantor_phone', 'guarantor_address', 'guarantor_relationship', 'guarantor_occupation']"
            :key="key" v-model="shared[key]" :placeholder="parsed.fields.find((f) => f.key === key)?.label" />
        </div>
      </details>
      <el-button @click="step = 0">戻る</el-button>
      <el-button type="primary" :loading="busy" @click="runPreview">プレビュー</el-button>
    </section>

    <section v-else-if="step === 2" class="import-section">
      <p>
        作成できる行 <strong>{{ counts.valid }}</strong> / 誤り <strong class="danger">{{ counts.errors }}</strong>
        / 既存と重複 <strong>{{ counts.duplicates }}</strong><template v-if="counts.done"> / 作成済み {{ counts.done }}</template>
      </p>
      <el-table :data="preview" size="small" max-height="520" class="gap">
        <el-table-column prop="row_number" label="行" width="60" />
        <el-table-column label="状態" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.already_created" type="info" size="small">作成済み</el-tag>
            <el-tag v-else-if="row.errors.length" type="danger" size="small">誤り</el-tag>
            <el-tag v-else-if="row.warnings.length" type="warning" size="small">要確認</el-tag>
            <el-tag v-else type="success" size="small">OK</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="申請人 / 旅券番号" min-width="180">
          <template #default="{ row }">{{ row.values.applicant_name || '（未入力）' }} / {{ row.values.passport_number || '-' }}</template>
        </el-table-column>
        <el-table-column label="誤り・注意" min-width="260">
          <template #default="{ row }">
            <div v-for="(issue, i) in row.errors" :key="'e' + i" class="danger">{{ issue.message }}<span v-if="issue.raw" class="muted">（元の値：{{ issue.raw }}）</span></div>
            <div v-for="(issue, i) in row.warnings" :key="'w' + i" class="warn">{{ issue.message }}</div>
          </template>
        </el-table-column>
        <el-table-column label="修正（元の値）" min-width="320">
          <template #default="{ row }">
            <div v-if="row.errors.length && rowByNumber(row.row_number)" class="fix-grid">
              <el-input v-for="header in mappedHeaders" :key="header" v-model="rowByNumber(row.row_number)!.cells[header]" size="small" :placeholder="header">
                <template #prepend>{{ header }}</template>
              </el-input>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-form inline>
        <el-form-item label="作成方式">
          <el-radio-group v-model="mode">
            <el-radio value="valid_only">有効な行だけ作成し、誤り行は報告する</el-radio>
            <el-radio value="all_or_nothing">すべて正しい場合だけ作成する</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item><el-checkbox v-model="skipDuplicates">既存と旅券番号が重複する行は作成しない</el-checkbox></el-form-item>
      </el-form>
      <el-button @click="step = 1">戻る</el-button>
      <el-button :loading="busy" @click="runPreview">修正を反映して再検証</el-button>
      <el-button type="primary" :loading="busy" :disabled="!counts.valid" @click="commit">作成する</el-button>
    </section>

    <section v-else-if="step === 3 && commitResult" class="import-section">
      <el-result :icon="commitResult.error_count ? 'warning' : 'success'"
        :title="`作成 ${commitResult.success_count} 件 / 誤り ${commitResult.error_count} 件 / 重複スキップ ${commitResult.skipped_count} 件`" />
      <div class="actions">
        <el-button type="primary" :disabled="!commitResult.success_count"
          @click="download(`/accounting/visa-imports/${parsed.batchId}/pdf-zip/`, 'visa_return.zip', 'post')">PDF を ZIP でダウンロード</el-button>
        <el-button :disabled="!commitResult.error_count"
          @click="download(`/accounting/visa-imports/${parsed.batchId}/error-report/`, 'visa_import_errors.csv')">誤りレポート（CSV）</el-button>
        <el-button v-if="commitResult.error_count" @click="retryErrors">誤り行を修正して再試行</el-button>
      </div>
      <el-table :data="resultRows" size="small" max-height="360">
        <el-table-column prop="row" label="行" width="60" />
        <el-table-column label="結果" width="160"><template #default="{ row }">{{ statusLabel[row.status] }}</template></el-table-column>
        <el-table-column label="詳細" min-width="300">
          <template #default="{ row }">
            <span v-if="row.application_id">申請 ID {{ row.application_id }}</span>
            <div v-for="(issue, i) in row.errors ?? []" :key="i" class="danger">{{ issue.label }}：{{ issue.message }}</div>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </el-drawer>
</template>

<style scoped>
.import-steps { margin-bottom: 16px; }
.import-section { display: flex; flex-direction: column; gap: 8px; }
.narrow { max-width: 420px; }
.gap { margin-bottom: 8px; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; }
.danger { color: var(--el-color-danger); font-size: 12px; }
.warn { color: var(--el-color-warning); font-size: 12px; }
.shared-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; margin: 8px 0; }
.fix-grid { display: grid; gap: 4px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.actions :deep(.el-button + .el-button) { margin-left: 0; }
</style>
