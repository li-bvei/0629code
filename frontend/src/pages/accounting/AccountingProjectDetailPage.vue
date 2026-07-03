<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  copyExpensesToProject,
  createAccountingProjectExpense,
  createAccountingProjectIncome,
  deleteAccountingProjectExpense,
  deleteAccountingProjectIncome,
  getAccountingProject,
  listAccountingExpenses,
  listAccountingExpenseCategories,
  listAccountingProjectExpenses,
  listAccountingProjectIncomes,
  updateAccountingProjectExpense,
  updateAccountingProjectIncome,
} from '../../api/accounting'
import type {
  AccountingListParams,
  AccountingProjectDetail,
  AccountingProjectExpense,
  AccountingProjectExpensePayload,
  AccountingProjectIncome,
  AccountingProjectIncomePayload,
  Expense,
  ExpenseCategory,
} from '../../types/accounting'
import { formatDate } from '../../utils/date'
import { createTimestamp, exportSheetsToExcel } from '../../utils/exportExcel'
import './accounting.css'

interface BatchIncomeRow {
  lineNumber: number
  income_date: string
  income_target: string
  amount: string
  note: string
  errors: string[]
}

interface BatchExpenseRow {
  lineNumber: number
  expense_date: string
  place: string
  category_name: string
  amount: string
  payment_method: string
  expense_target: string
  note: string
  errors: string[]
}

const route = useRoute()
const router = useRouter()
const projectId = computed(() => route.params.id as string)
const loading = ref(false)
const project = ref<AccountingProjectDetail | null>(null)
const incomes = ref<AccountingProjectIncome[]>([])
const expenses = ref<AccountingProjectExpense[]>([])
const categories = ref<ExpenseCategory[]>([])
const existingExpenses = ref<Expense[]>([])

const incomeDialogVisible = ref(false)
const expenseDialogVisible = ref(false)
const incomeBatchDialogVisible = ref(false)
const expenseBatchDialogVisible = ref(false)
const copyDialogVisible = ref(false)
const incomeFormRef = ref<FormInstance>()
const expenseFormRef = ref<FormInstance>()
const submitting = ref(false)
const incomeEditingId = ref<number | null>(null)
const expenseEditingId = ref<number | null>(null)
const selectedExpenseIds = ref<number[]>([])
const copyLoading = ref(false)
const exporting = ref(false)

const incomeForm = ref<AccountingProjectIncomePayload>({
  project: 0,
  income_date: '',
  income_target: '',
  amount: '',
  note: '',
})
const expenseForm = ref<AccountingProjectExpensePayload>({
  project: 0,
  expense_date: '',
  place: '',
  category_name: '',
  amount: '',
  payment_method: '',
  expense_target: '',
  note: '',
  source_expense: null,
})
const incomeBatchText = ref('')
const incomeBatchRows = ref<BatchIncomeRow[]>([])
const expenseBatchText = ref('')
const expenseBatchRows = ref<BatchExpenseRow[]>([])
const copyFilters = ref<AccountingListParams>({
  search: '',
  start_date: null,
  end_date: null,
  category: '',
})

const paymentMethodOptions = ['现金', '信用卡', '银行转账', 'PayPay', 'ICOCA', '公司账户', '个人垫付', '其他']

const incomeRules: FormRules<AccountingProjectIncomePayload> = {
  income_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  amount: [{ required: true, message: '金額を入力してください。', trigger: 'blur' }],
}
const expenseRules: FormRules<AccountingProjectExpensePayload> = {
  expense_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  amount: [{ required: true, message: '金額を入力してください。', trigger: 'blur' }],
}

const validIncomeBatchRows = computed(() => incomeBatchRows.value.filter((row) => !row.errors.length))
const invalidIncomeBatchRows = computed(() => incomeBatchRows.value.filter((row) => row.errors.length))
const validExpenseBatchRows = computed(() => expenseBatchRows.value.filter((row) => !row.errors.length))
const invalidExpenseBatchRows = computed(() => expenseBatchRows.value.filter((row) => row.errors.length))

const formatYen = (value: number | string) => `${Number(value || 0).toLocaleString()}円`
const formatPeriod = () => {
  if (!project.value) return '-'
  const start = formatDate(project.value.start_date)
  const end = formatDate(project.value.end_date)
  if (start === '-' && end === '-') return '-'
  return `${start} - ${end}`
}
const isValidDate = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

