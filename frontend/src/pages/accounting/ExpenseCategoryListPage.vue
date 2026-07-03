<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  createAccountingExpenseCategory,
  deleteAccountingExpenseCategory,
  listAccountingExpenseCategories,
  updateAccountingExpenseCategory,
} from '../../api/accounting'
import type { AccountingListParams, ExpenseCategory, ExpenseCategoryPayload } from '../../types/accounting'
import { formatDateTime } from '../../utils/date'
import './accounting.css'

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const categories = ref<ExpenseCategory[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filters = ref<AccountingListParams>({
  search: '',
  is_active: '',
})
const addDialogVisible = ref(false)
const addFormRef = ref<FormInstance>()
const submitting = ref(false)
const addForm = ref<ExpenseCategoryPayload>({
  name: '',
  is_active: true,
  sort_order: 0,
})
const boolOptions = [
  { label: '有効', value: 'true' },
  { label: '無効', value: 'false' },
]

const rules: FormRules<ExpenseCategoryPayload> = {
  name: [{ required: true, message: 'カテゴリ名を入力してください。', trigger: 'blur' }],
}

const fetchCategories = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listAccountingExpenseCategories({ ...filters.value, page })
    categories.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = '支出カテゴリの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const clearFilters = () => {
  filters.value = { search: '', is_active: '' }
  fetchCategories(1)
}

const openAddDialog = () => {
  addForm.value = {
    name: '',
    is_active: true,
    sort_order: 0,
  }
  addFormRef.value?.clearValidate()
  addDialogVisible.value = true
}

const submitAddCategory = async () => {
  if (!addFormRef.value) return
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createAccountingExpenseCategory(addForm.value)
    ElMessage.success('支出カテゴリを作成しました。')
    addDialogVisible.value = false
    await fetchCategories(1)
  } catch {
    ElMessage.error('支出カテゴリの作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const toggleActive = async (category: ExpenseCategory) => {
  try {
    await updateAccountingExpenseCategory(category.id, { is_active: !category.is_active })
    ElMessage.success(category.is_active ? 'カテゴリを無効にしました。' : 'カテゴリを有効にしました。')
    await fetchCategories(currentPage.value)
  } catch {
    ElMessage.error('カテゴリ状態の更新に失敗しました。')
  }
}

const confirmDelete = async (category: ExpenseCategory) => {
  try {
    await ElMessageBox.confirm(`「${category.name}」を削除します。よろしいですか？`, '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingExpenseCategory(category.id)
    ElMessage.success('支出カテゴリを削除しました。')
    await fetchCategories(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('支出カテゴリの削除に失敗しました。')
    }
  }
}

onMounted(() => {
  fetchCategories()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>支出カテゴリ</h1>
          <p>支出記録で使用するカテゴリを管理します</p>
        </div>
        <div class="accounting-toolbar">
          <el-button type="primary" @click="openAddDialog">新規追加</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="accounting-card">
      <div class="accounting-filter-card">
        <div class="accounting-filter-row">
          <el-input v-model="filters.search" placeholder="カテゴリ名で検索" clearable class="accounting-filter-search" />
          <el-select v-model="filters.is_active" clearable placeholder="有効状態" class="accounting-filter-select">
            <el-option v-for="option in boolOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <div class="accounting-filter-actions">
            <el-button type="primary" @click="fetchCategories(1)">検索</el-button>
            <el-button @click="clearFilters">クリア</el-button>
          </div>
        </div>
      </div>

      <el-table v-loading="loading" :data="categories" stripe>
        <el-table-column prop="name" label="カテゴリ名" min-width="180" />
        <el-table-column label="有効" width="100">
          <template #default="{ row }">{{ row.is_active ? '有効' : '無効' }}</template>
        </el-table-column>
        <el-table-column prop="sort_order" label="並び順" width="100" />
        <el-table-column label="作成日時" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="router.push(`/accounting/expense-categories/${row.id}/edit`)">編集</el-button>
            <el-button text type="primary" @click="toggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button text type="danger" @click="confirmDelete(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!loading && !categories.length" class="empty-text">データがありません</p>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchCategories"
        />
      </div>
    </el-card>

    <el-dialog v-model="addDialogVisible" title="支出カテゴリを追加" width="520px">
      <el-form ref="addFormRef" :model="addForm" :rules="rules" label-position="top">
        <el-form-item label="カテゴリ名" prop="name">
          <el-input v-model="addForm.name" />
        </el-form-item>
        <el-form-item label="並び順" prop="sort_order">
          <el-input v-model.number="addForm.sort_order" inputmode="numeric" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="addForm.is_active">有効</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAddCategory">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
