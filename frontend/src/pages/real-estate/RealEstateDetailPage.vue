<script setup lang="ts">
// 不動産の単件ワークベンチ。区画：物件・当事者・金額・ファイル・法定台帳・会計参照・内部利益配分・監査記録。
// 編集ボタンの表示は目安で、可否は後端が判定する（担当外は 403）。
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '../../api/realEstate'
import { listEmployees } from '../../api/employees'
import RemoteCompanySelect from '../../components/RemoteCompanySelect.vue'
import RemoteCustomerSelect from '../../components/RemoteCustomerSelect.vue'
import { useAuthStore } from '../../stores/auth'
import type { Employee } from '../../types/api'
import type {
  AuditRow, LedgerCorrection, LegalLedger, ProfitDistribution, RealEstateAccountingLink, RealEstateFile,
  RealEstateTransaction, TransactionParty,
} from '../../types/realEstate'
import {
  FILE_KIND_OPTIONS, LEDGER_FORM_OPTIONS, PARTY_ROLE_OPTIONS, PAYMENT_OPTIONS, STAGE_OPTIONS, TRANSFER_OPTIONS, TYPE_OPTIONS,
} from '../../types/realEstate'
import { formatDate, formatDateTime } from '../../utils/date'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const id = computed(() => Number(route.params.id))
const tx = ref<RealEstateTransaction | null>(null)
const employees = ref<Employee[]>([])
const activeTab = ref('overview')
const loading = ref(false)

const canEdit = computed(() => Boolean(tx.value) && (auth.can('real_estate.real_estate_change_all')
  || (tx.value!.responsible_employee != null && tx.value!.responsible_employee === auth.user?.employee_id)))
const canManageLedger = computed(() => auth.can('real_estate.manage_legal_ledger'))
const canProfit = computed(() => auth.can('real_estate.manage_profit_distribution'))
const canIncome = computed(() => auth.can('accounting.use_income'))
const canVoucher = computed(() => auth.can('accounting.use_voucher'))

const errText = (error: unknown, fallback: string) => {
  const r = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
  if (r?.status === 403) return typeof r.data?.detail === 'string' ? r.data.detail : 'この操作の権限がありません。'
  const d = r?.data
  if (d && typeof d.detail === 'string') return d.detail
  const first = d ? Object.values(d)[0] : null
  return Array.isArray(first) && typeof first[0] === 'string' ? first[0] : typeof first === 'string' ? first : fallback
}
const yen = (v: string | number | null | undefined) => (v === null || v === undefined || v === '' ? '-' : `￥${Number(v).toLocaleString()}`)

// --- 概要（物件・金額・状態） ---
const editVisible = ref(false)
const edit = reactive<Record<string, unknown>>({})
const EDIT_FIELDS = [
  'party_name', 'customer', 'property_name', 'room_number', 'property_address', 'property_kind', 'area_sqm',
  'management_company_name', 'management_company', 'responsible_employee', 'transaction_type', 'stage', 'transaction_date',
  'rent_or_price', 'brokerage_fee', 'advertising_fee', 'handling_fee', 'payment_status', 'payment_date', 'transfer_status',
  'note',
] as const
const openEdit = () => {
  if (!tx.value) return
  for (const f of EDIT_FIELDS) edit[f] = (tx.value as unknown as Record<string, unknown>)[f] ?? null
  editVisible.value = true
}
const saveEdit = async () => {
  if (!tx.value) return
  const payload: Record<string, unknown> = {}
  for (const f of EDIT_FIELDS) payload[f] = edit[f] === '' && !['note', 'room_number', 'property_address', 'property_kind', 'management_company_name', 'payment_status', 'transfer_status', 'party_name', 'property_name'].includes(f) ? null : edit[f]
  try {
    tx.value = await api.updateTransaction(tx.value.id, payload)
    editVisible.value = false
    ElMessage.success('保存しました。')
  } catch (error) {
    ElMessage.error(errText(error, '保存できませんでした。'))
  }
}
const changeStage = async (stage: string) => {
  if (!tx.value) return
  try {
    tx.value = await api.updateTransaction(tx.value.id, { stage: stage as RealEstateTransaction['stage'] })
    ElMessage.success('段階を変更しました。')
  } catch (error) {
    ElMessage.error(errText(error, '変更できませんでした。'))
  }
}

