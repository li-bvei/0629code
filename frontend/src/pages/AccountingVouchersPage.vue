<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createVoucherItemTemplate,
  createAccountingVoucher,
  deleteAccountingVoucher,
  deleteVoucherItemTemplate,
  downloadAccountingVoucherPdf,
  listVoucherItemTemplates,
  listAccountingVouchers,
  updateAccountingVoucher,
  updateVoucherItemTemplate,
} from '../api/accounting'
import type {
  AccountingVoucher,
  AccountingVoucherLineItem,
  AccountingVoucherPayload,
  AccountingVoucherType,
  VoucherItemTemplate,
} from '../types/accounting'
import { formatDate } from '../utils/date'
import './accounting/accounting.css'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const errorMessage = ref('')
const vouchers = ref<AccountingVoucher[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const editingVoucherId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const selectedBankInfo = ref('')
const voucherItemTemplates = ref<VoucherItemTemplate[]>([])
const itemManagerVisible = ref(false)
const itemManagerLoading = ref(false)
const itemManagerSearch = ref('')
const managedVoucherItemTemplates = ref<VoucherItemTemplate[]>([])
const filters = ref({
  issue_date_from: '',
  issue_date_to: '',
  voucher_type: '',
  recipient_name: '',
  title: '',
  amount_min: '',
  amount_max: '',
  keyword: '',
})
const newItemTemplate = ref({
  name: '',
  default_unit_price: '',
  is_active: true,
  sort_order: 0,
})

const defaultIssuer = {
  issuer_name: 'SUNRISE日晟鴻達株式会社',
  issuer_postal_code: '5430043',
  issuer_address: '大阪府大阪市天王寺区\n勝山４丁目７－３佐々木ビル２階',
  issuer_tel: '06-7650-6385',
  issuer_registration_number: 'T1120001256801',
}

const bankInfoOptions = [
  {
    label: '大阪信用金庫',
    value: 'osaka_shinkin',
    text: '大阪信用金庫　勝山支店\n普通　0178251\n口座名義　サンライズニッセイコウタツ（カ',
  },
  {
    label: 'GMOあおぞらネット銀行',
    value: 'gmo_aozora',
    text: 'GMOあおぞらネット銀行　法人第二営業部\n普通　1667066\n口座名義　サンライズニッセイコウタツ（カ',
  },
  {
    label: '手動入力',
    value: 'manual',
    text: '',
  },
]

const getTodayDate = () => {
  const date = new Date()
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}

const createLineItem = (): AccountingVoucherLineItem => ({
  item_name: '',
  quantity: 1,
  unit_price: '',
  line_total: 0,
})

const voucherForm = ref<AccountingVoucherPayload>({
  voucher_type: 'invoice',
  issue_date: getTodayDate(),
  recipient_name: '',
  recipient_postal_code: '',
  recipient_address: '',
  title: '',
  amount: '',
  tax_amount: 0,
  details: '',
  line_items: [createLineItem()],
  note: '',
  payment_due_date: null,
  payment_method: '',
  ...defaultIssuer,
  bank_info: '',
})

const rules: FormRules<AccountingVoucherPayload> = {
  voucher_type: [{ required: true, message: '帳票種別を選択してください。', trigger: 'change' }],
  issue_date: [{ required: true, message: '発行日を入力してください。', trigger: 'change' }],
}

const getLineTotal = (item: AccountingVoucherLineItem) => {
  return Math.round(Number(item.quantity || 0) * Number(item.unit_price || 0))
}

const lineSubtotal = computed(() => {
  return (voucherForm.value.line_items || []).reduce((sum, item) => sum + getLineTotal(item), 0)
})
const totalAmount = computed(() => lineSubtotal.value)
const taxExcludedAmount = computed(() => Math.round(totalAmount.value / 1.1))
const taxAmount = computed(() => totalAmount.value - taxExcludedAmount.value)
const filteredManagedItemTemplates = computed(() => {
  const keyword = itemManagerSearch.value.trim()
  if (!keyword) return managedVoucherItemTemplates.value
  return managedVoucherItemTemplates.value.filter((item) => item.name.includes(keyword))
})

const formatMoney = (value?: number | string | null) => `￥${Number(value || 0).toLocaleString()}`
const getVoucherTypeLabel = (type: AccountingVoucherType) => (type === 'invoice' ? '請求書' : '領収書')
const getVoucherTypeTag = (type: AccountingVoucherType) => (type === 'invoice' ? 'primary' : 'success')
const getVoucherLineTotal = (item: AccountingVoucherLineItem) => {
  if (item.line_total !== undefined && item.line_total !== null && item.line_total !== '') {
    return Number(item.line_total || 0)
  }
  return Math.round(Number(item.quantity || 0) * Number(item.unit_price || 0))
}
const getVoucherLineItems = (voucher: AccountingVoucher) => {
  if (voucher.line_items?.length) return voucher.line_items
  if (voucher.details) {
    return voucher.details
      .split('\n')
      .filter(Boolean)
      .map((item_name) => ({ item_name, quantity: '', unit_price: '', line_total: '' }))
  }
  return []
}
const getVoucherContentSummary = (voucher: AccountingVoucher) => {
  const items = getVoucherLineItems(voucher)
  if (!items.length) return '-'
  const visible = items.slice(0, 2).map((item) => {
    const name = item.item_name || '-'
    const amount = getVoucherLineTotal(item)
    return amount ? `${name} ${formatMoney(amount)}` : name
  })
  const rest = items.length - visible.length
  return rest > 0 ? `${visible.join('、')}、他${rest}件` : visible.join('、')
}
const getVoucherContentTooltip = (voucher: AccountingVoucher) => {
  const items = getVoucherLineItems(voucher)
  if (!items.length) return '-'
  return items
    .map((item) => {
      const name = item.item_name || '-'
      const unitPrice = item.unit_price !== undefined && item.unit_price !== '' ? formatMoney(item.unit_price) : '-'
      const quantity = item.quantity !== undefined && item.quantity !== '' ? item.quantity : '-'
      const lineTotal = getVoucherLineTotal(item)
      const note = (item as AccountingVoucherLineItem & { note?: string; remarks?: string }).note
        || (item as AccountingVoucherLineItem & { note?: string; remarks?: string }).remarks
        || ''
      return `${name} / 単価 ${unitPrice} / 数量 ${quantity} / 金額 ${formatMoney(lineTotal)}${note ? ` / ${note}` : ''}`
    })
    .join('\n')
}
const summary = computed(() => {
  return vouchers.value.reduce(
    (result, voucher) => {
      result.amount += Number(voucher.amount || 0)
      result.tax += Number(voucher.tax_amount || 0)
      result.total += Number(voucher.total_amount || 0)
      return result
    },
    { count: vouchers.value.length, amount: 0, tax: 0, total: 0 },
  )
})

const extractFilename = (contentDisposition?: string) => {
  if (!contentDisposition) return '帳票.pdf'
  const encoded = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
  if (encoded?.[1]) return decodeURIComponent(encoded[1])
  const plain = contentDisposition.match(/filename="?([^";]+)"?/)
  return plain?.[1] || '帳票.pdf'
}

