<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createVoucherItemTemplate,
  createAccountingVoucher,
  transitionBusinessDocument,
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
  AccountingVoucherTaxCategory,
  AccountingVoucherType,
  VoucherItemTemplate,
} from '../types/accounting'
import { formatDate } from '../utils/date'
import RemoteCaseSelect from '../components/RemoteCaseSelect.vue'
import VoucherStatusActions from '../components/vouchers/VoucherStatusActions.vue'
import VoucherLinesTable from '../components/vouchers/VoucherLinesTable.vue'
import VoucherHistoryDialog from '../components/vouchers/VoucherHistoryDialog.vue'
import { apiErrorText } from '../components/vouchers/voucherErrors'
import { useDocumentList } from '../components/vouchers/useDocumentList'
import { summarizeLines } from '../utils/voucherCalc'
import {
  createLine, keyForSavedRow, toPayloadLines, validateLines, withKeys, type VoucherLine,
} from '../utils/voucherLines'
import './accounting/accounting.css'

// P2-C11：請求書と領収書は状態を共有しない（invoice_status / receipt_status）。
// 2026-10 P1：状態は自由に切り替えられる。内容は下書きのときだけ編集でき、発行後に直すときは下書きに戻す。
const route = useRoute()
const documentActions = useDocumentList<AccountingVoucher>('vouchers', '請求書', listAccountingVouchers)
const editingLocked = ref(false)
const editingVoucher = ref<AccountingVoucher | null>(null)
// 明細（連続入力の行）。行ごとの誤りは key ごとに持ち、他の行は消さない
const lines = ref<VoucherLine[]>([createLine()])
const lineErrors = ref<Record<number, string>>({})
const historyVisible = ref(false)
const historyTarget = ref<AccountingVoucher | null>(null)
const revertingToDraft = ref(false)
const editingCaseOption = ref<{ value: number; label: string } | null>(null)
const INVOICE_STATUS_OPTIONS = [
  { value: 'draft', label: '下書き' }, { value: 'issued', label: '発行済み' }, { value: 'sent', label: '送付済み' },
  { value: 'paid', label: '入金済み' }, { value: 'cancelled', label: '取消' }, { value: 'unset', label: '状態未設定（旧データ）' },
]
const RECEIPT_STATUS_OPTIONS = [
  { value: 'draft', label: '下書き' }, { value: 'issued', label: '発行済み' }, { value: 'voided', label: '無効' },
  { value: 'unset', label: '状態未設定（旧データ）' },
]
const statusOptions = computed(() => (filters.value.voucher_type === 'receipt' ? RECEIPT_STATUS_OPTIONS : INVOICE_STATUS_OPTIONS))

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const errorMessage = ref('')
const vouchers = ref<AccountingVoucher[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const editingVoucherId = ref<number | null>(null)
const showRecipientDetail = ref(false)
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
  keyword: typeof route.query.keyword === 'string' ? route.query.keyword : '',
  status: '',
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

const TAX_CATEGORY_10: AccountingVoucherTaxCategory = 'tax_10'
const taxCategoryOptions: { label: string; value: AccountingVoucherTaxCategory }[] = [
  { label: '10％', value: TAX_CATEGORY_10 },
  { label: '8％', value: 'tax_8' },
  { label: '非課税', value: 'non_taxable' },
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
  tax_category: TAX_CATEGORY_10,
  price_type: 'tax_included',
})

const voucherForm = ref<AccountingVoucherPayload>({
  voucher_type: 'invoice',
  issue_date: getTodayDate(),
  recipient_name: '',
  recipient_honorific: '御中',
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
  case: null,
})

const rules: FormRules<AccountingVoucherPayload> = {
  voucher_type: [{ required: true, message: '帳票種別を選択してください。', trigger: 'change' }],
  issue_date: [{ required: true, message: '発行日を入力してください。', trigger: 'change' }],
}