// --- 当事者 ---
const parties = ref<TransactionParty[]>([])
const partyVisible = ref(false)
const partyForm = reactive<Partial<TransactionParty>>({})
const openParty = (row?: TransactionParty) => {
  Object.assign(partyForm, { id: undefined, role: 'lessor', name: '', address: '', license_number: '', customer: null, company: null, note: '' }, row ?? {})
  partyVisible.value = true
}
const saveParty = async () => {
  try {
    await api.saveParty(partyForm.id ?? null, { ...partyForm, transaction: id.value })
    partyVisible.value = false
    parties.value = await api.listParties(id.value)
  } catch (error) {
    ElMessage.error(errText(error, '保存できませんでした。'))
  }
}
const removeParty = async (row: TransactionParty) => {
  try {
    await ElMessageBox.confirm(`${row.role_display}「${row.name}」を削除しますか？`, '確認', { type: 'warning' })
  } catch { return }
  try {
    await api.deleteParty(row.id)
    parties.value = await api.listParties(id.value)
  } catch (error) {
    ElMessage.error(errText(error, '削除できませんでした。'))
  }
}

// --- 法定台帳 ---
const ledger = ref<LegalLedger | null>(null)
const corrections = ref<LedgerCorrection[]>([])
const ledgerForm = reactive<Record<string, unknown>>({})
const LEDGER_FIELDS = ['transaction_form', 'transaction_type', 'property_location', 'property_name', 'room_number', 'area_sqm',
  'building_outline', 'rent_or_price', 'remuneration', 'advertising_fee', 'handling_fee', 'special_terms', 'contract_date'] as const
const LEDGER_LABELS: Record<string, string> = {
  transaction_form: '取引態様', transaction_type: '取引種別', property_location: '所在地', property_name: '物件名',
  room_number: '部屋番号', area_sqm: '面積㎡', building_outline: '建物の概要', rent_or_price: '賃料・価格', remuneration: '報酬',
  advertising_fee: '広告料', handling_fee: '手数料', special_terms: '特約', contract_date: '取引日',
}
const syncLedgerForm = () => {
  if (!ledger.value) return
  for (const f of LEDGER_FIELDS) ledgerForm[f] = (ledger.value as unknown as Record<string, unknown>)[f] ?? null
}
const loadLedger = async () => {
  ledger.value = await api.getLedgerForTransaction(id.value)
  syncLedgerForm()
  corrections.value = ledger.value ? await api.listCorrections(ledger.value.id) : []
}
const createLedger = async () => {
  try {
    ledger.value = await api.ensureLedger(id.value)
    syncLedgerForm()
    ElMessage.success('取引の内容から台帳を作成しました。')
  } catch (error) {
    ElMessage.error(errText(error, '台帳を作成できませんでした。'))
  }
}
const ledgerPayload = () => Object.fromEntries(LEDGER_FIELDS.map((f) => [f, ledgerForm[f] === '' && !['property_location', 'property_name', 'room_number', 'building_outline', 'special_terms'].includes(f) ? null : ledgerForm[f]]))
const saveLedger = async () => {
  if (!ledger.value) return
  try {
    ledger.value = await api.updateLedger(ledger.value.id, ledgerPayload() as Partial<LegalLedger>)
    syncLedgerForm()
    ElMessage.success('台帳を保存しました。')
  } catch (error) {
    ElMessage.error(errText(error, '保存できませんでした。'))
  }
}
const lock = async () => {
  if (!ledger.value) return
  try {
    await ElMessageBox.confirm('ロック後は直接変更できず、更正（理由・履歴付き）だけになります。ロックしますか？', '台帳のロック', { type: 'warning' })
  } catch { return }
  try {
    ledger.value = await api.lockLedger(ledger.value.id)
    tx.value = await api.getTransaction(id.value)
    ElMessage.success('台帳をロックしました。')
  } catch (error) {
    ElMessage.error(errText(error, 'ロックできませんでした。'))
  }
}
const correctionVisible = ref(false)
const correctionReason = ref('')
const openCorrection = () => {
  syncLedgerForm()
  correctionReason.value = ''
  correctionVisible.value = true
}
const submitCorrection = async () => {
  if (!ledger.value) return
  const current = ledger.value as unknown as Record<string, unknown>
  const payload = ledgerPayload()
  const changes = Object.fromEntries(Object.entries(payload).filter(([k, v]) => String(v ?? '') !== String(current[k] ?? '')))
  if (!Object.keys(changes).length) return ElMessage.warning('変更がありません。')
  try {
    ledger.value = await api.correctLedger(ledger.value.id, changes, correctionReason.value)
    corrections.value = await api.listCorrections(ledger.value.id)
    correctionVisible.value = false
    ElMessage.success(`更正しました（第 ${ledger.value.version} 版）。`)
  } catch (error) {
    ElMessage.error(errText(error, '更正できませんでした。'))
  }
}
const toggleHold = async () => {
  if (!ledger.value) return
  let reason = ''
  if (!ledger.value.legal_hold) {
    try {
      reason = (await ElMessageBox.prompt('legal hold（保存延長）の理由', 'legal hold', { inputPattern: /\S/, inputErrorMessage: '理由を入力してください' })).value
    } catch { return }
  }
  try {
    ledger.value = await api.setLegalHold(ledger.value.id, !ledger.value.legal_hold, reason)
  } catch (error) {
    ElMessage.error(errText(error, '変更できませんでした。'))
  }
}
const printLedger = () => window.print()