const fetchVouchers = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listAccountingVouchers({ page, ...filters.value })
    vouchers.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = '帳票一覧の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  fetchVouchers(1)
}

const resetFilters = () => {
  filters.value = {
    issue_date_from: '',
    issue_date_to: '',
    voucher_type: '',
    recipient_name: '',
    title: '',
    amount_min: '',
    amount_max: '',
    keyword: '',
  }
  fetchVouchers(1)
}

const fetchVoucherItemTemplates = async () => {
  try {
    const data = await listVoucherItemTemplates({ page_size: 1000 })
    voucherItemTemplates.value = data.results
  } catch {
    ElMessage.error('常用項目の取得に失敗しました。')
  }
}

const fetchManagedVoucherItemTemplates = async () => {
  itemManagerLoading.value = true
  try {
    const data = await listVoucherItemTemplates({ page_size: 1000, include_inactive: 1 })
    managedVoucherItemTemplates.value = data.results.map((item) => ({ ...item }))
  } catch {
    ElMessage.error('明細項目一覧の取得に失敗しました。')
  } finally {
    itemManagerLoading.value = false
  }
}

const openItemManager = async () => {
  itemManagerVisible.value = true
  await fetchManagedVoucherItemTemplates()
}

const resetNewItemTemplate = () => {
  newItemTemplate.value = {
    name: '',
    default_unit_price: '',
    is_active: true,
    sort_order: 0,
  }
}

