<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listDashboardDeadlines } from '../api/dashboard'
import { listCases } from '../api/cases'
import type { Case, DashboardDeadline } from '../types/api'
import { formatDate, formatDateTime } from '../utils/date'
import { diffDaysFromToday } from '../utils/reminder'

const loading = ref(false)
const errorMessage = ref('')
const deadlines = ref<DashboardDeadline[]>([])
const cases = ref<Case[]>([])

const deadlineItems = computed(() =>
  [...deadlines.value].sort((a, b) => a.days_left - b.days_left),
)

const recentCases = computed(() =>
  [...cases.value].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 10),
)

const inProgressCases = computed(() => (
  [...cases.value]
    .filter((caseItem) => caseItem.applied_at && !['完了', '中止', 'completed'].includes(caseItem.status))
    .sort((a, b) => (a.applied_at || '').localeCompare(b.applied_at || ''))
    .slice(0, 10)
))

const getElapsedDays = (dateKey?: string | null) => {
  const days = diffDaysFromToday(dateKey)
  if (days === null) return '-'
  return days <= 0 ? `申請から${Math.abs(days)}日` : '申請日前'
}

const getElapsedTagType = (dateKey?: string | null) => {
  const days = diffDaysFromToday(dateKey)
  if (days === null || days > 0) return 'info'
  const elapsedDays = Math.abs(days)
  if (elapsedDays >= 60) return 'danger'
  if (elapsedDays >= 30) return 'warning'
  return 'info'
}

const formatDeadlineDays = (daysLeft: number) => {
  if (daysLeft < 0) return `期限切れ ${Math.abs(daysLeft)}日`
  if (daysLeft === 0) return '本日期限'
  return `期限まであと ${daysLeft}日`
}

const getDeadlineTagType = (daysLeft: number) => {
  if (daysLeft < 0) return 'danger'
  if (daysLeft <= 30) return 'warning'
  return 'info'
}

const fetchDashboard = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [deadlineData, caseData] = await Promise.all([
      listDashboardDeadlines(),
      listCases(),
    ])
    deadlines.value = deadlineData
    cases.value = caseData.results
  } catch {
    errorMessage.value = 'ダッシュボードデータの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboard()
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>ダッシュボード</h1>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <div v-loading="loading" class="detail-grid">
      <el-card shadow="never">
        <template #header>期限提醒</template>
        <el-table v-if="deadlineItems.length" :data="deadlineItems" stripe>
          <el-table-column prop="target_name" label="対象" min-width="160" />
          <el-table-column prop="deadline_label" label="期限種別" min-width="140" />
          <el-table-column label="期限日" width="130">
            <template #default="{ row }">{{ formatDate(row.deadline_date) }}</template>
          </el-table-column>
          <el-table-column label="残り日数" min-width="160">
            <template #default="{ row }">
              <el-tag :type="getDeadlineTagType(row.days_left)">
                {{ formatDeadlineDays(row.days_left) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="案件番号" min-width="140">
            <template #default="{ row }">
              <router-link v-if="row.case_id" class="text-link" :to="`/cases/${row.case_id}`">
                {{ row.case_number }}
              </router-link>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="case_type" label="案件種別" min-width="150" />
        </el-table>
        <p v-else class="empty-text">該当データなし</p>
      </el-card>

      <el-card shadow="never">
        <template #header>申請中案件</template>
        <el-table v-if="inProgressCases.length" :data="inProgressCases" stripe>
          <el-table-column label="案件番号" min-width="140">
            <template #default="{ row }">
              <router-link class="text-link" :to="`/cases/${row.id}`">
                {{ row.case_number }}
              </router-link>
            </template>
          </el-table-column>
          <el-table-column prop="customer_name" label="顧客名" min-width="140" />
          <el-table-column prop="company_name" label="会社名" min-width="160">
            <template #default="{ row }">{{ row.company_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="case_type" label="案件種別" min-width="150" />
          <el-table-column label="申請日" width="130">
            <template #default="{ row }">{{ formatDate(row.applied_at) }}</template>
          </el-table-column>
          <el-table-column label="経過日数" min-width="140">
            <template #default="{ row }">
              <el-tag :type="getElapsedTagType(row.applied_at)">
                {{ getElapsedDays(row.applied_at) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="ステータス" width="120" />
        </el-table>
        <p v-else class="empty-text">申請中の案件はありません</p>
      </el-card>

      <el-card shadow="never">
        <template #header>最近更新された案件</template>
        <el-table v-if="recentCases.length" :data="recentCases" stripe>
          <el-table-column label="案件番号" min-width="140">
            <template #default="{ row }">
              <router-link class="text-link" :to="`/cases/${row.id}`">
                {{ row.case_number }}
              </router-link>
            </template>
          </el-table-column>
          <el-table-column prop="case_type" label="案件種別" min-width="150" />
          <el-table-column prop="customer_name" label="顧客名" min-width="140" />
          <el-table-column prop="company_name" label="会社名" min-width="160">
            <template #default="{ row }">{{ row.company_name || '-' }}</template>
          </el-table-column>
          <el-table-column prop="status" label="ステータス" width="120" />
          <el-table-column label="更新日時" min-width="160">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-text">該当データなし</p>
      </el-card>
    </div>
  </section>
</template>
