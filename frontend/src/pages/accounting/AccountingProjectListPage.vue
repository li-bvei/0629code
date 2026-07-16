<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { deleteAccountingProject, listAccountingProjects, updateAccountingProject } from '../../api/accounting'
import type { AccountingListParams, AccountingProject } from '../../types/accounting'
import { formatAccountingNumber, toAccountingNumber } from '../../utils/accountingFormat'
import { formatDate, formatDateTime } from '../../utils/date'
import './accounting.css'

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const projects = ref<AccountingProject[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filters = ref<AccountingListParams>({
  search: '',
  is_active: '',
})
const boolOptions = [
  { label: '有効', value: 'true' },
  { label: '無効', value: 'false' },
]

const fetchProjects = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listAccountingProjects({ ...filters.value, page })
    projects.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = 'プロジェクト収支表の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const searchProjects = () => {
  fetchProjects(1)
}

const clearFilters = () => {
  filters.value = { search: '', is_active: '' }
  searchProjects()
}

const confirmDelete = async (project: AccountingProject) => {
  try {
    await ElMessageBox.confirm(`「${project.name}」を削除します。よろしいですか？`, '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingProject(project.id)
    ElMessage.success('プロジェクト収支表を削除しました。')
    await fetchProjects(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('プロジェクト収支表の削除に失敗しました。')
    }
  }
}

const setProjectActive = async (project: AccountingProject, isActive: boolean) => {
  try {
    await updateAccountingProject(project.id, { is_active: isActive })
    ElMessage.success(isActive ? '有効化しました。' : '無効化しました。')
    await fetchProjects(currentPage.value)
  } catch {
    ElMessage.error('状態の更新に失敗しました。')
  }
}

onMounted(() => {
  fetchProjects()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>プロジェクト収支表</h1>
          <p>案件・店舗・月別業務など、個別プロジェクトの収入と支出をまとめて管理できます。</p>
        </div>
        <div class="accounting-toolbar">
          <el-button type="primary" @click="router.push('/accounting/projects/new')">新規追加</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="accounting-card">
      <div class="accounting-filter-card">
        <div class="accounting-filter-row">
          <el-input v-model="filters.search" placeholder="项目名称・说明・备注で検索" clearable class="accounting-filter-search" />
          <el-select v-model="filters.is_active" clearable placeholder="有効状態" class="accounting-filter-select">
            <el-option v-for="option in boolOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <div class="accounting-filter-actions">
            <el-button type="primary" @click="searchProjects">検索</el-button>
            <el-button @click="clearFilters">クリア</el-button>
          </div>
        </div>
      </div>

      <div class="project-list-count">{{ total.toLocaleString() }}件</div>

      <el-table v-loading="loading" :data="projects" stripe>
        <el-table-column label="プロジェクト名" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <button class="entity-link" type="button" :title="row.name" @click="router.push(`/accounting/projects/${row.id}`)">
              {{ row.name }}
            </button>
          </template>
        </el-table-column>
        <el-table-column label="開始日" width="120">
          <template #default="{ row }">{{ formatDate(row.start_date) }}</template>
        </el-table-column>
        <el-table-column label="終了日" width="120">
          <template #default="{ row }">{{ formatDate(row.end_date) }}</template>
        </el-table-column>
        <el-table-column label="収入" width="130" align="right" header-align="right">
          <template #default="{ row }"><span class="accounting-number">{{ formatAccountingNumber(row.income_total || 0) }}</span></template>
        </el-table-column>
        <el-table-column label="支出" width="130" align="right" header-align="right">
          <template #default="{ row }"><span class="accounting-number">{{ formatAccountingNumber(row.expense_total || 0) }}</span></template>
        </el-table-column>
        <el-table-column label="残高" width="130" align="right" header-align="right">
          <template #default="{ row }">
            <span class="accounting-number" :class="{ 'is-negative': toAccountingNumber(row.balance || 0) < 0 }">
              {{ formatAccountingNumber(row.balance || 0) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="有効" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '有効' : '無効' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="備考" min-width="220" show-overflow-tooltip />
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
                  <el-dropdown-item @click="router.push(`/accounting/projects/${row.id}`)">詳細</el-dropdown-item>
                  <el-dropdown-item @click="router.push(`/accounting/projects/${row.id}/edit`)">編集</el-dropdown-item>
                  <el-dropdown-item v-if="row.is_active" divided @click="setProjectActive(row, false)">無効化</el-dropdown-item>
                  <el-dropdown-item v-else divided @click="setProjectActive(row, true)">有効化</el-dropdown-item>
                  <el-dropdown-item divided class="danger-item" @click="confirmDelete(row)">削除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!loading && !projects.length" class="empty-text">データがありません</p>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchProjects"
        />
      </div>
    </el-card>
  </section>
</template>