const fetchProject = async () => {
  project.value = await getAccountingProject(projectId.value)
}

const fetchIncomes = async () => {
  const rows: AccountingProjectIncome[] = []
  let page = 1
  while (true) {
    const data = await listAccountingProjectIncomes({ project: projectId.value, page })
    rows.push(...data.results)
    if (rows.length >= data.count || !data.results.length) break
    page += 1
  }
  incomes.value = rows
}

const fetchExpenses = async () => {
  const rows: AccountingProjectExpense[] = []
  let page = 1
  while (true) {
    const data = await listAccountingProjectExpenses({ project: projectId.value, page })
    rows.push(...data.results)
    if (rows.length >= data.count || !data.results.length) break
    page += 1
  }
  expenses.value = rows
}

const fetchCategories = async () => {
  const data = await listAccountingExpenseCategories({ is_active: true })
  categories.value = data.results
}

const refreshAll = async () => {
  loading.value = true
  try {
    await Promise.all([fetchProject(), fetchIncomes(), fetchExpenses(), fetchCategories()])
  } catch {
    ElMessage.error('プロジェクト収支表の取得に失敗しました。')
  } finally {
    loading.value = false
  }
}

const openIncomeDialog = (income?: AccountingProjectIncome) => {
  incomeEditingId.value = income?.id || null
  incomeForm.value = {
    project: Number(projectId.value),
    income_date: income?.income_date || '',
    income_target: income?.income_target || '',
    amount: income?.amount || '',
    note: income?.note || '',
  }
  incomeFormRef.value?.clearValidate()
  incomeDialogVisible.value = true
}

const openExpenseDialog = (expense?: AccountingProjectExpense) => {
  expenseEditingId.value = expense?.id || null
  expenseForm.value = {
    project: Number(projectId.value),
    expense_date: expense?.expense_date || '',
    place: expense?.place || '',
    category_name: expense?.category_name || '',
    amount: expense?.amount || '',
    payment_method: expense?.payment_method || '',
    expense_target: expense?.expense_target || '',
    note: expense?.note || '',
    source_expense: expense?.source_expense || null,
  }
  expenseFormRef.value?.clearValidate()
  expenseDialogVisible.value = true
}

