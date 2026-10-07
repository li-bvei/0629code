<script setup lang="ts">
// 請求書・領収書の状態履歴：変更前後・操作者・時刻・理由と、その時点の帳票内容（発行の版）。
import { ref, watch } from 'vue'
import { listVoucherStatusHistory } from '../../api/accounting'
import type { VoucherStatusHistoryRow } from '../../types/accounting'
import { formatDateTime } from '../../utils/date'
import { formatYen } from '../../utils/voucherCalc'
import { apiErrorText } from './voucherErrors'

const props = defineProps<{ voucherId: number | null; number?: string }>()
const visible = defineModel<boolean>('visible', { required: true })
const rows = ref<VoucherStatusHistoryRow[]>([])
const loading = ref(false)
const error = ref('')

const load = async () => {
  if (!props.voucherId) return
  loading.value = true
  error.value = ''
  try {
    rows.value = await listVoucherStatusHistory(props.voucherId)
  } catch (e) {
    error.value = apiErrorText(e, '状態履歴を取得できませんでした。')
  } finally {
    loading.value = false
  }
}
watch(() => [visible.value, props.voucherId], () => { if (visible.value) load() })
</script>

<template>
  <el-dialog v-model="visible" :title="`状態履歴${number ? `（${number}）` : ''}`" width="min(860px, 96vw)">
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false">
      <el-button link type="primary" @click="load">再読み込み</el-button>
    </el-alert>
    <el-table v-loading="loading" :data="rows" size="small" empty-text="状態の変更はまだありません" row-key="id">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="history-snapshot">
            <div>番号：{{ row.snapshot.number || row.voucher_number }} ／ 発行日：{{ row.snapshot.issue_date || '-' }} ／ 宛先：{{ row.snapshot.recipient_name || '-' }}</div>
            <div>件名：{{ row.snapshot.title || '-' }}</div>
            <ul>
              <li v-for="(item, i) in row.snapshot.line_items || []" :key="i">
                {{ item.item_name }}　{{ item.quantity }}{{ item.unit || '' }} × {{ formatYen(item.unit_price) }} ＝ {{ formatYen(item.line_total) }}<span v-if="item.note">（{{ item.note }}）</span>
              </li>
            </ul>
            <div>合計 {{ formatYen(row.snapshot.total_amount) }}（税 {{ formatYen(row.snapshot.tax_amount as number) }}）</div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="日時" width="150"><template #default="{ row }">{{ formatDateTime(row.changed_at) }}</template></el-table-column>
      <el-table-column label="変更" min-width="190">
        <template #default="{ row }">{{ row.from_status_display }} → <strong>{{ row.to_status_display }}</strong></template>
      </el-table-column>
      <el-table-column label="版" width="70"><template #default="{ row }">{{ row.version ? `第${row.version}版` : '-' }}</template></el-table-column>
      <el-table-column label="操作者" width="110" prop="changed_by_name" />
      <el-table-column label="理由・メモ" min-width="150"><template #default="{ row }">{{ row.reason || '-' }}</template></el-table-column>
      <el-table-column label="合計" width="110" align="right"><template #default="{ row }">{{ formatYen(row.snapshot.total_amount) }}</template></el-table-column>
    </el-table>
    <template #footer><el-button @click="visible = false">閉じる</el-button></template>
  </el-dialog>
</template>

<style scoped>
.history-snapshot {
  padding: 4px 16px;
  font-size: 13px;
  line-height: 1.7;
}

.history-snapshot ul {
  margin: 4px 0;
  padding-left: 18px;
}
</style>
