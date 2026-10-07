<script setup lang="ts">
// 明細行がサービス項目から作られた場合の表示（P4）：選んだ時点の項目・標準価格（参考）・変えた項目。
// 委託底価は底価権限者の応答にだけ含まれる internal_line_costs から表示する（社内用・PDF には出ない）。
import { computed } from 'vue'
import type { AccountingVoucherLineItem, InternalLineCost } from '../../types/accounting'
import { changedServiceFieldLabels, floorForLine, isProvisionalService, serviceSummary } from '../../utils/serviceItems'

const props = defineProps<{ line: AccountingVoucherLineItem; costs?: InternalLineCost[]; disabled?: boolean }>()
const emit = defineEmits<{ (e: 'unlink'): void }>()

const changed = computed(() => changedServiceFieldLabels(props.line))
const floor = computed(() => floorForLine(props.line, props.costs))
const saved = computed(() => Boolean(props.line.line_key))
</script>

<template>
  <div v-if="line.service_item_id && line.service" class="service-line-badge">
    <el-tag size="small" type="info" effect="plain">サービス項目</el-tag>
    <span class="name">{{ line.service.name }}</span>
    <span class="sub">{{ serviceSummary(line.service) }}</span>
    <el-tag v-if="isProvisionalService(line.service)" size="small" type="warning" effect="plain"
            title="選んだ時点で価格が未確定のサービス項目です。発行の前に確認が必要です">暫定価格から作成</el-tag>
    <span v-if="line.service.professional_type_display" class="sub">委託：{{ line.service.professional_type_display }}</span>
    <el-tag v-if="changed.length" size="small" type="warning">変更：{{ changed.join('・') }}</el-tag>
    <span v-if="floor !== null" class="floor" title="社内用。顧客の PDF には表示されません">底価 ¥{{ Number(floor).toLocaleString('ja-JP') }}（社内）</span>
    <span v-if="!saved" class="sub">保存すると選んだ時点の内容を記録します</span>
    <el-button v-if="!disabled" link size="small" @click="emit('unlink')">項目から外す</el-button>
  </div>
</template>

<style scoped>
.service-line-badge {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
  font-size: 12px;
  padding: 2px 0 4px;
}

.name {
  font-weight: 600;
}

.sub {
  color: var(--el-text-color-secondary);
}

.floor {
  color: var(--el-color-warning-dark-2);
}
</style>
