<script setup lang="ts">
// 案件・顧客・会社から見る帳票の要約。各帳票の権限がある部分だけ表示し、全く権限がなければ何も出さない。
import { computed, onMounted, ref, watch } from 'vue'
import { getVoucherLinks } from '../../api/accounting'
import type { VoucherLinkBlock, VoucherLinks } from '../../types/accounting'
import { formatYen } from '../../utils/voucherCalc'

const props = defineProps<{ caseId?: number; customerId?: number; companyId?: number }>()
const data = ref<VoucherLinks | null>(null)

const load = async () => {
  const params = props.caseId ? { case: props.caseId } : props.customerId ? { customer: props.customerId } : props.companyId ? { company: props.companyId } : null
  if (!params) return
  try {
    data.value = await getVoucherLinks(params)
  } catch {
    data.value = null // 権限なし・対象外は非表示
  }
}
onMounted(load)
watch(() => [props.caseId, props.customerId, props.companyId], load)

const blocks = computed(() => {
  if (!data.value) return []
  const defs: [keyof VoucherLinks, string, string][] = [
    ['estimates', '見積書', '/vouchers/estimates'],
    ['contracts', '契約書', '/vouchers/contracts'],
    ['invoices', '請求書', '/vouchers/invoices'],
    ['receipts', '領収書', '/vouchers/invoices'],
  ]
  return defs
    .map(([key, label, path]) => ({ key, label, path, block: data.value![key] as VoucherLinkBlock }))
    .filter((row) => row.block.visible)
})
</script>

<template>
  <el-card v-if="blocks.length" shadow="never" class="voucher-links">
    <template #header><span>帳票</span></template>
    <div v-for="row in blocks" :key="row.key" class="voucher-links-block">
      <div class="voucher-links-title">{{ row.label }}<span v-if="row.block.visible">（{{ row.block.count }}）</span></div>
      <template v-if="row.block.visible">
        <div v-if="!row.block.items.length" class="voucher-links-empty">なし</div>
        <router-link v-for="item in row.block.items.slice(0, 5)" :key="item.id" class="voucher-links-row"
                     :to="{ path: row.path, query: { keyword: item.number } }">
          <span>{{ item.number }}</span>
          <el-tag size="small" type="info">{{ item.status_display }}</el-tag>
          <span class="amount">{{ formatYen(item.total_amount) }}</span>
        </router-link>
      </template>
    </div>
  </el-card>
</template>

<style scoped>
.voucher-links-block + .voucher-links-block {
  margin-top: 10px;
}

.voucher-links-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}

.voucher-links-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 2px 0;
  color: inherit;
  text-decoration: none;
}

.voucher-links-row .amount {
  margin-left: auto;
}

.voucher-links-empty {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
