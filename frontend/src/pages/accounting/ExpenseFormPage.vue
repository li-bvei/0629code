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
import type { ExpenseCategory, ExpensePayload } from '../../types/accounting'

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
  is_reimbursed: false,
  is_exported: false,
})

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
    is_reimbursed: expense.is_reimbursed,
    is_exported: false,
  }
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
  } catch {
    ElMessage.error(isEdit.value ? '支出記録の更新に失敗しました。' : '支出記録の作成に失敗しました。')
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
            <el-input v-model="form.place" />
          </el-form-item>
          <el-form-item label="カテゴリ" prop="category">
            <el-select v-model="form.category" placeholder="選択してください" class="form-control">
              <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.name" />
            </el-select>
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
            <el-input v-model="form.expense_target" />
          </el-form-item>
        </div>
        <el-form-item label="備考" prop="note">
          <el-input v-model="form.note" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="form.is_reimbursed">精算済み</el-checkbox>
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <el-button @click="router.push('/accounting/expenses')">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-card>
  </section>
</template>