// --- ファイル ---
const files = ref<RealEstateFile[]>([])
const fileForm = reactive({ kind: 'contract', title: '', file: null as File | null })
const uploading = ref(false)
const upload = async () => {
  if (!fileForm.file || !fileForm.title) return ElMessage.warning('タイトルとファイルを入力してください。')
  uploading.value = true
  try {
    await api.uploadFile(id.value, fileForm.kind, fileForm.title, fileForm.file)
    Object.assign(fileForm, { title: '', file: null })
    files.value = await api.listFiles(id.value)
    ElMessage.success('登録しました。')
  } catch (error) {
    ElMessage.error(errText(error, '登録できませんでした。'))
  } finally {
    uploading.value = false
  }
}
const download = async (row: RealEstateFile) => {
  try {
    const { blob } = await api.downloadFile(row.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = row.file_name || `${row.title}`
    a.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(errText(error, 'ダウンロードできませんでした。'))
  }
}

// --- 会計参照 ---
const links = ref<RealEstateAccountingLink[]>([])
const linkForm = reactive({ income_source: '' as string | number, voucher: '' as string | number, note: '' })
const addLink = async () => {
  try {
    await api.createAccountingLink({ transaction: id.value, income_source: linkForm.income_source ? Number(linkForm.income_source) : null,
      voucher: linkForm.voucher ? Number(linkForm.voucher) : null, note: linkForm.note })
    Object.assign(linkForm, { income_source: '', voucher: '', note: '' })
    links.value = await api.listAccountingLinks(id.value)
  } catch (error) {
    ElMessage.error(errText(error, '参照を追加できませんでした。'))
  }
}
const removeLink = async (row: RealEstateAccountingLink) => {
  try {
    await api.deleteAccountingLink(row.id)
    links.value = await api.listAccountingLinks(id.value)
  } catch (error) {
    ElMessage.error(errText(error, '削除できませんでした。'))
  }
}

// --- 内部利益配分（専用権限。閲覧は監査に残る。法定台帳には含まれない） ---
const profits = ref<ProfitDistribution[]>([])
const profitVisible = ref(false)
const profitForm = reactive<Partial<ProfitDistribution>>({})
const revenueBase = computed(() => Number(tx.value?.brokerage_fee || 0) + Number(tx.value?.advertising_fee || 0))
const profitPreview = computed(() => profitForm.method === 'fixed'
  ? Number(profitForm.fixed_amount || 0)
  : Math.round(Number(profitForm.base_amount || 0) * Number(profitForm.ratio_percent || 0) / 100))
const openProfit = (row?: ProfitDistribution) => {
  Object.assign(profitForm, { id: undefined, recipient_name: '', method: 'ratio', base_amount: String(revenueBase.value),
    ratio_percent: '', fixed_amount: '', note: '' }, row ?? {})
  profitVisible.value = true
}
const saveProfit = async () => {
  const payload = { ...profitForm, transaction: id.value } as Record<string, unknown>
  if (payload.method === 'fixed') payload.ratio_percent = null
  else payload.fixed_amount = null
  for (const key of ['id', 'amount', 'status', 'status_display', 'method_display', 'settled_at', 'transaction_number']) delete payload[key]
  try {
    await api.saveProfit(profitForm.id ?? null, payload as Partial<ProfitDistribution>)
    profitVisible.value = false
    profits.value = await api.listProfits(id.value)
  } catch (error) {
    ElMessage.error(errText(error, '保存できませんでした。'))
  }
}
const settle = async (row: ProfitDistribution) => {
  try {
    await api.settleProfit(row.id)
    profits.value = await api.listProfits(id.value)
  } catch (error) {
    ElMessage.error(errText(error, '結算できませんでした。'))
  }
}
const reopen = async (row: ProfitDistribution) => {
  let reason = ''
  try {
    reason = (await ElMessageBox.prompt('草稿に戻す理由', '草稿に戻す', { inputPattern: /\S/, inputErrorMessage: '理由を入力してください' })).value
  } catch { return }
  try {
    await api.reopenProfit(row.id, reason)
    profits.value = await api.listProfits(id.value)
  } catch (error) {
    ElMessage.error(errText(error, '変更できませんでした。'))
  }
}

// --- 監査記録 ---
const auditRows = ref<AuditRow[]>([])
const loadAudit = async () => {
  try {
    auditRows.value = await api.getTransactionAuditLog(id.value)
  } catch {
    auditRows.value = []
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    tx.value = await api.getTransaction(id.value)
    const [p, f, l] = await Promise.all([api.listParties(id.value), api.listFiles(id.value), api.listAccountingLinks(id.value)])
    parties.value = p
    files.value = f
    links.value = l
    await loadLedger()
    if (canProfit.value) profits.value = await api.listProfits(id.value)
  } catch (error) {
    ElMessage.error(errText(error, '記録を取得できませんでした。'))
  } finally {
    loading.value = false
  }
}

const onTab = (name: string | number) => {
  if (name === 'audit') loadAudit()
}

onMounted(async () => {
  await loadAll()
  try {
    employees.value = (await listEmployees({ page_size: 200 })).results
  } catch {
    employees.value = []
  }
})
</script>

<template>
  <section v-loading="loading" class="page">
    <div class="page-header page-header-row">
      <div>
        <el-button text @click="router.push('/real-estate')">← 一覧</el-button>
        <h1 v-if="tx">{{ tx.transaction_number }}　{{ tx.property_name }} {{ tx.room_number }}</h1>
        <div v-if="tx" class="header-tags">
          <el-tag :type="tx.transaction_type === 'sale' ? 'warning' : 'info'">{{ tx.transaction_type_display }}</el-tag>
          <span>当事者：{{ tx.party_name }}</span>
          <span>担当：{{ tx.responsible_employee_name || '-' }}</span>
          <el-tag v-for="m in tx.missing_items" :key="m" size="small" type="warning">要補充：{{ m }}</el-tag>
        </div>
      </div>
      <div v-if="tx" class="header-actions">
        <el-select :model-value="tx.stage" :disabled="!canEdit" style="width: 140px" @change="changeStage">
          <el-option v-for="o in STAGE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-button v-if="canEdit" type="primary" @click="openEdit">基本情報を編集</el-button>
      </div>
    </div>

    <el-alert v-if="tx && !canEdit" type="info" :closable="false" show-icon class="page-alert"
              title="閲覧のみ（担当外の記録です）。変更は担当者または全件変更の権限者が行います。" />
    <el-alert v-if="tx?.transaction_type === 'sale'" type="warning" :closable="false" show-icon class="page-alert"
              title="売買は記録のみです（第 1 版では売買の業務フロー・10 年保存の運用は有効にしていません）。" />

    <el-tabs v-if="tx" v-model="activeTab" @tab-change="onTab">
      <el-tab-pane label="物件・金額" name="overview">
        <div class="grid-2">
          <el-card shadow="never">
            <template #header>物件</template>
            <dl class="fields">
              <div><dt>物件名</dt><dd>{{ tx.property_name }}</dd></div>
              <div><dt>部屋番号</dt><dd>{{ tx.room_number || '-' }}</dd></div>
              <div><dt>所在地</dt><dd>{{ tx.property_address || '-' }}</dd></div>
              <div><dt>種類</dt><dd>{{ tx.property_kind || '-' }}</dd></div>
              <div><dt>面積</dt><dd>{{ tx.area_sqm ? `${tx.area_sqm} ㎡` : '-' }}</dd></div>
              <div><dt>管理会社</dt><dd>{{ tx.management_company_name || '-' }}<span v-if="tx.management_company_ref_name" class="sub">（主档：{{ tx.management_company_ref_name }}）</span></dd></div>
              <div><dt>顧客主档</dt><dd>{{ tx.customer_name || '未参照' }}</dd></div>
              <div><dt>取引日</dt><dd>{{ tx.transaction_date ? formatDate(tx.transaction_date) : '-' }}</dd></div>
            </dl>
          </el-card>
          <el-card shadow="never">
            <template #header>金額・支払</template>
            <dl class="fields">
              <div><dt>賃料・価格</dt><dd>{{ yen(tx.rent_or_price) }}</dd></div>
              <div><dt>仲介手数料（報酬）</dt><dd>{{ yen(tx.brokerage_fee) }}</dd></div>
              <div><dt>広告料</dt><dd>{{ yen(tx.advertising_fee) }}</dd></div>
              <div><dt>手数料</dt><dd>{{ yen(tx.handling_fee) }}</dd></div>
              <div><dt>支払状態</dt><dd>{{ tx.payment_status_display }}<span v-if="tx.payment_date">（{{ formatDate(tx.payment_date) }}）</span></dd></div>
              <div><dt>振込状態</dt><dd>{{ tx.transfer_status_display }}</dd></div>
            </dl>
            <div class="source-amounts">
              <div class="sub">取込元の請求金額（意味の確定まで合算しない）</div>
              <dl class="fields">
                <div><dt>向SUNRISE請求書金額</dt><dd>{{ yen(tx.source_billed_to_sunrise_amount) }}</dd></div>
                <div><dt>向客人請求金額</dt><dd>{{ yen(tx.source_billed_to_client_amount) }}</dd></div>
                <div><dt>SUNRISE請求書金額</dt><dd>{{ yen(tx.source_sunrise_invoice_amount) }}</dd></div>
              </dl>
            </div>
          </el-card>
        </div>
        <el-card v-if="tx.note" shadow="never" class="mt"><template #header>備考</template><div class="pre">{{ tx.note }}</div></el-card>
      </el-tab-pane>

      <el-tab-pane :label="`当事者（${parties.length}）`" name="parties">
        <el-card shadow="never">
          <el-button v-if="canEdit && !ledger?.is_locked" size="small" type="primary" class="mb" @click="openParty()">当事者を追加</el-button>
          <el-table :data="parties" size="small" empty-text="当事者は未登録です（台帳には各当事者と代理・媒介業者が必要）">
            <el-table-column prop="role_display" label="立場" width="120" />
            <el-table-column prop="name" label="氏名・名称" min-width="150" />
            <el-table-column prop="address" label="住所" min-width="200" />
            <el-table-column prop="license_number" label="免許番号" width="140" />
            <el-table-column label="主档参照" width="160"><template #default="{ row }">{{ row.customer_name || row.company_name || '-' }}</template></el-table-column>
            <el-table-column v-if="canEdit && !ledger?.is_locked" width="120">
              <template #default="{ row }">
                <el-button text size="small" @click="openParty(row)">編集</el-button>
                <el-button text size="small" type="danger" @click="removeParty(row)">削除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="法定台帳" name="ledger">
        <el-card shadow="never" class="ledger-print">
          <template v-if="!ledger">
            <p class="sub">まだ台帳がありません。取引の内容（物件・金額・取引日）から台帳の下書きを作成できます。</p>
            <el-button v-if="canEdit" type="primary" @click="createLedger">台帳を作成</el-button>
          </template>
          <template v-else>
            <div class="ledger-head">
              <el-tag v-if="ledger.is_locked" type="success">ロック済み（第 {{ ledger.version }} 版）</el-tag>
              <el-tag v-else>編集中</el-tag>
              <span>事業年度：{{ ledger.fiscal_year ?? '-' }}<span v-if="ledger.fiscal_year_end_month">（{{ ledger.fiscal_year_end_month }} 月決算・快照）</span><span v-if="ledger.fiscal_year_closed_at">（締め済み）</span></span>
              <span>保存：{{ ledger.retention_years }} 年・期限 {{ ledger.retention_until ? formatDate(ledger.retention_until) : '-' }}</span>
              <el-tag v-if="ledger.retention_due" type="danger">到期復核（自動削除はしません）</el-tag>
              <el-tag v-if="ledger.legal_hold" type="warning">legal hold：{{ ledger.legal_hold_reason }}</el-tag>
              <div class="grow" />
              <el-button size="small" @click="printLedger">印刷</el-button>
              <template v-if="canManageLedger">
                <el-button v-if="!ledger.is_locked" size="small" type="warning" @click="lock">ロック</el-button>
                <el-button v-else size="small" type="warning" @click="openCorrection">更正</el-button>
                <el-button size="small" @click="toggleHold">{{ ledger.legal_hold ? 'legal hold 解除' : 'legal hold' }}</el-button>
              </template>
            </div>
            <el-form label-position="top" :disabled="ledger.is_locked || !canEdit">
              <div class="form-grid">
                <el-form-item label="取引態様">
                  <el-select v-model="ledgerForm.transaction_form" style="width: 100%"><el-option v-for="o in LEDGER_FORM_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select>
                </el-form-item>
                <el-form-item label="取引種別">
                  <el-select v-model="ledgerForm.transaction_type" style="width: 100%"><el-option v-for="o in TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select>
                </el-form-item>
                <el-form-item label="所在地"><el-input v-model="ledgerForm.property_location" /></el-form-item>
                <el-form-item label="物件名"><el-input v-model="ledgerForm.property_name" /></el-form-item>
                <el-form-item label="部屋番号"><el-input v-model="ledgerForm.room_number" /></el-form-item>
                <el-form-item label="面積（㎡）"><el-input v-model="ledgerForm.area_sqm" inputmode="decimal" /></el-form-item>
                <el-form-item label="賃料・価格"><el-input v-model="ledgerForm.rent_or_price" inputmode="numeric" /></el-form-item>
                <el-form-item label="報酬"><el-input v-model="ledgerForm.remuneration" inputmode="numeric" /></el-form-item>
                <el-form-item label="広告料"><el-input v-model="ledgerForm.advertising_fee" inputmode="numeric" /></el-form-item>
                <el-form-item label="手数料"><el-input v-model="ledgerForm.handling_fee" inputmode="numeric" /></el-form-item>
                <el-form-item label="取引（契約）日"><el-date-picker v-model="ledgerForm.contract_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
              </div>
              <el-form-item label="建物の概要"><el-input v-model="ledgerForm.building_outline" type="textarea" :rows="2" /></el-form-item>
              <el-form-item label="特約"><el-input v-model="ledgerForm.special_terms" type="textarea" :rows="3" /></el-form-item>
            </el-form>
            <div class="sub">各当事者・代理／媒介業者は「当事者」区画の内容が台帳に含まれます（{{ ledger.parties.length }} 名）。</div>
            <el-button v-if="!ledger.is_locked && canEdit" type="primary" class="mt" @click="saveLedger">台帳を保存</el-button>
            <template v-if="corrections.length">
              <h4 class="mt">更正履歴</h4>
              <el-table :data="corrections" size="small">
                <el-table-column label="日時" width="160"><template #default="{ row }">{{ formatDateTime(row.corrected_at) }}</template></el-table-column>
                <el-table-column prop="version" label="版" width="60" />
                <el-table-column label="変更" min-width="260">
                  <template #default="{ row }">
                    <div v-for="(pair, key) in row.changes" :key="key">{{ LEDGER_LABELS[key] || key }}：{{ pair[0] ?? '（空）' }} → {{ pair[1] ?? '（空）' }}</div>
                  </template>
                </el-table-column>
                <el-table-column prop="reason" label="理由" min-width="160" />
                <el-table-column prop="corrected_by_name" label="実行者" width="100" />
              </el-table>
            </template>
          </template>
        </el-card>
      </el-tab-pane>

      <el-tab-pane :label="`ファイル（${files.length}）`" name="files">
        <el-card shadow="never">
          <div v-if="canEdit" class="upload-row">
            <el-select v-model="fileForm.kind" style="width: 150px"><el-option v-for="o in FILE_KIND_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select>
            <el-input v-model="fileForm.title" placeholder="タイトル" style="width: 200px" />
            <input type="file" @change="(e: Event) => (fileForm.file = (e.target as HTMLInputElement).files?.[0] ?? null)" />
            <el-button type="primary" :loading="uploading" @click="upload">登録</el-button>
          </div>
          <el-table :data="files" size="small" empty-text="ファイルはありません">
            <el-table-column prop="kind_display" label="種類" width="130" />
            <el-table-column prop="title" label="タイトル" min-width="160" />
            <el-table-column label="ファイル" min-width="180"><template #default="{ row }">{{ row.file_name || (row.document_title ? `案件書類：${row.document_title}` : '-') }}</template></el-table-column>
            <el-table-column prop="uploaded_by_name" label="登録者" width="100" />
            <el-table-column label="日時" width="150"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
            <el-table-column width="110"><template #default="{ row }"><el-button v-if="row.has_file" text size="small" type="primary" @click="download(row)">ダウンロード</el-button></template></el-table-column>
          </el-table>
          <p class="sub">ダウンロードは権限確認と監査を通る受保護ダウンロードです。</p>
        </el-card>
      </el-tab-pane>

      <el-tab-pane :label="`会計参照（${links.length}）`" name="accounting">
        <el-card shadow="never">
          <p class="sub">会計の記録を参照するだけで、会計データは複製しません。内容は会計の権限がある人にだけ表示されます。</p>
          <div v-if="canEdit && (canIncome || canVoucher)" class="upload-row">
            <el-input v-if="canIncome" v-model="linkForm.income_source" placeholder="収入 ID" style="width: 120px" />
            <el-input v-if="canVoucher" v-model="linkForm.voucher" placeholder="請求書・領収書 ID" style="width: 160px" />
            <el-input v-model="linkForm.note" placeholder="備考" style="width: 200px" />
            <el-button type="primary" @click="addLink">参照を追加</el-button>
          </div>
          <el-table :data="links" size="small" empty-text="参照はありません">
            <el-table-column label="収入" min-width="200">
              <template #default="{ row }">
                <template v-if="row.income_summary">{{ row.income_summary.date }} {{ row.income_summary.target }} {{ yen(row.income_summary.amount) }}</template>
                <template v-else-if="row.income_source">（収入 #{{ row.income_source }}・閲覧権限なし）</template>
              </template>
            </el-table-column>
            <el-table-column label="請求書・領収書" min-width="200">
              <template #default="{ row }">
                <template v-if="row.voucher_summary">{{ row.voucher_summary.type }} {{ row.voucher_summary.number }} {{ yen(row.voucher_summary.total) }}</template>
                <template v-else-if="row.voucher">（帳票 #{{ row.voucher }}・閲覧権限なし）</template>
              </template>
            </el-table-column>
            <el-table-column prop="note" label="備考" min-width="140" />
            <el-table-column v-if="canEdit" width="80"><template #default="{ row }"><el-button text size="small" type="danger" @click="removeLink(row)">解除</el-button></template></el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane v-if="canProfit" :label="`内部利益配分（${profits.length}）`" name="profit">
        <el-card shadow="never">
          <el-alert type="warning" :closable="false" show-icon class="mb"
                    title="社内限り：法定台帳には含まれません。閲覧・変更はすべて監査記録に残ります。" />
          <el-button v-if="canEdit" size="small" type="primary" class="mb" @click="openProfit()">配分を追加</el-button>
          <el-table :data="profits" size="small" empty-text="配分はありません">
            <el-table-column prop="recipient_name" label="配分先" min-width="120" />
            <el-table-column label="計算" min-width="170">
              <template #default="{ row }">{{ row.method === 'fixed' ? `固定 ${yen(row.fixed_amount)}` : `${yen(row.base_amount)} × ${row.ratio_percent}%` }}</template>
            </el-table-column>
            <el-table-column label="配分金額" width="120" align="right"><template #default="{ row }">{{ yen(row.amount) }}</template></el-table-column>
            <el-table-column label="状態" width="100"><template #default="{ row }"><el-tag size="small" :type="row.status === 'settled' ? 'success' : 'info'">{{ row.status_display }}</el-tag></template></el-table-column>
            <el-table-column prop="note" label="備考" min-width="140" />
            <el-table-column v-if="canEdit" width="170">
              <template #default="{ row }">
                <template v-if="row.status === 'draft'">
                  <el-button text size="small" @click="openProfit(row)">編集</el-button>
                  <el-button text size="small" type="success" @click="settle(row)">結算</el-button>
                </template>
                <el-button v-else text size="small" @click="reopen(row)">草稿に戻す</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="監査記録" name="audit">
        <el-card shadow="never">
          <el-table :data="auditRows" size="small" empty-text="記録はありません">
            <el-table-column label="日時" width="160"><template #default="{ row }">{{ formatDateTime(row.occurred_at) }}</template></el-table-column>
            <el-table-column prop="user" label="利用者" width="110" />
            <el-table-column prop="action" label="操作" min-width="170" />
            <el-table-column prop="object_type" label="対象" min-width="180" />
            <el-table-column prop="result" label="結果" width="80" />
            <el-table-column prop="reason" label="理由" min-width="140" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="editVisible" title="基本情報を編集" width="760px">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="顧客・当事者"><el-input v-model="edit.party_name as string" /></el-form-item>
          <el-form-item label="顧客主档（任意）"><RemoteCustomerSelect v-model="edit.customer as number | null" clearable /></el-form-item>
          <el-form-item label="物件名"><el-input v-model="edit.property_name as string" /></el-form-item>
          <el-form-item label="部屋番号"><el-input v-model="edit.room_number as string" /></el-form-item>
          <el-form-item label="所在地"><el-input v-model="edit.property_address as string" /></el-form-item>
          <el-form-item label="物件種類"><el-input v-model="edit.property_kind as string" /></el-form-item>
          <el-form-item label="面積（㎡）"><el-input v-model="edit.area_sqm as string" inputmode="decimal" /></el-form-item>
          <el-form-item label="管理会社"><el-input v-model="edit.management_company_name as string" /></el-form-item>
          <el-form-item label="管理会社主档（任意）"><RemoteCompanySelect v-model="edit.management_company as number | null" clearable /></el-form-item>
          <el-form-item label="担当">
            <el-select v-model="edit.responsible_employee" filterable style="width: 100%"><el-option v-for="e in employees" :key="e.id" :label="e.name" :value="e.id" /></el-select>
          </el-form-item>
          <el-form-item label="取引種別">
            <el-select v-model="edit.transaction_type" style="width: 100%"><el-option v-for="o in TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select>
          </el-form-item>
          <el-form-item label="取引日"><el-date-picker v-model="edit.transaction_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
          <el-form-item label="賃料・価格"><el-input v-model="edit.rent_or_price as string" inputmode="numeric" /></el-form-item>
          <el-form-item label="仲介手数料（報酬）"><el-input v-model="edit.brokerage_fee as string" inputmode="numeric" /></el-form-item>
          <el-form-item label="広告料"><el-input v-model="edit.advertising_fee as string" inputmode="numeric" /></el-form-item>
          <el-form-item label="手数料"><el-input v-model="edit.handling_fee as string" inputmode="numeric" /></el-form-item>
          <el-form-item label="支払状態">
            <el-select v-model="edit.payment_status" style="width: 100%"><el-option v-for="o in PAYMENT_OPTIONS" :key="o.value" :label="o.label" :value="o.value === 'unset' ? '' : o.value" /></el-select>
          </el-form-item>
          <el-form-item label="支払日"><el-date-picker v-model="edit.payment_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
          <el-form-item label="振込状態">
            <el-select v-model="edit.transfer_status" style="width: 100%"><el-option v-for="o in TRANSFER_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select>
          </el-form-item>
        </div>
        <el-form-item label="備考"><el-input v-model="edit.note as string" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">キャンセル</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="partyVisible" title="当事者" width="560px">
      <el-form label-position="top">
        <el-form-item label="立場"><el-select v-model="partyForm.role" style="width: 100%"><el-option v-for="o in PARTY_ROLE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select></el-form-item>
        <el-form-item label="氏名・名称"><el-input v-model="partyForm.name" /></el-form-item>
        <el-form-item label="住所"><el-input v-model="partyForm.address" /></el-form-item>
        <el-form-item label="免許番号（宅建業者）"><el-input v-model="partyForm.license_number" /></el-form-item>
        <el-form-item label="顧客主档（任意）"><RemoteCustomerSelect v-model="partyForm.customer" clearable /></el-form-item>
        <el-form-item label="会社主档（任意）"><RemoteCompanySelect v-model="partyForm.company" clearable /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="partyVisible = false">キャンセル</el-button>
        <el-button type="primary" @click="saveParty">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="correctionVisible" title="台帳の更正" width="760px">
      <el-alert type="warning" :closable="false" show-icon class="mb" title="変更した項目と理由が更正履歴と監査記録に残り、版が上がります。" />
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item v-for="f in LEDGER_FIELDS" :key="f" :label="LEDGER_LABELS[f]">
            <el-date-picker v-if="f === 'contract_date'" v-model="ledgerForm[f]" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            <el-select v-else-if="f === 'transaction_form'" v-model="ledgerForm[f]" style="width: 100%"><el-option v-for="o in LEDGER_FORM_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select>
            <el-select v-else-if="f === 'transaction_type'" v-model="ledgerForm[f]" style="width: 100%"><el-option v-for="o in TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" /></el-select>
            <el-input v-else v-model="ledgerForm[f] as string" />
          </el-form-item>
        </div>
        <el-form-item label="更正理由（必須）"><el-input v-model="correctionReason" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="correctionVisible = false">キャンセル</el-button>
        <el-button type="warning" @click="submitCorrection">更正する</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="profitVisible" title="内部利益配分" width="520px">
      <el-form label-position="top">
        <el-form-item label="配分先"><el-input v-model="profitForm.recipient_name" /></el-form-item>
        <el-form-item label="計算方法">
          <el-radio-group v-model="profitForm.method"><el-radio value="ratio">比率</el-radio><el-radio value="fixed">固定金額</el-radio></el-radio-group>
        </el-form-item>
        <template v-if="profitForm.method === 'ratio'">
          <el-form-item label="基準額（初期値：仲介手数料＋広告料）"><el-input v-model="profitForm.base_amount" inputmode="numeric" /></el-form-item>
          <el-form-item label="比率（％）"><el-input v-model="profitForm.ratio_percent as string" inputmode="decimal" /></el-form-item>
        </template>
        <el-form-item v-else label="固定金額"><el-input v-model="profitForm.fixed_amount as string" inputmode="numeric" /></el-form-item>
        <div class="sub">配分金額（自動計算）：{{ yen(profitPreview) }}</div>
        <el-form-item label="備考"><el-input v-model="profitForm.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profitVisible = false">キャンセル</el-button>
        <el-button type="primary" @click="saveProfit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.header-tags,
.header-actions,
.ledger-head,
.upload-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.ledger-head,
.upload-row {
  margin-bottom: 12px;
}

.grow {
  flex: 1;
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr));
  gap: 12px;
}

.fields {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  margin: 0;
}

.fields > div {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 8px;
}

.fields dt {
  color: var(--el-text-color-secondary);
}

.fields dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.source-amounts {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color);
}

.sub {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.mt {
  margin-top: 12px;
}

.mb {
  margin-bottom: 12px;
}

.pre {
  white-space: pre-wrap;
}

@media (max-width: 639px) {
  .fields > div {
    grid-template-columns: minmax(0, 1fr);
    gap: 2px;
  }

  .header-actions {
    width: 100%;
  }

  .upload-row > * {
    width: 100% !important;
  }
}

@media print {
  .ledger-head button {
    display: none;
  }
}
</style>
