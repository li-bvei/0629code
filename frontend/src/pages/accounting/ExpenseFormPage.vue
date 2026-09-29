<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  createAccountingExpense,
  getAccountingExpense,
  listAccountingExpenseCategories,
  updateAccountingExpense,
} from '../../api/accounting'
import ExpenseFormFields from '../../components/accounting/ExpenseFormFields.vue'
import type { ExpenseCategory, ExpensePayload } from '../../types/accounting'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)
const categories = ref<ExpenseCategory[]>([])
const expenseId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => Boolean(expenseId.value))

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
        <ExpenseFormFields v-model="form" :categories="categories" :case-initial="caseInitial" />
      </el-form>

      <div class="form-actions">
        <el-button @click="router.push('/accounting/expenses')">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-card>
  </section>
</template>
