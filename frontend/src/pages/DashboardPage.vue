<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { dismissDeadline, getDashboardSummary, listDashboardDeadlines } from '../api/dashboard'
import type { DashboardDeadline, DashboardSummary } from '../types/api'
import { formatDate, formatDateTime } from '../utils/date'

const loading = ref(false)
const errorMessage = ref('')
const summary = ref<DashboardSummary | null>(null)
const deadlineItems = ref<DashboardDeadline[]>([])

const kpiCards = ref<Array<{ key: string, label: string, value: number, tone: string, to?: string }>>([])

const buildKpis = (data: DashboardSummary) => {
  kpiCards.value = [
    { key: 'overdue', label: '期限超過', value: data.actions.overdue, tone: 'danger' },
    { key: 'today', label: '今日対応', value: data.actions.today, tone: 'warning' },
    { key: 'next_7_days', label: '7日以内', value: data.actions.next_7_days, tone: 'info' },
    { key: 'waiting', label: '待機中', value: data.cases.waiting, tone: 'info' },
    { key: 'unassigned', label: '担当未設定', value: data.cases.unassigned, tone: 'danger' },
    { key: 'without_next_action', label: '次アクション未設定', value: data.cases.without_next_action, tone: 'danger' },
  ]
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

const dismissingKey = ref('')
const deadlineKey = (item: DashboardDeadline) => `${item.target_type}-${item.target_id}-${item.type}-${item.deadline_date}`

const dismissDeadlineItem = async (item: DashboardDeadline) => {
  try {
    await ElMessageBox.confirm(
      `「${item.target_name}」の${item.deadline_label}を対象外として処理します。`
      + '対応が必要な場合はこの操作を行わないでください。よろしいですか？',
      '対象外として処理',
      { confirmButtonText: '対象外にする', cancelButtonText: 'キャンセル', type: 'warning' },
    )
  } catch {
    return
  }

  dismissingKey.value = deadlineKey(item)
  try {
    await dismissDeadline({
      source_type: item.target_type,
      source_id: item.target_id,
      deadline_type: item.type,
      deadline_date: item.deadline_date,
    })
    deadlineItems.value = deadlineItems.value.filter((d) => deadlineKey(d) !== deadlineKey(item))
    ElMessage.success('対象外として処理しました。')
  } catch {
    ElMessage.error('処理に失敗しました。')
  } finally {
    dismissingKey.value = ''
  }
}

const fetchDashboard = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [summaryData, deadlineData] = await Promise.all([
      getDashboardSummary(),
      listDashboardDeadlines(),
    ])
    summary.value = summaryData
    buildKpis(summaryData)
    deadlineItems.value = [...deadlineData].sort((a, b) => a.days_left - b.days_left)
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
      <el-card v-if="summary" shadow="never" class="kpi-card">
        <template #header>今日の作業</template>
        <div class="kpi-grid">
          <div v-for="kpi in kpiCards" :key="kpi.key" class="kpi-item" :class="`is-${kpi.tone}`">
            <span class="kpi-count">{{ kpi.value }}</span>
            <span class="kpi-label">{{ kpi.label }}</span>
          </div>
        </div>
      </el-card>

      <el-card v-if="summary" shadow="never" class="stage-summary-card">
        <template #header>案件の進捗状況（全 {{ summary.cases.total }} 件・進行中 {{ summary.cases.active }} 件）</template>
        <div class="stage-summary-grid">
          <div v-for="item in summary.stages" :key="item.key" class="stage-summary-item" :class="`is-${item.key}`">
            <span class="stage-summary-count">{{ item.count }}</span>
            <span class="stage-summary-label">{{ item.label }}</span>
          </div>
        </div>
      </el-card>

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
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button
                text
                type="primary"
                :loading="dismissingKey === deadlineKey(row)"
                @click="dismissDeadlineItem(row)"
              >対象外</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-text">該当データなし</p>
      </el-card>

      <el-card v-if="summary" shadow="never">
        <template #header>最近更新された案件</template>
        <el-table v-if="summary.recent_cases.length" :data="summary.recent_cases" stripe>
          <el-table-column label="案件番号" min-width="150">
            <template #default="{ row }">
              <router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link>
            </template>
          </el-table-column>
          <el-table-column prop="customer_name" label="顧客名" min-width="130" />
          <el-table-column prop="company_name" label="会社名" min-width="150">
            <template #default="{ row }">{{ row.company_name || '-' }}</template>
          </el-table-column>
          <el-table-column label="進捗" width="130">
            <template #default="{ row }">{{ row.status_display }}</template>
          </el-table-column>
          <el-table-column label="担当" width="110">
            <template #default="{ row }">{{ row.responsible_employee_name || '未設定' }}</template>
          </el-table-column>
          <el-table-column label="次の対応" min-width="160">
            <template #default="{ row }">
              <span v-if="row.next_action">{{ row.next_action }}<span v-if="row.next_action_due_at"> ({{ formatDate(row.next_action_due_at) }})</span></span>
              <span v-else class="empty-text">未設定</span>
            </template>
          </el-table-column>
          <el-table-column label="更新日時" min-width="150">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
        </el-table>
        <p v-else class="empty-text">該当データなし</p>
      </el-card>
    </div>
  </section>
</template>

<style scoped>
.stage-summary-grid,
.kpi-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.stage-summary-item,
.kpi-item {
  flex: 1;
  min-width: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 8px;
  border-radius: var(--el-border-radius-base);
  background: var(--el-fill-color-light);
}

.stage-summary-count,
.kpi-count {
  font-size: 24px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.3;
}

.kpi-item.is-danger .kpi-count {
  color: var(--el-color-danger);
}

.kpi-item.is-warning .kpi-count {
  color: var(--el-color-warning);
}

.stage-summary-label,
.kpi-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  text-align: center;
}
</style>