const resetForm = () => {
  editingVoucherId.value = null
  voucherForm.value = {
    voucher_type: 'invoice',
    issue_date: getTodayDate(),
    recipient_name: '',
    recipient_postal_code: '',
    recipient_address: '',
    title: '',
    amount: '',
    tax_amount: 0,
    details: '',
    line_items: [createLineItem()],
    note: '',
    payment_due_date: null,
    payment_method: '',
    ...defaultIssuer,
    bank_info: '',
  }
  selectedBankInfo.value = ''
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (voucher: AccountingVoucher) => {
  editingVoucherId.value = voucher.id
  voucherForm.value = {
    voucher_type: voucher.voucher_type,
    issue_date: voucher.issue_date,
    recipient_name: voucher.recipient_name,
    recipient_postal_code: voucher.recipient_postal_code,
    recipient_address: voucher.recipient_address,
    title: voucher.title,
    amount: voucher.amount,
    tax_amount: voucher.tax_amount,
    details: voucher.details,
    line_items: voucher.line_items?.length
      ? voucher.line_items.map((item) => ({ ...item }))
      : [{
          item_name: voucher.title || voucher.details || '',
          quantity: 1,
          unit_price: voucher.amount,
          line_total: voucher.amount,
        }],
    note: voucher.note,
    payment_due_date: voucher.payment_due_date,
    payment_method: voucher.payment_method,
    issuer_name: voucher.issuer_name,
    issuer_postal_code: voucher.issuer_postal_code,
    issuer_address: voucher.issuer_address,
    issuer_tel: voucher.issuer_tel,
    issuer_registration_number: voucher.issuer_registration_number,
    bank_info: voucher.bank_info,
  }
  selectedBankInfo.value = ''
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

const handleBankInfoSelect = (value: string) => {
  const selected = bankInfoOptions.find((option) => option.value === value)
  if (selected && selected.value !== 'manual') {
    voucherForm.value.bank_info = selected.text
  }
}

const findVoucherItemTemplate = (name: string) => {
  return voucherItemTemplates.value.find((template) => template.name === name)
}

const isNewVoucherItemName = (name?: string) => {
  const normalized = (name || '').trim()
  return Boolean(normalized) && !findVoucherItemTemplate(normalized)
}

const handleLineItemNameChange = (item: AccountingVoucherLineItem) => {
  const selected = findVoucherItemTemplate(item.item_name)
  if (!selected?.default_unit_price) return
  if (!Number(item.unit_price || 0)) {
    item.unit_price = selected.default_unit_price
  }
}

const saveVoucherItemTemplate = async (item: AccountingVoucherLineItem) => {
  const name = (item.item_name || '').trim()
  if (!name) return

  const unitPrice = Number(item.unit_price || 0)
  try {
    await createVoucherItemTemplate({
      name,
      default_unit_price: unitPrice > 0 ? unitPrice : null,
      is_active: true,
    })
    await fetchVoucherItemTemplates()
    item.item_name = name
    ElMessage.success('常用項目に追加しました。')
  } catch {
    ElMessage.info('既に登録されています。')
    await fetchVoucherItemTemplates()
  }
}

const normalizeUnitPrice = (value: number | string | null | undefined) => {
  const amount = Number(value || 0)
  return amount > 0 ? amount : null
}

const addManagedItemTemplate = async () => {
  const name = newItemTemplate.value.name.trim()
  if (!name) {
    ElMessage.error('項目名を入力してください。')
    return
  }

  try {
    await createVoucherItemTemplate({
      name,
      default_unit_price: normalizeUnitPrice(newItemTemplate.value.default_unit_price),
      is_active: newItemTemplate.value.is_active,
      sort_order: Number(newItemTemplate.value.sort_order || 0),
    })
    resetNewItemTemplate()
    await fetchManagedVoucherItemTemplates()
    await fetchVoucherItemTemplates()
    ElMessage.success('追加しました。')
  } catch {
    ElMessage.error('明細項目の追加に失敗しました。項目名が重複している可能性があります。')
  }
}

const saveManagedItemTemplate = async (item: VoucherItemTemplate) => {
  const name = item.name.trim()
  if (!name) {
    ElMessage.error('項目名を入力してください。')
    return
  }

  try {
    await updateVoucherItemTemplate(item.id, {
      name,
      default_unit_price: normalizeUnitPrice(item.default_unit_price),
      is_active: item.is_active,
      sort_order: Number(item.sort_order || 0),
    })
    await fetchManagedVoucherItemTemplates()
    await fetchVoucherItemTemplates()
    ElMessage.success('保存しました。')
  } catch {
    ElMessage.error('明細項目の保存に失敗しました。')
  }
}

const confirmDeleteItemTemplate = async (item: VoucherItemTemplate) => {
  try {
    await ElMessageBox.confirm('この明細項目を削除しますか？', '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteVoucherItemTemplate(item.id)
    await fetchManagedVoucherItemTemplates()
    await fetchVoucherItemTemplates()
    ElMessage.success('削除しました。')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('明細項目の削除に失敗しました。')
    }
  }
}

const addLineItem = () => {
  voucherForm.value.line_items = [...(voucherForm.value.line_items || []), createLineItem()]
}

const removeLineItem = (index: number) => {
  const items = [...(voucherForm.value.line_items || [])]
  items.splice(index, 1)
  voucherForm.value.line_items = items.length ? items : [createLineItem()]
}

const normalizeLineItems = () => {
  return (voucherForm.value.line_items || [])
    .filter((item) => item.item_name || item.quantity || item.unit_price)
    .map((item) => ({
      item_name: item.item_name || '',
      quantity: Number(item.quantity || 0),
      unit_price: Number(item.unit_price || 0),
      line_total: getLineTotal(item),
    }))
}

const buildPayload = () => {
  const lineItems = normalizeLineItems()
  const payload = {
    ...voucherForm.value,
    line_items: lineItems,
    details: lineItems.map((item) => item.item_name).filter(Boolean).join('\n'),
    amount: taxExcludedAmount.value,
    tax_amount: taxAmount.value,
  }
  if (payload.voucher_type === 'invoice') {
    payload.payment_method = ''
  } else {
    payload.payment_due_date = null
    payload.bank_info = ''
  }
  return payload
}

const submitVoucher = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  const lineItems = normalizeLineItems()
  if (!lineItems.length || lineItems.some((item) => !item.item_name)) {
    ElMessage.error('明細の項目名を入力してください。')
    return
  }

  submitting.value = true
  try {
    if (editingVoucherId.value) {
      await updateAccountingVoucher(editingVoucherId.value, buildPayload())
      ElMessage.success('帳票を更新しました。')
    } else {
      await createAccountingVoucher(buildPayload())
      ElMessage.success('帳票を作成しました。')
    }
    dialogVisible.value = false
    await fetchVouchers(editingVoucherId.value ? currentPage.value : 1)
  } catch {
    ElMessage.error(editingVoucherId.value ? '帳票の更新に失敗しました。' : '帳票の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const confirmDeleteVoucher = async (voucher: AccountingVoucher) => {
  try {
    await ElMessageBox.confirm(
      `「${voucher.voucher_number}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteAccountingVoucher(voucher.id)
    ElMessage.success('帳票を削除しました。')
    await fetchVouchers(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('帳票の削除に失敗しました。')
    }
  }
}

const downloadPdf = async (voucher: AccountingVoucher, withSeal = false) => {
  try {
    const { blob, contentDisposition } = await downloadAccountingVoucherPdf(voucher.id, withSeal)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = extractFilename(contentDisposition)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('PDFのダウンロードに失敗しました。')
  }
}

const handleVoucherActionCommand = (voucher: AccountingVoucher, command: string) => {
  if (command === 'edit') {
    openEditDialog(voucher)
    return
  }
  if (command === 'pdf-no-seal') {
    downloadPdf(voucher, false)
    return
  }
  if (command === 'pdf-seal') {
    downloadPdf(voucher, true)
    return
  }
  if (command === 'delete') {
    confirmDeleteVoucher(voucher)
  }
}

onMounted(() => {
  fetchVouchers()
  fetchVoucherItemTemplates()
})
</script>

<template>
  <section class="accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>請求書・領収書</h1>
          <p>請求書と領収書を作成し、PDFとしてダウンロードできます。</p>
        </div>
        <div class="accounting-toolbar">
          <el-button plain @click="openItemManager">明細項目管理</el-button>
          <el-button type="primary" @click="openCreateDialog">新規作成</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card class="accounting-filter-card" shadow="never">
      <div class="filter-title">検索条件</div>
      <div class="accounting-filter-row voucher-filter-row">
        <el-date-picker
          v-model="filters.issue_date_from"
          type="date"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          placeholder="発行日 From"
          class="accounting-filter-date"
        />
        <el-date-picker
          v-model="filters.issue_date_to"
          type="date"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          placeholder="発行日 To"
          class="accounting-filter-date"
        />
        <el-select
          v-model="filters.voucher_type"
          clearable
          placeholder="種別"
          class="accounting-filter-select"
        >
          <el-option label="請求書" value="invoice" />
          <el-option label="領収書" value="receipt" />
        </el-select>
        <el-input v-model="filters.recipient_name" clearable placeholder="宛先" class="accounting-filter-search" />
        <el-input v-model="filters.title" clearable placeholder="件名 / 内容" class="accounting-filter-search" />
        <el-input v-model="filters.amount_min" clearable inputmode="numeric" placeholder="最低金額" class="accounting-filter-date" />
        <el-input v-model="filters.amount_max" clearable inputmode="numeric" placeholder="最高金額" class="accounting-filter-date" />
        <el-input v-model="filters.keyword" clearable placeholder="キーワード" class="accounting-filter-search" />
        <div class="accounting-filter-actions">
          <el-button type="primary" @click="handleSearch">検索</el-button>
          <el-button @click="resetFilters">リセット</el-button>
        </div>
      </div>
    </el-card>

    <div class="accounting-summary-strip">
      <div class="accounting-summary-pill">
        <span>対象件数</span>
        <strong>{{ summary.count }}件</strong>
      </div>
      <div class="accounting-summary-pill">
        <span>税抜金額</span>
        <strong>{{ formatMoney(summary.amount) }}</strong>
      </div>
      <div class="accounting-summary-pill">
        <span>消費税</span>
        <strong>{{ formatMoney(summary.tax) }}</strong>
      </div>
      <div class="accounting-summary-pill is-accent">
        <span>税込合計</span>
        <strong>{{ formatMoney(summary.total) }}</strong>
      </div>
    </div>

    <el-card class="accounting-card" shadow="never">
      <el-table v-loading="loading" :data="vouchers" stripe>
        <el-table-column label="発行日" width="110">
          <template #default="{ row }">{{ formatDate(row.issue_date) }}</template>
        </el-table-column>
        <el-table-column label="種別" width="90">
          <template #default="{ row }">
            <el-tag :type="getVoucherTypeTag(row.voucher_type)">
              {{ getVoucherTypeLabel(row.voucher_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="recipient_name" label="宛先" min-width="180">
          <template #default="{ row }">{{ row.recipient_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="title" label="件名 / タイトル" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.title || '-' }}</template>
        </el-table-column>
        <el-table-column label="内容" min-width="240">
          <template #default="{ row }">
            <el-tooltip placement="top-start" effect="light">
              <template #content>
                <div class="voucher-content-tooltip">
                  <div
                    v-for="line in getVoucherContentTooltip(row).split('\n')"
                    :key="line"
                  >
                    {{ line }}
                  </div>
                </div>
              </template>
              <span class="voucher-content-summary">{{ getVoucherContentSummary(row) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="金額（税込）" width="130" align="right">
          <template #default="{ row }">{{ formatMoney(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column label="支払期日" width="110">
          <template #default="{ row }">{{ row.payment_due_date ? formatDate(row.payment_due_date) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click" @command="handleVoucherActionCommand(row, $event)">
              <el-button text type="primary">
                操作
                <span class="operation-caret">▼</span>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">編集</el-dropdown-item>
                  <el-dropdown-item command="pdf-no-seal">PDF（印章なし）</el-dropdown-item>
                  <el-dropdown-item command="pdf-seal">PDF（印章あり）</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>削除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchVouchers"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingVoucherId ? '帳票を編集' : '帳票を作成'"
      width="760px"
      class="accounting-expense-dialog"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="voucherForm" :rules="rules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="帳票種別" prop="voucher_type">
            <el-select v-model="voucherForm.voucher_type" class="form-control">
              <el-option label="請求書" value="invoice" />
              <el-option label="領収書" value="receipt" />
            </el-select>
          </el-form-item>
          <el-form-item label="発行日" prop="issue_date">
            <el-date-picker
              v-model="voucherForm.issue_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="宛先会社名" prop="recipient_name" class="accounting-dialog-full">
            <el-input v-model="voucherForm.recipient_name" />
          </el-form-item>
          <el-form-item label="宛先郵便番号" prop="recipient_postal_code">
            <el-input v-model="voucherForm.recipient_postal_code" />
          </el-form-item>
          <el-form-item label="宛先住所" prop="recipient_address" class="accounting-dialog-full">
            <el-input v-model="voucherForm.recipient_address" />
          </el-form-item>
          <el-form-item label="件名 / 但し書き" prop="title" class="accounting-dialog-full">
            <el-input v-model="voucherForm.title" />
          </el-form-item>
          <div class="voucher-line-section accounting-dialog-full">
            <div class="voucher-line-header">
              <div>
                <div class="form-section-title">明細</div>
                <p>項目名、数量、単価を入力すると金額を自動計算します。</p>
              </div>
              <el-button type="primary" plain @click="addLineItem">明細追加</el-button>
            </div>
            <div class="voucher-line-list">
              <div
                v-for="(item, index) in voucherForm.line_items"
                :key="index"
                class="voucher-line-row"
              >
                <el-form-item label="項目名">
                  <div class="voucher-item-name-control">
                    <el-select
                      v-model="item.item_name"
                      filterable
                      allow-create
                      default-first-option
                      placeholder="選択または入力"
                      class="form-control"
                      @change="handleLineItemNameChange(item)"
                    >
                      <el-option
                        v-for="template in voucherItemTemplates"
                        :key="template.id"
                        :label="template.name"
                        :value="template.name"
                      />
                    </el-select>
                    <el-button
                      v-if="isNewVoucherItemName(item.item_name)"
                      size="small"
                      plain
                      @click="saveVoucherItemTemplate(item)"
                    >
                      保存为常用項目
                    </el-button>
                  </div>
                </el-form-item>
                <el-form-item label="数量">
                  <el-input v-model="item.quantity" inputmode="decimal" />
                </el-form-item>
                <el-form-item label="単価（税込）">
                  <el-input v-model="item.unit_price" inputmode="numeric" />
                </el-form-item>
                <el-form-item label="金額（税込）">
                  <el-input :model-value="formatMoney(getLineTotal(item))" disabled />
                </el-form-item>
                <el-button text type="danger" class="voucher-line-delete" @click="removeLineItem(index)">
                  削除
                </el-button>
              </div>
            </div>
            <div class="voucher-total-box">
              <div>
                <span>税抜金額</span>
                <strong>{{ formatMoney(taxExcludedAmount) }}</strong>
              </div>
              <div>
                <span>消費税</span>
                <strong>{{ formatMoney(taxAmount) }}</strong>
              </div>
              <div class="is-total">
                <span>税込合計</span>
                <strong>{{ formatMoney(totalAmount) }}</strong>
              </div>
            </div>
          </div>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full">
            <el-input v-model="voucherForm.note" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item v-if="voucherForm.voucher_type === 'invoice'" label="支払期限" prop="payment_due_date">
            <el-date-picker
              v-model="voucherForm.payment_due_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item
            v-if="voucherForm.voucher_type === 'invoice'"
            label="振込先選択"
            class="accounting-dialog-full"
          >
            <el-select
              v-model="selectedBankInfo"
              clearable
              placeholder="選択してください"
              class="form-control"
              @change="handleBankInfoSelect"
            >
              <el-option
                v-for="option in bankInfoOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </el-form-item>
          <el-form-item
            v-if="voucherForm.voucher_type === 'invoice'"
            label="振込先"
            prop="bank_info"
            class="accounting-dialog-full"
          >
            <el-input v-model="voucherForm.bank_info" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item v-if="voucherForm.voucher_type === 'receipt'" label="支払方法" prop="payment_method">
            <el-select v-model="voucherForm.payment_method" clearable placeholder="選択してください" class="form-control">
              <el-option label="現金" value="現金" />
              <el-option label="銀行振込" value="銀行振込" />
              <el-option label="クレジットカード" value="クレジットカード" />
              <el-option label="その他" value="その他" />
            </el-select>
          </el-form-item>
          <div class="form-section-title">発行者情報</div>
          <el-form-item label="発行者名" prop="issuer_name" class="accounting-dialog-full">
            <el-input v-model="voucherForm.issuer_name" />
          </el-form-item>
          <el-form-item label="発行者郵便番号" prop="issuer_postal_code">
            <el-input v-model="voucherForm.issuer_postal_code" />
          </el-form-item>
          <el-form-item label="発行者住所" prop="issuer_address" class="accounting-dialog-full">
            <el-input v-model="voucherForm.issuer_address" />
          </el-form-item>
          <el-form-item label="発行者電話番号" prop="issuer_tel">
            <el-input v-model="voucherForm.issuer_tel" />
          </el-form-item>
          <el-form-item label="登録番号" prop="issuer_registration_number">
            <el-input v-model="voucherForm.issuer_registration_number" />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitVoucher">
          {{ editingVoucherId ? '保存' : '作成' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="itemManagerVisible"
      title="明細項目管理"
      width="900px"
      class="accounting-expense-dialog"
      @closed="resetNewItemTemplate"
    >
      <div class="voucher-item-manager">
        <div class="accounting-filter-row voucher-item-manager-search">
          <el-input
            v-model="itemManagerSearch"
            clearable
            placeholder="キーワード検索"
            class="accounting-filter-search"
          />
        </div>

        <div class="voucher-item-manager-add">
          <el-input v-model="newItemTemplate.name" placeholder="項目名" />
          <el-input v-model="newItemTemplate.default_unit_price" inputmode="numeric" placeholder="標準単価" />
          <el-input v-model="newItemTemplate.sort_order" inputmode="numeric" placeholder="並び順" />
          <el-switch v-model="newItemTemplate.is_active" active-text="有効" />
          <el-button type="primary" @click="addManagedItemTemplate">追加</el-button>
        </div>

        <el-table v-loading="itemManagerLoading" :data="filteredManagedItemTemplates" stripe>
          <el-table-column label="並び順" width="110">
            <template #default="{ row }">
              <el-input v-model="row.sort_order" inputmode="numeric" />
            </template>
          </el-table-column>
          <el-table-column label="項目名" min-width="240">
            <template #default="{ row }">
              <el-input v-model="row.name" />
            </template>
          </el-table-column>
          <el-table-column label="標準単価" width="150">
            <template #default="{ row }">
              <el-input v-model="row.default_unit_price" inputmode="numeric" placeholder="-" />
            </template>
          </el-table-column>
          <el-table-column label="有効" width="100">
            <template #default="{ row }">
              <el-switch v-model="row.is_active" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" @click="saveManagedItemTemplate(row)">保存</el-button>
              <el-button text type="danger" @click="confirmDeleteItemTemplate(row)">削除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button @click="itemManagerVisible = false">閉じる</el-button>
      </template>
    </el-dialog>
  </section>
</template>
