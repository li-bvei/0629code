<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { saveAs } from 'file-saver'
import { useRouter } from 'vue-router'
import {
  createAccountingExpense,
  deleteAccountingExpense,
  downloadAccountingExpensesExcel,
  getAccountingExpenseSummary,
  listAccountingExpenseCategories,
  listAccountingExpenses,
} from '../../api/accounting'
import type { AccountingListParams, Expense, ExpenseCategory, ExpensePayload } from '../../types/accounting'
import { formatAccountingNumber } from '../../utils/accountingFormat'
import { formatDate } from '../../utils/date'
import './accounting.css'

interface BatchExpenseRow {
  lineNumber: number
  expense_date: string
  place: string
  category: string
  amount: string
  payment_method: string
  expense_target: string
  note: string
  errors: string[]
}

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const expenses = ref<Expense[]>([])
const categories = ref<ExpenseCategory[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filters = ref<AccountingListParams>({
  search: '',
  start_date: null,
  end_date: null,
  category: '',
  payment_method: '',
  is_reimbursed: '',
})

const addDialogVisible = ref(false)
const addFormRef = ref<FormInstance>()
const submitting = ref(false)
const addForm = ref<ExpensePayload>({
  expense_date: '',
  place: '',
  category: '',
  amount: '',
  payment_method: '',
  expense_target: '',
  note: '',
  is_reimbursed: false,
  is_exported: false,
})

const batchDialogVisible = ref(false)
const batchText = ref('')
const batchRows = ref<BatchExpenseRow[]>([])
const batchSubmitting = ref(false)
const exporting = ref(false)
const summaryLoading = ref(true)
const summaryLoaded = ref(false)
let summaryRequestId = 0
const summary = ref({
  count: 0,
  totalExpense: 0,
  balance: 0,
})

const paymentMethodOptions = ['现金', '信用卡', '银行转账', 'PayPay', 'ICOCA', '公司账户', '个人垫付', '其他']
const boolOptions = [
  { label: 'はい', value: 'true' },
  { label: 'いいえ', value: 'false' },
]

const addRules: FormRules<ExpensePayload> = {
  expense_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  category: [{ required: true, message: 'カテゴリを選択してください。', trigger: 'change' }],
  amount: [{ required: true, message: '金額を入力してください。', trigger: 'blur' }],
}

const validBatchRows = computed(() => batchRows.value.filter((row) => !row.errors.length))
const invalidBatchRows = computed(() => batchRows.value.filter((row) => row.errors.length))

const formatBoolean = (value: boolean) => (value ? 'はい' : 'いいえ')

const downloadFileName = (contentDisposition?: string) => {
  const fallback = '支出記録.xlsx'
  if (!contentDisposition) return fallback
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
  if (utf8Match) return decodeURIComponent(utf8Match[1])
  const match = contentDisposition.match(/filename="?([^"]+)"?/)
  return match?.[1] || fallback
}

const createEmptyExpenseForm = (): ExpensePayload => ({
  expense_date: '',
  place: '',
  category: '',
  amount: '',
  payment_method: '',
  expense_target: '',
  note: '',
  is_reimbursed: false,
  is_exported: false,
})

const isValidDate = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

const fetchExpenses = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listAccountingExpenses({ ...filters.value, page })
    expenses.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = '支出記録の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const refreshExpenseSummary = async () => {
  const requestId = ++summaryRequestId
  summaryLoading.value = true
  try {
    const data = await getAccountingExpenseSummary(filters.value)
    if (requestId !== summaryRequestId) return
    summary.value = {
      count: data.target_count,
      totalExpense: Number(data.total_expense || 0),
      balance: Number(data.balance || 0),
    }
    summaryLoaded.value = true
  } catch {
    if (requestId !== summaryRequestId) return
    ElMessage.error('支出集計の取得に失敗しました。')
  } finally {
    if (requestId === summaryRequestId) {
      summaryLoading.value = false
    }
  }
}

const loadExpensesWithSummary = async (page = currentPage.value) => {
  await Promise.all([fetchExpenses(page), refreshExpenseSummary()])
}

const fetchCategories = async () => {
  try {
    const data = await listAccountingExpenseCategories({ is_active: true })
    categories.value = data.results
  } catch {
    ElMessage.error('支出カテゴリの取得に失敗しました。')
  }
}

const searchExpenses = () => {
  loadExpensesWithSummary(1)
}

const clearFilters = () => {
  filters.value = {
    search: '',
    start_date: null,
    end_date: null,
    category: '',
    payment_method: '',
    is_reimbursed: '',
  }
  loadExpensesWithSummary(1)
}

