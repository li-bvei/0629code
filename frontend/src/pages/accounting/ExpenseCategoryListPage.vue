<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  createAccountingExpenseCategory,
  createExpenseCategoryRule,
  deleteAccountingExpenseCategory,
  deleteExpenseCategoryRule,
  listAccountingExpenseCategories,
  listExpenseCategoryRules,
  promoteExpenseCategoryRule,
  updateAccountingExpenseCategory,
  updateExpenseCategoryRule,
} from '../../api/accounting'
import { useAuthStore } from '../../stores/auth'
import type {
  AccountingListParams, ExpenseCategory, ExpenseCategoryPayload, ExpenseCategoryRule, ExpenseCategoryRulePayload,
} from '../../types/accounting'
import { describeApiErrors, responseOf } from '../../utils/apiErrors'
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

// --- カテゴリ提案の規則（場所などに含まれる文字 → カテゴリ）。manage_expense_category を持つ人だけ ---
const auth = useAuthStore()
const canManageRules = auth.can('accounting.manage_expense_category')
const ruleRows = ref<ExpenseCategoryRule[]>([])
const ruleTotal = ref(0)
const rulePage = ref(1)
const ruleLoading = ref(false)
const ruleDialogVisible = ref(false)
const ruleSaving = ref(false)
const ruleCategoryOptions = ref<ExpenseCategory[]>([])
const matchFieldOptions = [
  { value: 'place', label: '場所' }, { value: 'expense_target', label: '費用対象' }, { value: 'note', label: '備考' },
] as const
const emptyRule = (): ExpenseCategoryRulePayload => ({ pattern: '', match_field: 'place', expense_category: 0, priority: 0, is_active: true })
const ruleForm = ref<ExpenseCategoryRulePayload>(emptyRule())
const ruleErrorText = (error: unknown, fallback: string) => {
  const { status, data } = responseOf(error)
  if (status === 403) return 'カテゴリ提案の規則を管理する権限がありません。'
  return describeApiErrors(data, { pattern: '文字', expense_category: 'カテゴリ', match_field: '対象項目', priority: '優先度' }).join(' ') || fallback
}
const fetchRules = async (page = rulePage.value) => {
  if (!canManageRules) return
  ruleLoading.value = true
  try {
    const data = await listExpenseCategoryRules(page)
    ruleRows.value = data.results
    ruleTotal.value = data.count
    rulePage.value = page
  } catch (error) {
    ElMessage.error(ruleErrorText(error, 'カテゴリ提案の規則を取得できませんでした。'))
  } finally {
    ruleLoading.value = false
  }
}
const searchRuleCategories = async (query: string) => {
  try {
    ruleCategoryOptions.value = (await listAccountingExpenseCategories({ search: query, is_active: 'true' })).results
  } catch {
    ruleCategoryOptions.value = []
  }
}
const openRuleDialog = () => {
  ruleForm.value = emptyRule()
  searchRuleCategories('')
  ruleDialogVisible.value = true
}
const submitRule = async () => {
  if (!ruleForm.value.pattern.trim() || !ruleForm.value.expense_category) {
    ElMessage.warning('文字とカテゴリを入力してください。')
    return
  }
  ruleSaving.value = true
  try {
    await createExpenseCategoryRule(ruleForm.value)
    ElMessage.success('規則を追加しました。')
    ruleDialogVisible.value = false
    await fetchRules(1)
  } catch (error) {
    ElMessage.error(ruleErrorText(error, '規則を追加できませんでした。'))
  } finally {
    ruleSaving.value = false
  }
}
const toggleRule = async (rule: ExpenseCategoryRule) => {
  try {
    await updateExpenseCategoryRule(rule.id, { is_active: !rule.is_active })
    await fetchRules()
  } catch (error) {
    ElMessage.error(ruleErrorText(error, '規則を更新できませんでした。'))
  }
}
// 利用者が記憶した本人用の規則を事務所共通にする（全員の提案に出るようになるため確認する）
const confirmPromoteRule = async (rule: ExpenseCategoryRule) => {
  try {
    await ElMessageBox.confirm(
      `${rule.owner_name} さんが記憶した ${rule.match_field_display}「${rule.pattern}」→「${rule.expense_category_name}」を事務所共通の規則にします。全員の入力画面で提案されるようになります。よろしいですか？`,
      '事務所共通にする', { confirmButtonText: '事務所共通にする', cancelButtonText: 'キャンセル', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await promoteExpenseCategoryRule(rule.id)
    ElMessage.success('事務所共通の規則にしました。')
    await fetchRules()
  } catch (error) {
    ElMessage.error(ruleErrorText(error, '事務所共通にできませんでした。'))
  }
}
const confirmDeleteRule = async (rule: ExpenseCategoryRule) => {
  try {
    await ElMessageBox.confirm(`${rule.match_field_display}「${rule.pattern}」→「${rule.expense_category_name}」の規則を削除します。よろしいですか？`, '削除確認', {
      confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteExpenseCategoryRule(rule.id)
    ElMessage.success('規則を削除しました。')
    await fetchRules()
  } catch (error) {
    ElMessage.error(ruleErrorText(error, '規則を削除できませんでした。'))
  }
}

onMounted(() => {
  fetchCategories()
  fetchRules(1)
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
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button text type="primary" class="table-action-trigger">
                操作
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="router.push(`/accounting/expense-categories/${row.id}/edit`)">編集</el-dropdown-item>
                  <el-dropdown-item divided @click="toggleActive(row)">
                    {{ row.is_active ? '停用' : '启用' }}
                  </el-dropdown-item>
                  <el-dropdown-item divided class="danger-item" @click="confirmDelete(row)">削除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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

    <el-card v-if="canManageRules" shadow="never" class="accounting-card rule-card">
      <template #header>
        <div class="page-header-row">
          <div>
            <strong>カテゴリ提案の規則</strong>
            <p class="rule-sub">場所などに決まった文字が含まれるとき、支出の入力画面でカテゴリを提案します（提案だけで、自動では変更しません）。入力時に記憶された規則は本人だけに効き、ここで事務所共通にできます。</p>
          </div>
          <el-button type="primary" plain @click="openRuleDialog">規則を追加</el-button>
        </div>
      </template>
      <el-table v-loading="ruleLoading" :data="ruleRows" stripe>
        <el-table-column prop="match_field_display" label="対象項目" width="110" />
        <el-table-column prop="pattern" label="含まれる文字" min-width="160" />
        <el-table-column prop="expense_category_name" label="提案するカテゴリ" min-width="150" />
        <el-table-column label="範囲" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.scope === 'office'" size="small" type="success">事務所共通</el-tag>
            <el-tag v-else size="small" type="info">本人のみ：{{ row.owner_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_display" label="登録元" width="130" />
        <el-table-column prop="priority" label="優先度" width="90" />
        <el-table-column label="有効" width="90">
          <template #default="{ row }">{{ row.is_active ? '有効' : '無効' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="270" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.scope === 'personal'" link type="primary" @click="confirmPromoteRule(row)">事務所共通にする</el-button>
            <el-button link type="primary" @click="toggleRule(row)">{{ row.is_active ? '無効にする' : '有効にする' }}</el-button>
            <el-button link type="danger" @click="confirmDeleteRule(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!ruleLoading && !ruleRows.length" class="empty-text">規則がありません</p>
      <div class="table-footer">
        <el-pagination layout="prev, pager, next" :current-page="rulePage" :page-size="pageSize" :total="ruleTotal" @current-change="fetchRules" />
      </div>
    </el-card>

    <el-dialog v-model="ruleDialogVisible" title="カテゴリ提案の規則を追加（事務所共通）" width="520px">
      <el-form :model="ruleForm" label-position="top">
        <el-form-item label="対象項目">
          <el-select v-model="ruleForm.match_field" style="width: 100%">
            <el-option v-for="option in matchFieldOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="含まれる文字（例：駐車場）">
          <el-input v-model="ruleForm.pattern" maxlength="100" />
        </el-form-item>
        <el-form-item label="提案するカテゴリ">
          <el-select v-model="ruleForm.expense_category" filterable remote :remote-method="searchRuleCategories"
                     placeholder="カテゴリを検索" style="width: 100%">
            <el-option v-for="category in ruleCategoryOptions" :key="category.id" :label="category.name" :value="category.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="優先度（大きいほど優先）">
          <el-input v-model.number="ruleForm.priority" inputmode="numeric" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="submitRule">保存</el-button>
      </template>
    </el-dialog>

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

<style scoped>
.rule-card {
  margin-top: 16px;
}

.rule-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
