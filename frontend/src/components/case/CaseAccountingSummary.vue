<script setup lang="ts">
// 案件に関連付いた会計記録の要約（会計データ自体は会計モジュールにあり、ここは参照と導線のみ）。
// 表示範囲は後端が利用者の会計権限で決める（支出は本人分／全件閲覧権限、収入・税務証明は各モジュール権限）。
import { onMounted, ref, watch } from 'vue'
import { getCaseAccountingSummary } from '../../api/accounting'
import { formatAccountingNumber } from '../../utils/accountingFormat'
import { formatDate } from '../../utils/date'
import type { CaseAccountingSummary } from '../../types/accounting'

const props = defineProps<{ caseId: number }>()
const summary = ref<CaseAccountingSummary | null>(null)
const errorMessage = ref('')
const loading = ref(false)

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    summary.value = await getCaseAccountingSummary(props.caseId)
  } catch {
    errorMessage.value = '会計の関連情報を取得できませんでした。'
  } finally {
    loading.value = false
  }
}

defineExpose({ load })
watch(() => props.caseId, load)
onMounted(load)
</script>

<template>
  <section v-loading="loading" class="case-accounting-summary" aria-label="会計の関連情報">
    <h3>会計（関連）</h3>
    <p v-if="errorMessage" class="muted">{{ errorMessage }}</p>
    <template v-else-if="summary">
      <div v-if="summary.expense.visible" class="block">
        <div class="row">
          <span>{{ summary.expense.scope === 'all' ? '支出（全員分）' : '私の支出' }}</span>
          <strong>{{ summary.expense.count }}件 / {{ formatAccountingNumber(summary.expense.total ?? 0) }}</strong>
        </div>
        <ul v-if="summary.expense.recent?.length">
          <li v-for="row in summary.expense.recent" :key="row.id">
            <router-link v-if="row.is_own" class="text-link" :to="`/accounting/expenses/${row.id}/edit`">{{ formatDate(row.expense_date) }} {{ row.category }}</router-link>
            <span v-else>{{ formatDate(row.expense_date) }} {{ row.category }}</span>
            <span class="amount">{{ formatAccountingNumber(row.amount) }}</span>
          </li>
        </ul>
        <router-link class="text-link" :to="{ path: '/accounting/expenses', query: { case: String(caseId) } }">支出記録で見る</router-link>
      </div>
      <div v-if="summary.income.visible" class="block">
        <div class="row">
          <span>収入</span>
          <strong>{{ summary.income.count }}件 / {{ formatAccountingNumber(summary.income.total ?? 0) }}</strong>
        </div>
      </div>
      <div v-if="summary.tax_renewal.visible && summary.tax_renewal.count" class="block">
        <div class="row"><span>税務証明記録</span><strong>{{ summary.tax_renewal.count }}件</strong></div>
      </div>
      <p v-if="!summary.expense.visible && !summary.income.visible" class="muted">会計の閲覧権限がありません。</p>
    </template>
  </section>
</template>

<style scoped>
.case-accounting-summary h3 {
  margin: 0 0 8px;
  font-size: 14px;
}

.block + .block {
  margin-top: 10px;
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

ul {
  margin: 6px 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
}

li {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 0;
}

.amount {
  font-variant-numeric: tabular-nums;
}

.muted {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
