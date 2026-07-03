<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAccountingDashboard } from '../../api/accounting'
import type { AccountingDashboard, ExpenseTargetChartItem } from '../../types/accounting'
import { formatDate } from '../../utils/date'
import './accounting.css'

interface SummaryCard {
  label: string
  value: string
  accent?: boolean
  danger?: boolean
}

const chartColors = ['#aad4f4', '#e2c5dd', '#9ed9cc', '#f5d48b', '#c8d4f7', '#f3b6b6', '#b9e2f7', '#d8c7f2']

const loading = ref(false)
const errorMessage = ref('')
const dashboard = ref<AccountingDashboard>({
  monthly_expense_total: 0,
  monthly_income_source_total: 0,
  monthly_vehicle_km_total: 0,
  monthly_unreimbursed_total: 0,
  total_expense_amount: 0,
  total_income_source_amount: 0,
  current_balance: 0,
  expense_target_chart: [],
  expense_category_chart: [],
  recent_expenses: [],
  recent_income_sources: [],
  recent_vehicle_usages: [],
})

const formatCurrency = (value: number | string) => `¥ ${Number(value || 0).toLocaleString()}`
const formatDistance = (value: number | string) => `${Number(value || 0).toLocaleString()} km`
const formatBoolean = (value: boolean) => (value ? 'はい' : 'いいえ')

const balanceValue = computed(() => Number(dashboard.value.current_balance || 0))
const getChartTotal = (items: ExpenseTargetChartItem[]) =>
  items.reduce((total, item) => total + Number(item.amount || 0), 0)
const getChartBackground = (items: ExpenseTargetChartItem[]) => {
  const total = getChartTotal(items)
  if (!items.length || total <= 0) {
    return '#eef3f7'
  }

  let current = 0
  const segments = items.map((item, index) => {
    const start = current
    current += (Number(item.amount || 0) / total) * 100
    return `${chartColors[index % chartColors.length]} ${start}% ${current}%`
  })
  return `conic-gradient(${segments.join(', ')})`
}

const summaryCards = computed<SummaryCard[]>(() => [
  { label: '本月支出合計', value: formatCurrency(dashboard.value.monthly_expense_total) },
  { label: '本月収入来源合計', value: formatCurrency(dashboard.value.monthly_income_source_total) },
  { label: '本月用車公里数', value: formatDistance(dashboard.value.monthly_vehicle_km_total) },
  { label: '本月未精算金額', value: formatCurrency(dashboard.value.monthly_unreimbursed_total) },
  {
    label: '账面剩余金额',
    value: formatCurrency(dashboard.value.current_balance),
    accent: true,
    danger: balanceValue.value < 0,
  },
  { label: '全部支出合計', value: formatCurrency(dashboard.value.total_expense_amount) },
  { label: '全部収入来源合計', value: formatCurrency(dashboard.value.total_income_source_amount) },
])

const chartPercent = (item: ExpenseTargetChartItem, items: ExpenseTargetChartItem[]) => {
  const total = getChartTotal(items)
  if (total <= 0) return '0%'
  return `${Math.round((Number(item.amount || 0) / total) * 100)}%`
}

