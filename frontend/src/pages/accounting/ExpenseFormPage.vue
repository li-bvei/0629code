<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  createAccountingExpense,
  getAccountingExpense,
  getExpenseCategorySuggestions,
  listAccountingExpenseCategories,
  updateAccountingExpense,
} from '../../api/accounting'
import RemoteCaseSelect from '../../components/RemoteCaseSelect.vue'
import RemoteCompanySelect from '../../components/RemoteCompanySelect.vue'
import RemoteCustomerSelect from '../../components/RemoteCustomerSelect.vue'
import type { ExpenseCategory, ExpenseCategorySuggestions, ExpensePayload } from '../../types/accounting'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)
const categories = ref<ExpenseCategory[]>([])
const expenseId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => Boolean(expenseId.value))

const paymentMethodOptions = ['现金', '信用卡', '银行转账', 'PayPay', 'ICOCA', '公司账户', '个人垫付', '其他']
const form = ref<ExpensePayload>({
  expense_date: '',
  place: '',
  category: '',
  amount: '',
  payment_method: '',
  expense_target: '',
  note: '',
  is_exported: false,
  customer: null,
  company: null,
  case: null,
})
const caseInitial = ref<{ value: number, label: string } | null>(null)

// --- カテゴリ入力支援：本人の履歴だけを使った候補・規範名の提案・推薦（最終決定は利用者） ---
const suggestions = ref<ExpenseCategorySuggestions | null>(null)
let suggestionTimer: ReturnType<typeof setTimeout> | null = null
let suggestionRequest = 0
const loadSuggestions = async () => {
  const requestId = ++suggestionRequest
  try {
    const data = await getExpenseCategorySuggestions({
      q: form.value.category || '',
      place: form.value.place || '',
      expense_target: form.value.expense_target || '',
      note: form.value.note || '',
    })
    if (requestId === suggestionRequest) suggestions.value = data
  } catch {
    if (requestId === suggestionRequest) suggestions.value = null
  }
}
const scheduleSuggestions = () => {
  if (suggestionTimer) clearTimeout(suggestionTimer)
  suggestionTimer = setTimeout(loadSuggestions, 300)
}
const fetchCategoryCandidates = async (query: string, callback: (items: Array<{ value: string }>) => void) => {
  try {
    const data = await getExpenseCategorySuggestions({ q: query })
    const names = new Set(data.matches.map((row) => row.name))
    categories.value.forEach((category) => {
      if (!query || category.name.includes(query)) names.add(category.name)
    })
    callback([...names].slice(0, 20).map((value) => ({ value })))
  } catch {
    callback(categories.value.map((category) => ({ value: category.name })))
  }
}
const applyCategory = (name: string) => {
  form.value.category = name
  scheduleSuggestions()
}
const recommendations = computed(() =>
  (suggestions.value?.recommendations ?? []).filter((row) => row.name !== form.value.category),
)

const rules: FormRules<ExpensePayload> = {
  expense_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  category: [{ required: true, message: 'カテゴリを選択してください。', trigger: 'change' }],
  amount: [{ required: true, message: '金額を入力してください。', trigger: 'blur' }],
}

const fetchCategories = async () => {
  const data = await listAccountingExpenseCategories({ is_active: true })
  categories.value = data.results
  if (!categories.value.length) {
    ElMessage.warning('先に支出カテゴリを登録してください')
  }
}

const fetchExpense = async () => {
  if (!expenseId.value) return
  const expense = await getAccountingExpense(expenseId.value)
  form.value = {
    expense_date: expense.expense_date,
    place: expense.place,
    category: expense.category,
    amount: expense.amount,
    payment_method: expense.payment_method,
    expense_target: expense.expense_target,
    note: expense.note,
    is_exported: false,
    customer: expense.customer ?? null,
    company: expense.company ?? null,
    case: expense.case ?? null,
  }
  caseInitial.value = expense.case ? { value: expense.case, label: expense.case_number || `#${expense.case}` } : null
}

const submit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (expenseId.value) {
      await updateAccountingExpense(expenseId.value, form.value)
      ElMessage.success('支出記録を更新しました。')
    } else {
      await createAccountingExpense(form.value)
      ElMessage.success('支出記録を作成しました。')
    }
    router.push('/accounting/expenses')
  } catch (error) {
    const response = (error as { response?: { status?: number; data?: { detail?: string } } })?.response
    ElMessage.error(
      response?.status === 403 && response.data?.detail
        ? response.data.detail
        : isEdit.value ? '支出記録の更新に失敗しました。' : '支出記録の作成に失敗しました。',
    )
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchCategories()
    await fetchExpense()
    await loadSuggestions()
  } catch {
    ElMessage.error('データの取得に失敗しました。')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>{{ isEdit ? '支出記録編集' : '新規支出' }}</h1>
      <el-button @click="router.push('/accounting/expenses')">戻る</el-button>
    </div>

    <el-card v-loading="loading" shadow="never">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="日付" prop="expense_date">
            <el-date-picker
              v-model="form.expense_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="場所" prop="place">
            <el-input v-model="form.place" @input="scheduleSuggestions" />
          </el-form-item>
          <el-form-item label="カテゴリ" prop="category">
            <el-autocomplete
              v-model="form.category"
              :fetch-suggestions="fetchCategoryCandidates"
              placeholder="検索または手入力"
              clearable
              class="form-control"
              @input="scheduleSuggestions"
              @select="scheduleSuggestions"
            />
            <div v-if="suggestions?.normalized" class="field-hint category-hint">
              {{ suggestions.normalized.reason }}：
              <el-button link type="primary" @click="applyCategory(suggestions.normalized.suggestion)">「{{ suggestions.normalized.suggestion }}」を使う</el-button>
              （入力のまま保存もできます）
            </div>
            <div v-if="recommendations.length" class="field-hint category-hint">
              過去の記録からの候補：
              <el-button v-for="row in recommendations" :key="row.name" link type="primary" :title="row.reason" @click="applyCategory(row.name)">{{ row.name }}</el-button>
            </div>
          </el-form-item>
          <el-form-item label="金額" prop="amount">
            <el-input v-model="form.amount" inputmode="numeric" />
          </el-form-item>
          <el-form-item label="支払方法" prop="payment_method">
            <el-select v-model="form.payment_method" clearable placeholder="選択してください" class="form-control">
              <el-option v-for="method in paymentMethodOptions" :key="method" :label="method" :value="method" />
            </el-select>
          </el-form-item>
          <el-form-item label="費用対象" prop="expense_target">
            <el-input v-model="form.expense_target" @input="scheduleSuggestions" />
          </el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="関連案件（任意）" prop="case">
            <RemoteCaseSelect v-model="form.case" :initial-option="caseInitial" />
            <div class="field-hint">担当している案件だけ関連付けできます。案件の経過には日付とカテゴリだけが記録され、金額は載りません。</div>
          </el-form-item>
          <el-form-item label="関連顧客（任意）" prop="customer">
            <RemoteCustomerSelect v-model="form.customer" />
          </el-form-item>
          <el-form-item label="関連会社（任意）" prop="company">
            <RemoteCompanySelect v-model="form.company" />
          </el-form-item>
        </div>
        <el-form-item label="備考" prop="note">
          <el-input v-model="form.note" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <el-button @click="router.push('/accounting/expenses')">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-card>
  </section>
</template>

<style scoped>
.category-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}
</style>
