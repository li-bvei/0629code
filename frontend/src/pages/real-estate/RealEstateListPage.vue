<script setup lang="ts">
// 不動産取引の協同台帳。モジュール権限のある利用者は全件を共同で扱う。
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules, TableInstance } from 'element-plus'
import {
  bulkUpdateTransactions, closeFiscalYear, createTransaction, exportLedgers, exportTransactions, listResponsibleSuggestions,
  listTransactions, previewBulkSelectedRows, previewBulkSelection,
} from '../../api/realEstate'
import RemoteCustomerSelect from '../../components/RemoteCustomerSelect.vue'
import { useAuthStore } from '../../stores/auth'
import type { RealEstateTransaction, RealEstateTransactionPayload } from '../../types/realEstate'
import { PAYMENT_OPTIONS, STAGE_OPTIONS, TYPE_OPTIONS } from '../../types/realEstate'
import { describeApiErrors, responseOf } from '../../utils/apiErrors'
import { formatDate } from '../../utils/date'
import { buildBulkRequest, buildPreviewRequest, describeBulkChanges, emptyBulkForm } from '../../utils/realEstateBulk'
import type { BulkTarget } from '../../utils/realEstateBulk'

const router = useRouter()
const auth = useAuthStore()
const rows = ref<RealEstateTransaction[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const errorMessage = ref('')
const emptyFilters = () => ({
  responsible_name: '', stage: '', management_company: '', payment_status: '', transfer_status: '', transaction_type: '',
  archive_status: 'active', transaction_date_from: '', transaction_date_to: '', missing: false, keyword: '',
})
const filters = reactive(emptyFilters())
// 一覧に実際に適用した条件（入力途中の条件ではなく、これを出力・一括変更の対象にする）
const appliedFilters = ref(emptyFilters())
const dateRange = computed<[string, string] | null>({
  get: () => (filters.transaction_date_from || filters.transaction_date_to
    ? [filters.transaction_date_from, filters.transaction_date_to] as [string, string] : null),
  set: (value: [string, string] | null) => {
    filters.transaction_date_from = value?.[0] ?? ''
    filters.transaction_date_to = value?.[1] ?? ''
  },
})
const TRANSFER_FILTER_OPTIONS = [
  { value: 'unset', label: '未設定' }, { value: 'pending', label: '振込待ち' }, { value: 'transferred', label: '振込済み' },
]

const loadRows = async (target: number) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listTransactions({ page: target, ...appliedFilters.value })
    rows.value = data.results
    total.value = data.count
    page.value = target
  } catch (error) {
    const lines = responseOf(error).status === 400 ? describeApiErrors(responseOf(error).data) : []
    errorMessage.value = lines.join(' ') || '不動産記録の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}
// 検索・リセット：条件が変わるので選択を解除する（古い条件の選択で一括変更しない）
const fetchRows = (target = 1) => {
  appliedFilters.value = { ...filters }
  clearSelection()
  return loadRows(target)
}
const resetFilters = () => {
  Object.assign(filters, emptyFilters())
  fetchRows(1)
}

// --- 一括変更（bulk_change_real_estate を持つ人だけに表示。判定は後端） ---
const canBulk = auth.can('real_estate.bulk_change_real_estate') && auth.can('real_estate.change_real_estate')
const tableRef = ref<TableInstance>()
// 一覧でチェックした記録（ページをまたいで保持）。チェックした時点に表示されていた updated_at を一緒に持つ。
const selectedRows = ref<{ id: number; updated_at: string }[]>([])
// 「絞り込み結果をすべて選択」で後端が固定した対象
const filterSelection = ref<BulkTarget | null>(null)
// 一括変更の対話を開いた時点で後端が固定した対象（手動選択も絞り込み全選択も、必ずこれで実行する）
const bulkTarget = ref<BulkTarget | null>(null)
const selectingAll = ref(false)
const preparingBulk = ref(false)
const targetCount = computed(() => filterSelection.value?.count ?? selectedRows.value.length)
const onSelectionChange = (selected: RealEstateTransaction[]) => {
  selectedRows.value = selected.map((row) => ({ id: row.id, updated_at: row.updated_at }))
  if (selected.length) filterSelection.value = null
}
function clearSelection() {
  selectedRows.value = []
  filterSelection.value = null
  bulkTarget.value = null
  tableRef.value?.clearSelection()
}
const bulkErrorText = (error: unknown, fallback: string) => {
  const { status, data } = responseOf(error)
  if (status === 403) return '一括変更の権限がありません。'
  return describeApiErrors(data, {
    changes: '変更内容', selection: '対象', selection_token: '対象', expected_count: '対象件数', clear_fields: '空欄にする項目',
  }).join(' ') || fallback
}
// 409：選択後に他の操作で対象が変わった。何も変更されていないので、最新の一覧を読み直して選び直してもらう。
const handleBulkFailure = async (error: unknown, fallback: string) => {
  ElMessage.error({ message: bulkErrorText(error, fallback), duration: 8000 })
  if (responseOf(error).status === 409) {
    bulkVisible.value = false
    clearSelection()
    await loadRows(page.value)
  }
}
// 「絞り込み結果をすべて選択」：件数と対象は後端が現在の条件で数え直して固定する（表示中のページだけではない）
const selectAllFiltered = async () => {
  selectingAll.value = true
  try {
    const preview = await previewBulkSelection(appliedFilters.value)
    if (!preview.count) {
      ElMessage.warning('この条件に一致する利用中の記録はありません。')
      return
    }
    tableRef.value?.clearSelection()
    selectedRows.value = []
    filterSelection.value = preview
  } catch (error) {
    ElMessage.error(bulkErrorText(error, '絞り込み結果を選択できませんでした。'))
  } finally {
    selectingAll.value = false
  }
}
const bulkVisible = ref(false)
const bulkSaving = ref(false)
const bulkForm = ref(emptyBulkForm())
const stageLabel = (value: string) => STAGE_OPTIONS.find((o) => o.value === value)?.label ?? value
const openBulk = async (stage = '') => {
  if (filterSelection.value) {
    bulkTarget.value = filterSelection.value
  } else {
    // 手動で選択した記録も、絞り込み全選択と同じく後端で対象と版を固定してから進む
    preparingBulk.value = true
    try {
      bulkTarget.value = await previewBulkSelectedRows(buildPreviewRequest(selectedRows.value))
    } catch (error) {
      await handleBulkFailure(error, '選択した記録を確認できませんでした。')
      return
    } finally {
      preparingBulk.value = false
    }
  }
  bulkForm.value = emptyBulkForm()
  if (stage) {
    bulkForm.value.enabled.stage = true
    bulkForm.value.stage = stage
  }
  bulkVisible.value = true
}
const submitBulk = async () => {
  const built = buildBulkRequest(bulkTarget.value, bulkForm.value)
  if (!built.request) {
    ElMessage.warning(built.error)
    return
  }
  const lines = [
    `対象：${built.request.expected_count} 件（利用中の記録のみ）`,
    `条件：${bulkTarget.value?.filter_summary.join(' / ') ?? ''}`,
    ...describeBulkChanges(built.request, stageLabel).map((line) => `変更：${line}`),
    'チェックした項目だけを変更します。選択後に他の人が変更した記録が 1 件でもあれば、全件を変更しません。',
  ]
  try {
    await ElMessageBox.confirm(lines.join('\n'), '一括変更の最終確認', {
      confirmButtonText: `${built.request.expected_count} 件を変更する`, cancelButtonText: '戻る', type: 'warning',
      customStyle: { whiteSpace: 'pre-line' },
    })
  } catch {
    return
  }
  bulkSaving.value = true
  try {
    const result = await bulkUpdateTransactions(built.request)
    const ledgerNote = result.locked_ledger_count
      ? ` ロック済みの法定台帳 ${result.locked_ledger_count} 件は変更していません（必要な場合は各記録で台帳を更正してください）。` : ''
    ElMessage.success({
      message: `${result.updated} 件を変更しました${result.unchanged ? `（既に同じ内容 ${result.unchanged} 件）` : ''}。${ledgerNote}`,
      duration: 6000,
    })
    bulkVisible.value = false
    clearSelection()
    await loadRows(page.value)
  } catch (error) {
    await handleBulkFailure(error, '一括変更できませんでした。何も変更していません。')
  } finally {
    bulkSaving.value = false
  }
}
const openRow = (row: RealEstateTransaction, column?: { type?: string }) => {
  if (column?.type === 'selection') return
  router.push(`/real-estate/${row.id}`)
}
const yen = (v: string | null) => (v === null || v === '' ? '-' : `￥${Number(v).toLocaleString()}`)

// --- 新規（首画面は 7 項目だけ。法定項目は詳細で段階的に補充） ---
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const emptyForm = (): RealEstateTransactionPayload => ({
  party_name: '', customer: null, property_name: '', room_number: '', management_company_name: '',
  responsible_name: '', transaction_type: 'rental', stage: 'inquiry',
})
const queryResponsible = async (query: string, done: (items: { value: string }[]) => void) => {
  try {
    done((await listResponsibleSuggestions(query)).map((item) => ({ value: item.name })))
  } catch {
    done([])
  }
}
const form = ref<RealEstateTransactionPayload>(emptyForm())
const rules: FormRules = {
  party_name: [{ required: true, message: '顧客・当事者名を入力してください。', trigger: 'blur' }],
  property_name: [{ required: true, message: '物件名を入力してください。', trigger: 'blur' }],
}
const openCreate = () => {
  form.value = emptyForm()
  formRef.value?.clearValidate()
  dialogVisible.value = true
}
const submit = async () => {
  if (!(await formRef.value?.validate().catch(() => false))) return
  saving.value = true
  try {
    const created = await createTransaction(form.value)
    ElMessage.success(`${created.transaction_number} を作成しました。`)
    dialogVisible.value = false
    router.push(`/real-estate/${created.id}`)
  } catch (error) {
    const data = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
    ElMessage.error(data?.status === 403 ? '不動産取引を新規登録する権限がありません。' : '作成できませんでした。')
  } finally {
    saving.value = false
  }
}

// --- 法定台帳の年度締め・出力（manage_legal_ledger のみ。判定は後端） ---
const canManageLedger = auth.can('real_estate.manage_legal_ledger')
const canCreate = auth.can('real_estate.create_real_estate')
const canCloseYear = auth.can('real_estate.close_legal_ledger_year')
// LIST 取込はナビゲーションの独立した入口ではなく、この画面の補助操作として出す（P3。権限は従来どおり）
const canImport = auth.can('real_estate.import_real_estate')
const canExport = auth.can('real_estate.export_real_estate')
const askFiscalYear = async (title: string, message: string) => {
  const result = await ElMessageBox.prompt(message, title, {
    inputPattern: /^\d{4}$/, inputErrorMessage: '西暦 4 桁で入力してください', confirmButtonText: '実行', cancelButtonText: 'キャンセル',
  })
  return Number(result.value)
}
const closeYear = async () => {
  let year: number
  try {
    year = await askFiscalYear('年度締め', '締める事業年度（末日の属する年）を入力してください。該当年度の台帳をすべてロックし、事業年度末月と保存期限を確定します（削除はしません）。')
  } catch {
    return
  }
  try {
    const result = await closeFiscalYear(year)
    ElMessage.success(`${result.fiscal_year} 年度：台帳 ${result.ledgers} 件（新たにロック ${result.newly_locked} 件）を締めました。`)
    loadRows(page.value)
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    ElMessage.error(status === 403 ? '年度締めの権限がありません。' : '年度締めに失敗しました。')
  }
}
const exportYear = async () => {
  let year: number | undefined
  try {
    const result = await ElMessageBox.prompt('出力する事業年度（空欄ですべて）', '台帳の出力（CSV）', {
      inputPattern: /^(\d{4})?$/, inputErrorMessage: '西暦 4 桁で入力してください', confirmButtonText: '出力', cancelButtonText: 'キャンセル',
    })
    year = result.value ? Number(result.value) : undefined
  } catch {
    return
  }
  try {
    const blob = await exportLedgers(year)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `法定台帳_${year ?? 'all'}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('出力できませんでした。')
  }
}

const exportList = async () => {
  try {
    const blob = await exportTransactions(appliedFilters.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '不動産取引.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('取引一覧を出力できませんでした。')
  }
}

onMounted(() => loadRows(1))
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <div>
        <h1>不動産取引</h1>
        <p class="sub">賃貸を中心とした取引の総覧です。法定項目は各記録の画面で段階的に補充します。</p>
      </div>
      <div class="header-actions">
        <el-button v-if="canExport" @click="exportList">取引 CSV 出力</el-button>
        <!-- 台帳出力は「出力」＋「台帳管理」、年度締めは「年度締め」の権限（後端の判定と同じ） -->
        <el-button v-if="canExport && canManageLedger" @click="exportYear">台帳 CSV 出力</el-button>
        <el-button v-if="canCloseYear" type="warning" plain @click="closeYear">年度締め</el-button>
        <el-button v-if="canImport" @click="router.push('/real-estate/import')">LIST 取込（確認）</el-button>
        <el-button v-if="canCreate" type="primary" @click="openCreate">新規登録</el-button>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="filter-card">
      <div class="filters">
        <el-input v-model="filters.responsible_name" clearable placeholder="担当（文字検索）" style="width: 150px" />
        <el-select v-model="filters.stage" clearable placeholder="段階" style="width: 130px">
          <el-option v-for="o in STAGE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-input v-model="filters.management_company" clearable placeholder="管理会社" style="width: 150px" />
        <el-select v-model="filters.payment_status" clearable placeholder="支払状態" style="width: 130px">
          <el-option v-for="o in PAYMENT_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="filters.transfer_status" clearable placeholder="振込状態" style="width: 130px">
          <el-option v-for="o in TRANSFER_FILTER_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" format="YYYY-MM-DD" unlink-panels
                        start-placeholder="取引日（開始）" end-placeholder="取引日（終了）" style="width: 260px; flex-grow: 0" />
        <el-select v-model="filters.transaction_type" clearable placeholder="取引種別" style="width: 150px">
          <el-option v-for="o in TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="filters.archive_status" placeholder="保存状態" style="width: 125px">
          <el-option label="利用中" value="active" /><el-option label="アーカイブ" value="archived" /><el-option label="すべて" value="all" />
        </el-select>
        <el-input v-model="filters.keyword" clearable placeholder="番号・当事者・物件・部屋・備考" style="width: 220px" @keyup.enter="fetchRows(1)" />
        <el-checkbox v-model="filters.missing">要補充のみ</el-checkbox>
        <el-button type="primary" @click="fetchRows(1)">検索</el-button>
        <el-button @click="resetFilters">リセット</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <div v-if="canBulk" class="bulk-bar">
        <span class="bulk-count">
          <template v-if="filterSelection">絞り込み結果の全 {{ filterSelection.count }} 件を選択中（利用中のみ）</template>
          <template v-else>{{ selectedRows.length }} 件を選択中</template>
        </span>
        <el-button link type="primary" :loading="selectingAll" :disabled="!total" @click="selectAllFiltered">絞り込み結果をすべて選択</el-button>
        <el-button link :disabled="!targetCount" @click="clearSelection">選択解除</el-button>
        <span class="bulk-actions">
          <el-button :disabled="!targetCount" :loading="preparingBulk" @click="openBulk()">一括変更</el-button>
          <el-button type="success" plain :disabled="!targetCount || preparingBulk" @click="openBulk('settled')">完了にする</el-button>
        </span>
      </div>
      <el-table ref="tableRef" v-loading="loading" :data="rows" stripe row-key="id" @row-click="openRow"
                @selection-change="onSelectionChange">
        <el-table-column v-if="canBulk" type="selection" width="44" reserve-selection
                         :selectable="(row: RealEstateTransaction) => !row.is_archived" />
        <el-table-column prop="transaction_number" label="番号" width="150" />
        <el-table-column label="当事者" min-width="130"><template #default="{ row }">{{ row.party_name }}</template></el-table-column>
        <el-table-column label="物件" min-width="170">
          <template #default="{ row }">{{ row.property_name }}<span v-if="row.room_number"> {{ row.room_number }}</span></template>
        </el-table-column>
        <el-table-column label="管理会社" min-width="120"><template #default="{ row }">{{ row.management_company_name || '-' }}</template></el-table-column>
        <el-table-column label="担当" width="110"><template #default="{ row }">{{ row.responsible_name || '-' }}</template></el-table-column>
        <el-table-column label="種別・段階" width="140">
          <template #default="{ row }">
            <el-tag size="small" :type="row.transaction_type === 'sale' ? 'warning' : 'info'">{{ row.transaction_type_display }}</el-tag>
            {{ row.stage_display }}
          </template>
        </el-table-column>
        <el-table-column label="取引日" width="105"><template #default="{ row }">{{ row.transaction_date ? formatDate(row.transaction_date) : '-' }}</template></el-table-column>
        <el-table-column label="仲介・広告" width="150" align="right">
          <template #default="{ row }">{{ yen(row.brokerage_fee) }} / {{ yen(row.advertising_fee) }}</template>
        </el-table-column>
        <el-table-column label="支払・振込" width="130">
          <template #default="{ row }">{{ row.payment_status_display }} / {{ row.transfer_status_display }}</template>
        </el-table-column>
        <el-table-column label="要補充・台帳" min-width="170">
          <template #default="{ row }">
            <el-tag v-for="m in row.missing_items" :key="m" size="small" type="warning" class="tag">{{ m }}</el-tag>
            <el-tag v-if="row.ledger_locked" size="small" type="success" class="tag">台帳ロック</el-tag>
            <el-tag v-else-if="row.has_ledger" size="small" class="tag">台帳あり</el-tag>
            <el-tag v-if="row.is_archived" size="small" type="info" class="tag">アーカイブ</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination layout="prev, pager, next" :current-page="page" :page-size="20" :total="total" @current-change="loadRows" />
      </div>
    </el-card>

    <el-dialog v-model="bulkVisible" title="不動産記録の一括変更" width="560px">
      <el-alert type="info" :closable="false" show-icon class="bulk-alert">
        <template #title>対象：{{ bulkTarget?.count ?? 0 }} 件（利用中の記録のみ）</template>
        <div>条件：{{ bulkTarget?.filter_summary.join(' / ') }}</div>
        <div>チェックした項目だけを変更します。その他の項目は変わりません。</div>
      </el-alert>
      <div class="bulk-field">
        <el-checkbox v-model="bulkForm.enabled.stage">段階</el-checkbox>
        <el-select v-model="bulkForm.stage" :disabled="!bulkForm.enabled.stage" placeholder="変更後の段階" style="width: 220px">
          <el-option v-for="o in STAGE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </div>
      <div class="bulk-field">
        <el-checkbox v-model="bulkForm.enabled.responsible_name">担当者</el-checkbox>
        <el-autocomplete v-model="bulkForm.responsible_name" :fetch-suggestions="queryResponsible" clearable
                         :disabled="!bulkForm.enabled.responsible_name || bulkForm.clear.responsible_name"
                         placeholder="自由入力（候補以外も可）" style="width: 220px" />
        <el-checkbox v-model="bulkForm.clear.responsible_name" :disabled="!bulkForm.enabled.responsible_name">空欄にする</el-checkbox>
      </div>
      <div class="bulk-field">
        <el-checkbox v-model="bulkForm.enabled.transaction_date">取引日</el-checkbox>
        <el-date-picker v-model="bulkForm.transaction_date" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD"
                        :disabled="!bulkForm.enabled.transaction_date || bulkForm.clear.transaction_date"
                        placeholder="YYYY-MM-DD" style="width: 220px; flex-grow: 0" />
        <el-checkbox v-model="bulkForm.clear.transaction_date" :disabled="!bulkForm.enabled.transaction_date">空欄にする</el-checkbox>
      </div>
      <p class="sub">取引日を変更しても法定台帳は変わりません。台帳の修正が必要な場合は、各記録の画面で更正してください。</p>
      <template #footer>
        <el-button @click="bulkVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="bulkSaving" @click="submitBulk">確認へ進む</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" title="不動産取引を登録" width="620px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="顧客・当事者" prop="party_name">
            <el-input v-model="form.party_name" placeholder="氏名・名称（軽量入力）" />
          </el-form-item>
          <el-form-item label="顧客主档（任意・自動では結び付けません）">
            <RemoteCustomerSelect v-model="form.customer" clearable />
          </el-form-item>
          <el-form-item label="物件名" prop="property_name"><el-input v-model="form.property_name" /></el-form-item>
          <el-form-item label="部屋番号"><el-input v-model="form.room_number" /></el-form-item>
          <el-form-item label="管理会社"><el-input v-model="form.management_company_name" /></el-form-item>
          <el-form-item label="担当">
            <el-autocomplete v-model="form.responsible_name" :fetch-suggestions="queryResponsible" clearable
                             placeholder="自由入力（候補以外も可）" style="width: 100%" />
          </el-form-item>
          <el-form-item label="取引種別">
            <el-radio-group v-model="form.transaction_type">
              <el-radio value="rental">賃貸</el-radio>
              <el-radio value="sale">売買（記録のみ）</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="現在の段階">
            <el-select v-model="form.stage" style="width: 100%">
              <el-option v-for="o in STAGE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="saving" @click="submit">登録して開く</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.sub {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin: 4px 0 0;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-card {
  margin-bottom: 12px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tag {
  margin: 0 4px 2px 0;
}

.bulk-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 10px;
}

.bulk-count {
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.bulk-actions {
  margin-left: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.bulk-actions .el-button + .el-button {
  margin-left: 0;
}

.bulk-alert {
  margin-bottom: 14px;
}

.bulk-field {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 12px;
}

.bulk-field > .el-checkbox:first-child {
  width: 84px;
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
