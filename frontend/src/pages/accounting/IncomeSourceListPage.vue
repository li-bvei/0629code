<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  createAccountingIncomeSource,
  deleteAccountingIncomeSource,
  listAccountingIncomeSources,
} from '../../api/accounting'
import type { AccountingListParams, IncomeSource, IncomeSourcePayload } from '../../types/accounting'
import { formatDate } from '../../utils/date'
import './accounting.css'

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const incomeSources = ref<IncomeSource[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filters = ref<AccountingListParams>({
  search: '',
  start_date: null,
  end_date: null,
})
const addDialogVisible = ref(false)
const addFormRef = ref<FormInstance>()
const submitting = ref(false)
const addForm = ref<IncomeSourcePayload>({
  source_date: '',
  source_target: '',
  amount: '',
  note: '',
  is_exported: false,
})

const rules: FormRules<IncomeSourcePayload> = {
  source_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  amount: [{ required: true, message: '金額を入力してください。', trigger: 'blur' }],
}

const formatCurrency = (value: number | string) => `¥ ${Number(value || 0).toLocaleString()}`

const fetchIncomeSources = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listAccountingIncomeSources({ ...filters.value, page })
    incomeSources.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = '収入来源の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const clearFilters = () => {
  filters.value = {
    search: '',
    start_date: null,
    end_date: null,
  }
  fetchIncomeSources(1)
}

const openAddDialog = () => {
  addForm.value = {
    source_date: '',
    source_target: '',
    amount: '',
    note: '',
    is_exported: false,
  }
  addFormRef.value?.clearValidate()
  addDialogVisible.value = true
}

const submitAddIncomeSource = async () => {
  if (!addFormRef.value) return
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createAccountingIncomeSource(addForm.value)
    ElMessage.success('収入来源を作成しました。')
    addDialogVisible.value = false
    await fetchIncomeSources(1)
  } catch {
    ElMessage.error('収入来源の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const confirmDelete = async (incomeSource: IncomeSource) => {
  try {
    await ElMessageBox.confirm('この収入来源を削除します。よろしいですか？', '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingIncomeSource(incomeSource.id)
    ElMessage.success('収入来源を削除しました。')
    await fetchIncomeSources(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('収入来源の削除に失敗しました。')
    }
  }
}

onMounted(() => {
  fetchIncomeSources()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>収入来源</h1>
          <p>入金や資金来源を記録します</p>
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
          <el-input v-model="filters.search" placeholder="対象・備考で検索" clearable class="accounting-filter-search" />
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
          <div class="accounting-filter-actions">
            <el-button type="primary" @click="fetchIncomeSources(1)">検索</el-button>
            <el-button @click="clearFilters">クリア</el-button>
          </div>
        </div>
      </div>

      <el-table v-loading="loading" :data="incomeSources" stripe>
        <el-table-column label="日付" width="130">
          <template #default="{ row }">{{ formatDate(row.source_date) }}</template>
        </el-table-column>
        <el-table-column prop="source_target" label="対象" min-width="180" />
        <el-table-column label="金額" min-width="120" align="right" header-align="right">
          <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="note" label="備考" min-width="240" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="router.push(`/accounting/income-sources/${row.id}/edit`)">編集</el-button>
            <el-button text type="danger" @click="confirmDelete(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!loading && !incomeSources.length" class="empty-text">データがありません</p>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchIncomeSources"
        />
      </div>
    </el-card>

    <el-dialog v-model="addDialogVisible" title="収入来源を追加" width="640px">
      <el-form ref="addFormRef" :model="addForm" :rules="rules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="日付" prop="source_date">
            <el-date-picker
              v-model="addForm.source_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="対象" prop="source_target">
            <el-input v-model="addForm.source_target" />
          </el-form-item>
          <el-form-item label="金額" prop="amount">
            <el-input v-model="addForm.amount" inputmode="numeric" />
          </el-form-item>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full">
            <el-input v-model="addForm.note" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAddIncomeSource">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