const exportExpenses = async () => {
  exporting.value = true
  try {
    const result = await downloadAccountingExpensesExcel(filters.value)
    saveAs(result.blob, downloadFileName(result.contentDisposition))
  } catch {
    ElMessage.error('Excel出力に失敗しました。')
  } finally {
    exporting.value = false
  }
}

const openAddDialog = () => {
  addForm.value = createEmptyExpenseForm()
  addFormRef.value?.clearValidate()
  addDialogVisible.value = true
}

const submitAddExpense = async () => {
  if (!addFormRef.value) return
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createAccountingExpense(addForm.value)
    ElMessage.success('支出記録を作成しました。')
    addDialogVisible.value = false
    await loadExpensesWithSummary(1)
  } catch {
    ElMessage.error('支出記録の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const openBatchDialog = () => {
  batchText.value = ''
  batchRows.value = []
  batchDialogVisible.value = true
}

const parseBatchLine = (line: string, lineNumber: number): BatchExpenseRow | null => {
  if (!line) return null

  const cells = line.includes('\t') ? line.split('\t') : line.split(',')
  const normalizedCells = cells.map((cell) => cell.trim())

  if (lineNumber === 1 && ['日期', '日付', 'expense_date'].includes(normalizedCells[0])) {
    return null
  }

  const [expenseDate = '', place = '', category = '', amount = '', paymentMethod = '', expenseTarget = '', note = ''] =
    normalizedCells
  const errors: string[] = []

  if (!expenseDate) {
    errors.push('日期为空')
  } else if (!isValidDate(expenseDate)) {
    errors.push('日期格式不正确')
  }
  if (!category) {
    errors.push('类别为空')
  }
  if (!amount) {
    errors.push('金额为空')
  } else if (Number.isNaN(Number(amount))) {
    errors.push('金额不是数字')
  }

  return {
    lineNumber,
    expense_date: expenseDate,
    place,
    category,
    amount,
    payment_method: paymentMethod,
    expense_target: expenseTarget,
    note,
    errors,
  }
}

const previewBatch = () => {
  const rows = batchText.value
    .split(/\r?\n/)
    .map((line, index) => parseBatchLine(line.trim(), index + 1))
    .filter((row): row is BatchExpenseRow => Boolean(row))

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
  if (!validBatchRows.value.length) {
    ElMessage.warning('追加できる有効な行がありません。')
    return
  }

  batchSubmitting.value = true
  let successCount = 0
  let failedCount = invalidBatchRows.value.length

  for (const row of validBatchRows.value) {
    try {
      await createAccountingExpense({
        expense_date: row.expense_date,
        place: row.place,
        category: row.category,
        amount: row.amount,
        payment_method: row.payment_method,
        expense_target: row.expense_target,
        note: row.note,
        is_reimbursed: false,
        is_exported: false,
      })
      successCount += 1
    } catch {
      row.errors.push('保存に失敗しました')
      failedCount += 1
    }
  }

  batchSubmitting.value = false
  await loadExpensesWithSummary(1)
  ElMessage.success(`追加完了：成功 ${successCount} 件、失敗 ${failedCount} 件`)
  if (failedCount === 0) {
    batchDialogVisible.value = false
  }
}

const confirmDelete = async (expense: Expense) => {
  try {
    await ElMessageBox.confirm('この支出記録を削除します。よろしいですか？', '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingExpense(expense.id)
    ElMessage.success('支出記録を削除しました。')
    await loadExpensesWithSummary(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('支出記録の削除に失敗しました。')
    }
  }
}

onMounted(() => {
  loadExpensesWithSummary()
  fetchCategories()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>支出記録</h1>
          <p>日々の支出を確認し、必要な記録を追加できます</p>
        </div>
        <div class="accounting-toolbar">
          <el-button :loading="exporting" @click="exportExpenses">Excel出力</el-button>
          <el-button @click="openBatchDialog">批量追加</el-button>
          <el-button type="primary" @click="openAddDialog">新規支出</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="accounting-card">
      <div class="accounting-filter-card">
        <div class="accounting-filter-row">
          <el-input
            v-model="filters.search"
            placeholder="場所・対象・備考で検索"
            clearable
            class="accounting-filter-search"
          />
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
          <el-select v-model="filters.category" clearable placeholder="カテゴリ" class="accounting-filter-select">
            <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.name" />
          </el-select>
          <el-select v-model="filters.payment_method" clearable placeholder="支払方法" class="accounting-filter-select">
            <el-option v-for="method in paymentMethodOptions" :key="method" :label="method" :value="method" />
          </el-select>
          <el-select v-model="filters.is_reimbursed" clearable placeholder="精算済み" class="accounting-filter-select">
            <el-option v-for="option in boolOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <div class="accounting-filter-actions">
            <el-button type="primary" @click="searchExpenses">検索</el-button>
            <el-button @click="clearFilters">クリア</el-button>
          </div>
        </div>
      </div>

      <div class="accounting-summary-strip">
        <div class="accounting-summary-pill">
          <span>対象件数</span>
          <strong>{{ summaryLoaded || !summaryLoading ? `${summary.count.toLocaleString()}件` : '読込中' }}</strong>
        </div>
        <div class="accounting-summary-pill">
          <span>支出合計</span>
          <strong class="accounting-number">
            {{ summaryLoaded || !summaryLoading ? formatAccountingNumber(summary.totalExpense) : '読込中' }}
          </strong>
        </div>
        <div class="accounting-summary-pill">
          <span>帳面残高</span>
          <strong class="accounting-number">
            {{ summaryLoaded || !summaryLoading ? formatAccountingNumber(summary.balance) : '読込中' }}
          </strong>
        </div>
      </div>

      <el-table v-loading="loading" :data="expenses" stripe>
        <el-table-column label="日付" width="130">
          <template #default="{ row }">{{ formatDate(row.expense_date) }}</template>
        </el-table-column>
        <el-table-column prop="place" label="場所" min-width="150" />
        <el-table-column prop="category" label="カテゴリ" min-width="130" />
        <el-table-column label="金額" min-width="120" align="right" header-align="right">
          <template #default="{ row }"><span class="accounting-number">{{ formatAccountingNumber(row.amount) }}</span></template>
        </el-table-column>
        <el-table-column prop="payment_method" label="支払方法" min-width="130" />
        <el-table-column prop="expense_target" label="費用対象" min-width="160" />
        <el-table-column prop="note" label="備考" min-width="220" show-overflow-tooltip />
        <el-table-column label="精算済み" width="110">
          <template #default="{ row }">{{ formatBoolean(row.is_reimbursed) }}</template>
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
                  <el-dropdown-item @click="router.push(`/accounting/expenses/${row.id}/edit`)">編集</el-dropdown-item>
                  <el-dropdown-item divided class="danger-item" @click="confirmDelete(row)">削除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <p v-if="!loading && !expenses.length" class="empty-text">データがありません</p>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchExpenses"
        />
      </div>
    </el-card>

    <el-dialog v-model="addDialogVisible" title="支出記録を追加" width="720px" class="accounting-expense-dialog">
      <el-form ref="addFormRef" :model="addForm" :rules="addRules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="日付" prop="expense_date">
            <el-date-picker
              v-model="addForm.expense_date"
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
          <el-form-item label="カテゴリ" prop="category">
            <el-select v-model="addForm.category" placeholder="選択してください" class="form-control">
              <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.name" />
            </el-select>
          </el-form-item>
          <el-form-item label="金額" prop="amount">
            <el-input v-model="addForm.amount" inputmode="numeric" />
          </el-form-item>
          <el-form-item label="支払方法" prop="payment_method">
            <el-select v-model="addForm.payment_method" clearable placeholder="選択してください" class="form-control">
              <el-option v-for="method in paymentMethodOptions" :key="method" :label="method" :value="method" />
            </el-select>
          </el-form-item>
          <el-form-item label="費用対象" prop="expense_target">
            <el-input v-model="addForm.expense_target" />
          </el-form-item>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full">
            <el-input v-model="addForm.note" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item class="accounting-dialog-full">
            <el-checkbox v-model="addForm.is_reimbursed">精算済み</el-checkbox>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAddExpense">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="batchDialogVisible" title="支出記録を一括追加" width="920px" class="accounting-batch-dialog">
      <div class="accounting-batch-help">
        请按以下格式粘贴，每行一条：
        <code>日期	地点	类别	金额	支付方式	费用对象	备注
2026-07-01	事务所	停车费	1200	个人垫付	公司内部	大阪停车
2026-07-02,役所,住民票,300,现金,王先生,住民票取得</code>
      </div>
      <el-input v-model="batchText" type="textarea" :rows="8" placeholder="Excel からコピーした内容を貼り付け" />
      <div class="accounting-batch-actions">
        <el-button @click="previewBatch">预览</el-button>
        <el-button type="primary" :loading="batchSubmitting" @click="submitBatch">确认追加</el-button>
      </div>
      <el-table v-if="batchRows.length" :data="batchRows" max-height="320" stripe>
        <el-table-column prop="lineNumber" label="行" width="70" />
        <el-table-column prop="expense_date" label="日期" width="120" />
        <el-table-column prop="place" label="地点" min-width="120" />
        <el-table-column prop="category" label="类别" min-width="120" />
        <el-table-column prop="amount" label="金额" width="110" align="right" header-align="right" />
        <el-table-column prop="payment_method" label="支付方式" min-width="120" />
        <el-table-column prop="expense_target" label="费用对象" min-width="140" />
        <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" min-width="180">
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