const submitIncome = async () => {
  if (!incomeFormRef.value) return
  const valid = await incomeFormRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (incomeEditingId.value) {
      await updateAccountingProjectIncome(incomeEditingId.value, incomeForm.value)
      ElMessage.success('プロジェクト収入を更新しました。')
    } else {
      await createAccountingProjectIncome(incomeForm.value)
      ElMessage.success('プロジェクト収入を追加しました。')
    }
    incomeDialogVisible.value = false
    await refreshAll()
  } catch {
    ElMessage.error('プロジェクト収入の保存に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const submitExpense = async () => {
  if (!expenseFormRef.value) return
  const valid = await expenseFormRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (expenseEditingId.value) {
      await updateAccountingProjectExpense(expenseEditingId.value, expenseForm.value)
      ElMessage.success('プロジェクト支出を更新しました。')
    } else {
      await createAccountingProjectExpense(expenseForm.value)
      ElMessage.success('プロジェクト支出を追加しました。')
    }
    expenseDialogVisible.value = false
    await refreshAll()
  } catch {
    ElMessage.error('プロジェクト支出の保存に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const confirmDeleteIncome = async (income: AccountingProjectIncome) => {
  try {
    await ElMessageBox.confirm('このプロジェクト収入を削除します。よろしいですか？', '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingProjectIncome(income.id)
    ElMessage.success('プロジェクト収入を削除しました。')
    await refreshAll()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('削除に失敗しました。')
  }
}

const confirmDeleteExpense = async (expense: AccountingProjectExpense) => {
  try {
    await ElMessageBox.confirm('このプロジェクト支出を削除します。よろしいですか？', '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingProjectExpense(expense.id)
    ElMessage.success('プロジェクト支出を削除しました。')
    await refreshAll()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('削除に失敗しました。')
  }
}

const parseBatchIncomeLine = (line: string, lineNumber: number): BatchIncomeRow | null => {
  if (!line) return null
  const cells = (line.includes('\t') ? line.split('\t') : line.split(',')).map((cell) => cell.trim())
  if (lineNumber === 1 && ['日期', '日付', 'income_date'].includes(cells[0])) return null
  const [incomeDate = '', incomeTarget = '', amount = '', note = ''] = cells
  const errors: string[] = []
  if (!incomeDate) errors.push('日付が未入力です')
  else if (!isValidDate(incomeDate)) errors.push('日付形式が正しくありません')
  if (!amount) errors.push('金額が未入力です')
  else if (Number.isNaN(Number(amount))) errors.push('金額は数字で入力してください')
  return { lineNumber, income_date: incomeDate, income_target: incomeTarget, amount, note, errors }
}

const parseBatchExpenseLine = (line: string, lineNumber: number): BatchExpenseRow | null => {
  if (!line) return null
  const cells = (line.includes('\t') ? line.split('\t') : line.split(',')).map((cell) => cell.trim())
  if (lineNumber === 1 && ['日期', '日付', 'expense_date'].includes(cells[0])) return null
  const [expenseDate = '', place = '', categoryName = '', amount = '', paymentMethod = '', expenseTarget = '', note = ''] = cells
  const errors: string[] = []
  if (!expenseDate) errors.push('日付が未入力です')
  else if (!isValidDate(expenseDate)) errors.push('日付形式が正しくありません')
  if (!amount) errors.push('金額が未入力です')
  else if (Number.isNaN(Number(amount))) errors.push('金額は数字で入力してください')
  return { lineNumber, expense_date: expenseDate, place, category_name: categoryName, amount, payment_method: paymentMethod, expense_target: expenseTarget, note, errors }
}

const previewIncomeBatch = () => {
  incomeBatchRows.value = incomeBatchText.value
    .split(/\r?\n/)
    .map((line, index) => parseBatchIncomeLine(line.trim(), index + 1))
    .filter((row): row is BatchIncomeRow => Boolean(row))
}

const previewExpenseBatch = () => {
  expenseBatchRows.value = expenseBatchText.value
    .split(/\r?\n/)
    .map((line, index) => parseBatchExpenseLine(line.trim(), index + 1))
    .filter((row): row is BatchExpenseRow => Boolean(row))
}

const submitIncomeBatch = async () => {
  if (!incomeBatchRows.value.length) previewIncomeBatch()
  if (!validIncomeBatchRows.value.length || invalidIncomeBatchRows.value.length) {
    ElMessage.warning('エラーのある行を修正してから追加してください。')
    return
  }
  for (const row of validIncomeBatchRows.value) {
    await createAccountingProjectIncome({
      project: Number(projectId.value),
      income_date: row.income_date,
      income_target: row.income_target,
      amount: row.amount,
      note: row.note,
    })
  }
  ElMessage.success(`追加完了：${validIncomeBatchRows.value.length}件`)
  incomeBatchDialogVisible.value = false
  incomeBatchText.value = ''
  incomeBatchRows.value = []
  await refreshAll()
}

const submitExpenseBatch = async () => {
  if (!expenseBatchRows.value.length) previewExpenseBatch()
  if (!validExpenseBatchRows.value.length || invalidExpenseBatchRows.value.length) {
    ElMessage.warning('エラーのある行を修正してから追加してください。')
    return
  }
  for (const row of validExpenseBatchRows.value) {
    await createAccountingProjectExpense({
      project: Number(projectId.value),
      expense_date: row.expense_date,
      place: row.place,
      category_name: row.category_name,
      amount: row.amount,
      payment_method: row.payment_method,
      expense_target: row.expense_target,
      note: row.note,
      source_expense: null,
    })
  }
  ElMessage.success(`追加完了：${validExpenseBatchRows.value.length}件`)
  expenseBatchDialogVisible.value = false
  expenseBatchText.value = ''
  expenseBatchRows.value = []
  await refreshAll()
}

const fetchExistingExpenses = async () => {
  copyLoading.value = true
  try {
    const rows: Expense[] = []
    let page = 1
    while (true) {
      const data = await listAccountingExpenses({ ...copyFilters.value, page })
      rows.push(...data.results)
      if (rows.length >= data.count || !data.results.length) break
      page += 1
    }
    existingExpenses.value = rows
  } catch {
    ElMessage.error('支出記録の取得に失敗しました。')
  } finally {
    copyLoading.value = false
  }
}

const openCopyDialog = async () => {
  selectedExpenseIds.value = []
  copyDialogVisible.value = true
  await fetchExistingExpenses()
}

const handleExpenseSelection = (rows: Expense[]) => {
  selectedExpenseIds.value = rows.map((row) => row.id)
}

const submitCopyExpenses = async () => {
  if (!selectedExpenseIds.value.length) {
    ElMessage.warning('コピーする支出記録を選択してください。')
    return
  }
  const result = await copyExpensesToProject(projectId.value, selectedExpenseIds.value)
  ElMessage.success(`${result.created}件をプロジェクト支出にコピーしました。`)
  copyDialogVisible.value = false
  await refreshAll()
}

const exportProject = () => {
  if (!project.value) return
  exporting.value = true
  try {
    exportSheetsToExcel(
      [
        {
          sheetName: 'プロジェクト収入',
          rows: incomes.value.map((row) => ({
            日付: row.income_date,
            対象: row.income_target || '',
            金額: Number(row.amount || 0),
            備考: row.note || '',
          })),
        },
        {
          sheetName: 'プロジェクト支出',
          rows: expenses.value.map((row) => ({
            日付: row.expense_date,
            場所: row.place || '',
            カテゴリ: row.category_name || '',
            金額: Number(row.amount || 0),
            支払方法: row.payment_method || '',
            費用対象: row.expense_target || '',
            備考: row.note || '',
          })),
        },
      ],
      `プロジェクト収支表_${project.value.name}_${createTimestamp()}.xlsx`,
    )
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  refreshAll()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>{{ project?.name || 'プロジェクト収支表' }}</h1>
          <p>プロジェクト単位の収入と支出を個別に管理します。</p>
        </div>
        <div class="accounting-toolbar">
          <el-button @click="router.push('/accounting/projects')">一覧へ戻る</el-button>
          <el-button :loading="exporting" @click="exportProject">Excel出力</el-button>
          <el-button type="primary" @click="router.push(`/accounting/projects/${projectId}/edit`)">編集</el-button>
        </div>
      </div>
    </div>

    <div v-loading="loading" class="accounting-page">
      <el-card shadow="never" class="accounting-card">
        <template #header>项目基本信息</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="项目名称">{{ project?.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="期间">{{ formatPeriod() }}</el-descriptions-item>
          <el-descriptions-item label="是否启用">{{ project?.is_active ? '有効' : '無効' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ project?.note || '-' }}</el-descriptions-item>
          <el-descriptions-item label="项目说明" :span="2">{{ project?.description || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <div class="accounting-summary-strip">
        <div class="accounting-summary-pill"><span>収入合計</span><strong>{{ formatYen(project?.income_total || 0) }}</strong></div>
        <div class="accounting-summary-pill"><span>支出合計</span><strong>{{ formatYen(project?.expense_total || 0) }}</strong></div>
        <div class="accounting-summary-pill"><span>残高</span><strong>{{ formatYen(project?.balance || 0) }}</strong></div>
        <div class="accounting-summary-pill"><span>収入件数</span><strong>{{ project?.income_count || 0 }}件</strong></div>
        <div class="accounting-summary-pill"><span>支出件数</span><strong>{{ project?.expense_count || 0 }}件</strong></div>
      </div>

      <el-card shadow="never" class="accounting-card">
        <template #header>
          <div class="card-header-row">
            <span>プロジェクト収入</span>
            <div class="card-actions">
              <el-button @click="incomeBatchDialogVisible = true">批量追加</el-button>
              <el-button type="primary" @click="openIncomeDialog()">新增</el-button>
            </div>
          </div>
        </template>
        <el-table :data="incomes" stripe>
          <el-table-column label="日付" width="130"><template #default="{ row }">{{ formatDate(row.income_date) }}</template></el-table-column>
          <el-table-column prop="income_target" label="対象" min-width="160" />
          <el-table-column label="金額" width="130" align="right" header-align="right"><template #default="{ row }">{{ formatYen(row.amount) }}</template></el-table-column>
          <el-table-column prop="note" label="備考" min-width="220" show-overflow-tooltip />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" @click="openIncomeDialog(row)">編集</el-button>
              <el-button text type="danger" @click="confirmDeleteIncome(row)">削除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="!incomes.length" class="empty-text">データがありません</p>
      </el-card>

      <el-card shadow="never" class="accounting-card">
        <template #header>
          <div class="card-header-row">
            <span>プロジェクト支出</span>
            <div class="card-actions">
              <el-button @click="openCopyDialog">既存支出から追加</el-button>
              <el-button @click="expenseBatchDialogVisible = true">批量追加</el-button>
              <el-button type="primary" @click="openExpenseDialog()">新增</el-button>
            </div>
          </div>
        </template>
        <el-table :data="expenses" stripe>
          <el-table-column label="日付" width="130"><template #default="{ row }">{{ formatDate(row.expense_date) }}</template></el-table-column>
          <el-table-column prop="place" label="場所" min-width="130" />
          <el-table-column prop="category_name" label="カテゴリ" min-width="130" />
          <el-table-column label="金額" width="130" align="right" header-align="right"><template #default="{ row }">{{ formatYen(row.amount) }}</template></el-table-column>
          <el-table-column prop="payment_method" label="支払方法" min-width="120" />
          <el-table-column prop="expense_target" label="費用対象" min-width="150" />
          <el-table-column prop="note" label="備考" min-width="220" show-overflow-tooltip />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button text type="primary" @click="openExpenseDialog(row)">編集</el-button>
              <el-button text type="danger" @click="confirmDeleteExpense(row)">削除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-if="!expenses.length" class="empty-text">データがありません</p>
      </el-card>
    </div>

    <el-dialog v-model="incomeDialogVisible" :title="incomeEditingId ? 'プロジェクト収入を編集' : 'プロジェクト収入を追加'" width="640px" class="accounting-batch-dialog">
      <el-form ref="incomeFormRef" :model="incomeForm" :rules="incomeRules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="日付" prop="income_date"><el-date-picker v-model="incomeForm.income_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" /></el-form-item>
          <el-form-item label="対象" prop="income_target"><el-input v-model="incomeForm.income_target" /></el-form-item>
          <el-form-item label="金額" prop="amount"><el-input v-model="incomeForm.amount" inputmode="numeric" /></el-form-item>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full"><el-input v-model="incomeForm.note" type="textarea" :rows="3" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="incomeDialogVisible = false">キャンセル</el-button><el-button type="primary" :loading="submitting" @click="submitIncome">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="expenseDialogVisible" :title="expenseEditingId ? 'プロジェクト支出を編集' : 'プロジェクト支出を追加'" width="720px" class="accounting-batch-dialog">
      <el-form ref="expenseFormRef" :model="expenseForm" :rules="expenseRules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="日付" prop="expense_date"><el-date-picker v-model="expenseForm.expense_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" class="form-control" /></el-form-item>
          <el-form-item label="場所" prop="place"><el-input v-model="expenseForm.place" /></el-form-item>
          <el-form-item label="カテゴリ" prop="category_name"><el-input v-model="expenseForm.category_name" /></el-form-item>
          <el-form-item label="金額" prop="amount"><el-input v-model="expenseForm.amount" inputmode="numeric" /></el-form-item>
          <el-form-item label="支払方法" prop="payment_method"><el-select v-model="expenseForm.payment_method" clearable class="form-control"><el-option v-for="method in paymentMethodOptions" :key="method" :label="method" :value="method" /></el-select></el-form-item>
          <el-form-item label="費用対象" prop="expense_target"><el-input v-model="expenseForm.expense_target" /></el-form-item>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full"><el-input v-model="expenseForm.note" type="textarea" :rows="3" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="expenseDialogVisible = false">キャンセル</el-button><el-button type="primary" :loading="submitting" @click="submitExpense">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="incomeBatchDialogVisible" title="プロジェクト収入を一括追加" width="860px" class="accounting-batch-dialog">
      <div class="accounting-batch-help">形式：日期	对象	金额	备注<code>2026-07-01	项目入金	50000	预付款</code></div>
      <el-input v-model="incomeBatchText" type="textarea" :rows="8" />
      <div class="accounting-batch-actions"><el-button @click="previewIncomeBatch">解析</el-button><el-button type="primary" :disabled="!incomeBatchRows.length || Boolean(invalidIncomeBatchRows.length)" @click="submitIncomeBatch">確認追加</el-button></div>
      <el-table v-if="incomeBatchRows.length" :data="incomeBatchRows" max-height="320" stripe>
        <el-table-column prop="lineNumber" label="行" width="70" />
        <el-table-column prop="income_date" label="日付" width="120" />
        <el-table-column prop="income_target" label="対象" min-width="140" />
        <el-table-column prop="amount" label="金額" width="120" />
        <el-table-column prop="note" label="備考" min-width="160" />
        <el-table-column label="状態" min-width="180"><template #default="{ row }"><el-tag v-if="row.errors.length" type="danger">{{ row.errors.join('、') }}</el-tag><el-tag v-else type="success">追加可能</el-tag></template></el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="expenseBatchDialogVisible" title="プロジェクト支出を一括追加" width="920px" class="accounting-batch-dialog">
      <div class="accounting-batch-help">形式：日期	地点	类别	金额	支付方式	费用对象	备注<code>2026-07-01	役所	証明書	300	现金	王先生	取得</code></div>
      <el-input v-model="expenseBatchText" type="textarea" :rows="8" />
      <div class="accounting-batch-actions"><el-button @click="previewExpenseBatch">解析</el-button><el-button type="primary" :disabled="!expenseBatchRows.length || Boolean(invalidExpenseBatchRows.length)" @click="submitExpenseBatch">確認追加</el-button></div>
      <el-table v-if="expenseBatchRows.length" :data="expenseBatchRows" max-height="320" stripe>
        <el-table-column prop="lineNumber" label="行" width="70" />
        <el-table-column prop="expense_date" label="日付" width="120" />
        <el-table-column prop="place" label="場所" min-width="120" />
        <el-table-column prop="category_name" label="カテゴリ" min-width="120" />
        <el-table-column prop="amount" label="金額" width="120" />
        <el-table-column prop="payment_method" label="支払方法" min-width="120" />
        <el-table-column prop="expense_target" label="費用対象" min-width="140" />
        <el-table-column label="状態" min-width="180"><template #default="{ row }"><el-tag v-if="row.errors.length" type="danger">{{ row.errors.join('、') }}</el-tag><el-tag v-else type="success">追加可能</el-tag></template></el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="copyDialogVisible" title="既存支出から追加" width="980px" class="accounting-batch-dialog">
      <div class="accounting-filter-card">
        <div class="accounting-filter-row">
          <el-input v-model="copyFilters.search" placeholder="場所・対象・備考で検索" clearable class="accounting-filter-search" />
          <el-date-picker v-model="copyFilters.start_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="開始日" class="accounting-filter-date" />
          <el-date-picker v-model="copyFilters.end_date" type="date" format="YYYY-MM-DD" value-format="YYYY-MM-DD" placeholder="終了日" class="accounting-filter-date" />
          <el-select v-model="copyFilters.category" clearable placeholder="カテゴリ" class="accounting-filter-select"><el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.name" /></el-select>
          <el-button type="primary" @click="fetchExistingExpenses">検索</el-button>
        </div>
      </div>
      <el-table v-loading="copyLoading" :data="existingExpenses" max-height="360" stripe @selection-change="handleExpenseSelection">
        <el-table-column type="selection" width="50" />
        <el-table-column label="日付" width="120"><template #default="{ row }">{{ formatDate(row.expense_date) }}</template></el-table-column>
        <el-table-column prop="place" label="場所" min-width="120" />
        <el-table-column prop="category" label="カテゴリ" min-width="120" />
        <el-table-column label="金額" width="120" align="right"><template #default="{ row }">{{ formatYen(row.amount) }}</template></el-table-column>
        <el-table-column prop="payment_method" label="支払方法" min-width="120" />
        <el-table-column prop="expense_target" label="費用対象" min-width="140" />
        <el-table-column prop="note" label="備考" min-width="160" show-overflow-tooltip />
      </el-table>
      <template #footer><el-button @click="copyDialogVisible = false">キャンセル</el-button><el-button type="primary" @click="submitCopyExpenses">確認追加</el-button></template>
    </el-dialog>
  </section>
</template>