const fetchDashboard = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    dashboard.value = await getAccountingDashboard()
  } catch {
    errorMessage.value = '会計データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboard()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <h1>会計ダッシュボード</h1>
      <p>支出・収入来源・用車記録をまとめて確認できます</p>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <div v-loading="loading" class="accounting-page">
      <div class="accounting-summary-grid">
        <div
          v-for="card in summaryCards"
          :key="card.label"
          class="accounting-summary-card"
          :class="{ 'is-accent': card.accent, 'is-danger': card.danger }"
        >
          <div class="accounting-summary-label">{{ card.label }}</div>
          <div class="accounting-summary-value" :class="{ 'is-negative': card.danger }">{{ card.value }}</div>
        </div>
      </div>

      <div class="accounting-chart-grid">
        <el-card shadow="never" class="accounting-card">
          <template #header>支出对象占比</template>
          <p class="accounting-chart-description">按费用对象统计支出金额</p>
          <div v-if="dashboard.expense_target_chart.length" class="accounting-chart-layout">
            <div class="accounting-donut" :style="{ background: getChartBackground(dashboard.expense_target_chart) }" />
            <div class="accounting-chart-list">
              <div v-for="(item, index) in dashboard.expense_target_chart" :key="item.name" class="accounting-chart-row">
                <span class="accounting-chart-dot" :style="{ backgroundColor: chartColors[index % chartColors.length] }" />
                <span class="accounting-chart-name">{{ item.name }}（{{ chartPercent(item, dashboard.expense_target_chart) }}）</span>
                <span class="accounting-chart-amount">{{ formatCurrency(item.amount) }}</span>
              </div>
            </div>
          </div>
          <p v-else class="empty-text">データがありません</p>
        </el-card>

        <el-card shadow="never" class="accounting-card">
          <template #header>支出类型占比</template>
          <p class="accounting-chart-description">按支出カテゴリ统计支出金额</p>
          <div v-if="dashboard.expense_category_chart.length" class="accounting-chart-layout">
            <div class="accounting-donut" :style="{ background: getChartBackground(dashboard.expense_category_chart) }" />
            <div class="accounting-chart-list">
              <div v-for="(item, index) in dashboard.expense_category_chart" :key="item.name" class="accounting-chart-row">
                <span class="accounting-chart-dot" :style="{ backgroundColor: chartColors[index % chartColors.length] }" />
                <span class="accounting-chart-name">{{ item.name }}（{{ chartPercent(item, dashboard.expense_category_chart) }}）</span>
                <span class="accounting-chart-amount">{{ formatCurrency(item.amount) }}</span>
              </div>
            </div>
          </div>
          <p v-else class="empty-text">データがありません</p>
        </el-card>
      </div>

      <div class="accounting-record-grid">
        <el-card shadow="never" class="accounting-card">
          <template #header>最近支出記録</template>
          <el-table v-if="dashboard.recent_expenses.length" :data="dashboard.recent_expenses" stripe>
            <el-table-column label="日付" width="110">
              <template #default="{ row }">{{ formatDate(row.expense_date) }}</template>
            </el-table-column>
            <el-table-column prop="category" label="カテゴリ" min-width="120" />
            <el-table-column label="金額" min-width="110" align="right" header-align="right">
              <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
            </el-table-column>
            <el-table-column prop="expense_target" label="費用対象" min-width="130" />
            <el-table-column label="精算" width="80">
              <template #default="{ row }">{{ formatBoolean(row.is_reimbursed) }}</template>
            </el-table-column>
          </el-table>
          <p v-else class="empty-text">データがありません</p>
        </el-card>

        <el-card shadow="never" class="accounting-card">
          <template #header>最近収入来源</template>
          <el-table v-if="dashboard.recent_income_sources.length" :data="dashboard.recent_income_sources" stripe>
            <el-table-column label="日付" width="110">
              <template #default="{ row }">{{ formatDate(row.source_date) }}</template>
            </el-table-column>
            <el-table-column prop="source_target" label="対象" min-width="150" />
            <el-table-column label="金額" min-width="110" align="right" header-align="right">
              <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
            </el-table-column>
          </el-table>
          <p v-else class="empty-text">データがありません</p>
        </el-card>

        <el-card shadow="never" class="accounting-card">
          <template #header>最近用車記録</template>
          <el-table v-if="dashboard.recent_vehicle_usages.length" :data="dashboard.recent_vehicle_usages" stripe>
            <el-table-column label="日付" width="110">
              <template #default="{ row }">{{ formatDate(row.usage_date) }}</template>
            </el-table-column>
            <el-table-column prop="usage_target" label="利用対象" min-width="130" />
            <el-table-column label="走行距離" width="110" align="right" header-align="right">
              <template #default="{ row }">{{ formatDistance(row.distance_km) }}</template>
            </el-table-column>
            <el-table-column prop="purpose" label="用途" min-width="120" />
          </el-table>
          <p v-else class="empty-text">データがありません</p>
        </el-card>
      </div>
    </div>
  </section>
</template>