const getTaxCategory = (item: AccountingVoucherLineItem): AccountingVoucherTaxCategory => {
  return taxCategoryOptions.some((option) => option.value === item.tax_category)
    ? item.tax_category as AccountingVoucherTaxCategory
    : TAX_CATEGORY_10
}

const getTaxCategoryLabel = (item: AccountingVoucherLineItem) => {
  return taxCategoryOptions.find((option) => option.value === getTaxCategory(item))?.label || '10％'
}

const taxSummary = computed(() => summarizeLines(lines.value))
const taxExcludedAmount = computed(() => taxSummary.value.subtotal)
const taxAmount = computed(() => taxSummary.value.tax_total)
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
      return `${name} / 単価 ${unitPrice} / 数量 ${quantity} / 税区分 ${getTaxCategoryLabel(item)} / 金額 ${formatMoney(lineTotal)}${note ? ` / ${note}` : ''}`
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
    // 状態の絞り込みは種別を選んだときだけ（請求書と領収書で状態の種類が違うため）
    const params = { page, ...filters.value, status: filters.value.voucher_type ? filters.value.status : '' }
    const data = await listAccountingVouchers(params)
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
    status: '',
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
    recipient_honorific: '御中',
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
    case: null,
  }
  editingLocked.value = false
  editingVoucher.value = null
  lines.value = [createLine()]
  lineErrors.value = {}
  editingCaseOption.value = null
  selectedBankInfo.value = ''
  showRecipientDetail.value = false
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
    recipient_honorific: voucher.recipient_honorific || '御中',
    recipient_postal_code: voucher.recipient_postal_code,
    recipient_address: voucher.recipient_address,
    title: voucher.title,
    amount: voucher.amount,
    tax_amount: voucher.tax_amount,
    details: voucher.details,
    line_items: voucher.line_items?.length
      ? voucher.line_items.map((item) => ({ ...item, tax_category: getTaxCategory(item) }))
      : [{
          item_name: voucher.title || voucher.details || '',
          quantity: 1,
          unit_price: voucher.amount,
          line_total: voucher.amount,
          tax_category: TAX_CATEGORY_10,
          price_type: 'tax_included',
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
    case: voucher.case,
  }
  editingLocked.value = !voucher.is_editable
  editingVoucher.value = voucher
  lines.value = withKeys(voucherForm.value.line_items || [])
  lineErrors.value = {}
  editingCaseOption.value = voucher.case ? { value: voucher.case, label: voucher.case_number } : null
  selectedBankInfo.value = ''
  showRecipientDetail.value = Boolean(voucher.recipient_postal_code || voucher.recipient_address)
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

const handleBankInfoSelect = (value: string) => {
  const selected = bankInfoOptions.find((option) => option.value === value)
  if (selected && selected.value !== 'manual') {
    voucherForm.value.bank_info = selected.text
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

const buildPayload = () => {
  // P4：画面で見ていた版を送る（他の人が先に保存していれば 409 で保存しない）
  const version = editingVoucher.value?.updated_at
  if (editingLocked.value) return { note: voucherForm.value.note, case: voucherForm.value.case, version }
  const lineItems = toPayloadLines(lines.value)
  const payload = {
    ...voucherForm.value,
    version: editingVoucherId.value ? version : undefined,
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
  if (!editingLocked.value) {
    // 誤りのある行にだけ印を付ける（入力済みの他の行はそのまま）
    lineErrors.value = validateLines(lines.value)
    const errorCount = Object.keys(lineErrors.value).length
    if (errorCount) {
      ElMessage.error(`${errorCount} 行の明細に誤りがあります。赤く表示された行を確認してください。`)
      return
    }
    if (!toPayloadLines(lines.value).length) {
      ElMessage.error('明細を 1 行以上入力してください。')
      return
    }
  }

  submitting.value = true
  try {
    if (editingVoucherId.value) {
      await updateAccountingVoucher(editingVoucherId.value, buildPayload())
      ElMessage.success('帳票を更新しました。')
    } else {
      await createAccountingVoucher(buildPayload() as AccountingVoucherPayload)
      ElMessage.success('帳票を作成しました。')
    }
    dialogVisible.value = false
    await fetchVouchers(editingVoucherId.value ? currentPage.value : 1)
  } catch (error) {
    const response = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
    const row = Number((response?.data?.line_item_row as unknown[] | undefined)?.[0] ?? response?.data?.line_item_row)
    if (row) {
      const key = keyForSavedRow(lines.value, row)
      const message = String((response?.data?.line_items as unknown[] | undefined)?.[0] ?? response?.data?.line_items ?? '')
      if (key !== null) lineErrors.value = { ...lineErrors.value, [key]: message.replace(/^\d+ 行目：/, '') }
    }
    if (response?.status === 409) {
      // 他の操作で発行された、または他の人が先に保存した：内容は保存していない（入力はそのまま残す）
      await fetchVouchers(currentPage.value)
      const latest = vouchers.value.find((row) => row.id === editingVoucherId.value)
      if (!latest || !latest.is_editable) editingLocked.value = true
    }
    const fallback = editingVoucherId.value ? '帳票の更新に失敗しました。' : '帳票の作成に失敗しました。'
    ElMessage.error({ message: apiErrorText(error, fallback), duration: 6000 })
  } finally {
    submitting.value = false
  }
}

// 発行済み・取消などの帳票を下書きに戻し、その場で編集できるようにする（履歴に残る）
const revertToDraft = async () => {
  const voucher = editingVoucher.value
  if (!voucher || revertingToDraft.value) return
  let reason = ''
  try {
    const result = await ElMessageBox.prompt(
      '下書きに戻すと内容を編集できます。再発行すると新しい版として履歴に残ります。理由・メモ（任意）', '下書きに戻す',
      { confirmButtonText: '下書きに戻す', cancelButtonText: 'キャンセル' },
    )
    reason = result.value || ''
  } catch {
    return
  }
  revertingToDraft.value = true
  try {
    const updated = await transitionBusinessDocument('vouchers', voucher.id, {
      status: 'draft', reason, expected_status: voucher.status_value,
    }) as AccountingVoucher
    editingVoucher.value = updated
    editingLocked.value = !updated.is_editable
    ElMessage.success('下書きに戻しました。内容を編集できます。')
    await fetchVouchers(currentPage.value)
  } catch (error) {
    ElMessage.error({ message: apiErrorText(error, '下書きに戻せませんでした。もう一度お試しください。'), duration: 6000 })
  } finally {
    revertingToDraft.value = false
  }
}

const openHistory = (voucher: AccountingVoucher) => {
  historyTarget.value = voucher
  historyVisible.value = true
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
  if (command === 'history') {
    openHistory(voucher)
    return
  }
  if (command === 'receipt') {
    documentActions.createFrom(voucher.id, 'create-receipt')
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
        <el-select
          v-model="filters.status"
          clearable
          :disabled="!filters.voucher_type"
          :placeholder="filters.voucher_type ? '状態' : '状態（種別を選択）'"
          class="accounting-filter-select"
        >
          <el-option v-for="option in statusOptions" :key="option.value" :label="option.label" :value="option.value" />
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
        <el-table-column label="番号" width="170">
          <template #default="{ row }">
            <div>{{ row.voucher_number }}</div>
            <div v-if="row.source_invoice_number || row.source_contract_number || row.source_estimate_number" class="voucher-source">
              元：{{ row.source_invoice_number || row.source_contract_number || row.source_estimate_number }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状態" width="150">
          <template #default="{ row }">
            <VoucherStatusActions endpoint="vouchers" :doc="row" @changed="fetchVouchers()" />
            <div v-if="row.paid_date" class="voucher-source">入金日 {{ formatDate(row.paid_date) }}</div>
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
              <el-button text type="primary" class="table-action-trigger">
                操作
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">{{ row.is_editable ? '編集' : '表示・備考' }}</el-dropdown-item>
                  <el-dropdown-item command="pdf-no-seal">PDF（印章なし）</el-dropdown-item>
                  <el-dropdown-item command="pdf-seal">PDF（印章あり）</el-dropdown-item>
                  <el-dropdown-item command="history">状態履歴</el-dropdown-item>
                  <el-dropdown-item v-if="row.voucher_type === 'invoice'" command="receipt" divided>領収書を作成</el-dropdown-item>
                  <el-dropdown-item v-if="row.is_editable" command="delete" divided class="danger-item">削除</el-dropdown-item>
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
      width="min(1200px, 96vw)"
      class="accounting-expense-dialog voucher-edit-dialog"
      :close-on-press-escape="false"
      :close-on-click-modal="false"
      @closed="resetForm"
    >
      <el-alert
        v-if="editingLocked"
        type="info"
        show-icon
        :closable="false"
        class="voucher-locked-alert"
        :title="`「${editingVoucher?.status_display || '下書き以外'}」の帳票です。内容を変更するには下書きに戻してください（備考と関連案件はこのまま変更できます）。`"
      >
        <el-button v-if="editingVoucher" size="small" type="primary" plain :loading="revertingToDraft" @click="revertToDraft">
          下書きに戻して編集
        </el-button>
      </el-alert>
      <el-form ref="formRef" :model="voucherForm" :rules="rules" :disabled="editingLocked" label-position="top">
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
            <div class="voucher-recipient-control">
              <el-input v-model="voucherForm.recipient_name" placeholder="会社名または個人名" />
              <el-select v-model="voucherForm.recipient_honorific" class="voucher-honorific-select">
                <el-option label="御中" value="御中" />
                <el-option label="様" value="様" />
                <el-option label="なし" value="" />
              </el-select>
            </div>
            <el-button
              v-if="!showRecipientDetail"
              text
              type="primary"
              size="small"
              @click="showRecipientDetail = true"
            >
              詳細住所を追加（任意）
            </el-button>
          </el-form-item>
          <template v-if="showRecipientDetail">
            <el-form-item label="宛先郵便番号" prop="recipient_postal_code">
              <el-input v-model="voucherForm.recipient_postal_code" />
            </el-form-item>
            <el-form-item label="宛先住所" prop="recipient_address" class="accounting-dialog-full">
              <el-input v-model="voucherForm.recipient_address" />
            </el-form-item>
          </template>
          <el-form-item label="件名 / 但し書き" prop="title" class="accounting-dialog-full">
            <el-input v-model="voucherForm.title" />
          </el-form-item>
          <div class="voucher-line-section accounting-dialog-full">
            <div class="form-section-title">明細</div>
            <VoucherLinesTable
              v-model="lines"
              :disabled="editingLocked"
              :templates="voucherItemTemplates"
              :errors="lineErrors"
              :allow-service-items="voucherForm.voucher_type === 'invoice'"
              :internal-costs="editingVoucher?.internal_line_costs"
              @save-template="saveVoucherItemTemplate"
            />
          </div>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full">
            <el-input v-model="voucherForm.note" type="textarea" :rows="3" :disabled="false" />
          </el-form-item>
          <el-form-item label="関連案件（任意）" class="accounting-dialog-full">
            <RemoteCaseSelect
              v-model="voucherForm.case"
              clearable
              :disabled="false"
              :initial-option="editingCaseOption"
              placeholder="担当案件から選択"
            />
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

    <VoucherHistoryDialog v-model:visible="historyVisible" :voucher-id="historyTarget?.id ?? null" :number="historyTarget?.voucher_number" />

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
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-dropdown trigger="click">
                <el-button text type="primary" class="table-action-trigger">
                  操作
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="saveManagedItemTemplate(row)">保存</el-dropdown-item>
                    <el-dropdown-item divided class="danger-item" @click="confirmDeleteItemTemplate(row)">削除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
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

<style scoped>
.voucher-source {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.voucher-locked-alert {
  margin-bottom: 12px;
}

:deep(.voucher-nowrap-form-item .el-form-item__label) {
  white-space: nowrap;
}
</style>
