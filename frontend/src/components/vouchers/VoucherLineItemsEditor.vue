<script setup lang="ts">
// 帳票明細の入力（見積書・契約書用）。定型項目は候補として出すだけで、自由入力できる。
// P4：見積書ではサービス項目から追加できる（選んだ後も名称・数量・単位・単価・税区分は編集できる）。
import { computed, onMounted, ref } from 'vue'
import { listVoucherItemTemplates } from '../../api/accounting'
import type { AccountingVoucherLineItem, InternalLineCost, ServiceItem, VoucherItemTemplate } from '../../types/accounting'
import ServiceItemPicker from '../services/ServiceItemPicker.vue'
import ServiceLineBadge from '../services/ServiceLineBadge.vue'
import { lineFromServiceItem, unlinkServiceItem } from '../../utils/serviceItems'
import { formatYen, lineAmounts, summarizeLines } from '../../utils/voucherCalc'

const props = defineProps<{ disabled?: boolean; allowServiceItems?: boolean; internalCosts?: InternalLineCost[] }>()
const lines = defineModel<AccountingVoucherLineItem[]>({ required: true })

const templates = ref<VoucherItemTemplate[]>([])
onMounted(async () => {
  try {
    templates.value = (await listVoucherItemTemplates({ page_size: 1000 })).results
  } catch {
    templates.value = []
  }
})

const suggest = (query: string, cb: (rows: { value: string }[]) => void) => {
  const q = (query || '').trim()
  cb(templates.value.filter((t) => !q || t.name.includes(q)).slice(0, 20).map((t) => ({ value: t.name })))
}
const applyTemplate = (item: AccountingVoucherLineItem) => {
  const found = templates.value.find((t) => t.name === item.item_name)
  if (found && found.default_unit_price != null && !Number(item.unit_price)) item.unit_price = Number(found.default_unit_price)
}

const addLine = () => {
  lines.value = [...lines.value, { item_name: '', quantity: 1, unit_price: 0, tax_category: 'tax_10', price_type: 'tax_included' }]
}
const pickService = (item: ServiceItem) => {
  const filled = lineFromServiceItem(item)
  const last = lines.value[lines.value.length - 1]
  if (last && !String(last.item_name || '').trim() && !Number(last.unit_price)) {
    lines.value = [...lines.value.slice(0, -1), filled]
  } else {
    lines.value = [...lines.value, filled]
  }
}
const unlinkService = (index: number) => {
  lines.value = lines.value.map((line, i) => (i === index ? unlinkServiceItem(line) : line))
}
const removeLine = (index: number) => {
  lines.value = lines.value.filter((_, i) => i !== index)
}
const summary = computed(() => summarizeLines(lines.value))
defineExpose({ summary })
</script>

<template>
  <div class="line-editor">
    <el-table :data="lines" size="small" border empty-text="明細がありません">
      <el-table-column label="項目" min-width="200">
        <template #default="{ row }">
          <el-autocomplete v-model="row.item_name" :fetch-suggestions="suggest" :disabled="props.disabled"
                           placeholder="項目名" style="width: 100%" @select="applyTemplate(row)" />
          <ServiceLineBadge v-if="row.service_item_id" :line="row" :costs="props.internalCosts" :disabled="props.disabled"
                            @unlink="unlinkService(lines.indexOf(row))" />
        </template>
      </el-table-column>
      <el-table-column label="数量" width="90">
        <template #default="{ row }"><el-input v-model="row.quantity" :disabled="props.disabled" inputmode="decimal" /></template>
      </el-table-column>
      <el-table-column label="単価" width="120">
        <template #default="{ row }"><el-input v-model="row.unit_price" :disabled="props.disabled" inputmode="numeric" /></template>
      </el-table-column>
      <el-table-column label="税区分" width="110">
        <template #default="{ row }">
          <el-select v-model="row.tax_category" :disabled="props.disabled">
            <el-option label="10％" value="tax_10" />
            <el-option label="8％" value="tax_8" />
            <el-option label="非課税" value="non_taxable" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="入力" width="100">
        <template #default="{ row }">
          <el-select v-model="row.price_type" :disabled="props.disabled || row.tax_category === 'non_taxable'">
            <el-option label="税込" value="tax_included" />
            <el-option label="税抜" value="tax_excluded" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="金額" width="110" align="right">
        <template #default="{ row }">{{ formatYen(lineAmounts(row).total) }}</template>
      </el-table-column>
      <el-table-column v-if="!props.disabled" width="60" align="center">
        <template #default="{ $index }"><el-button text type="danger" size="small" @click="removeLine($index)">削除</el-button></template>
      </el-table-column>
    </el-table>
    <div class="line-editor-footer">
      <div class="line-editor-add">
        <el-button v-if="!props.disabled" size="small" @click="addLine">明細を追加</el-button>
        <ServiceItemPicker v-if="!props.disabled && props.allowServiceItems" @pick="pickService" />
      </div>
      <div class="line-editor-summary">
        <span>小計（税抜） {{ formatYen(summary.subtotal) }}</span>
        <span>消費税 {{ formatYen(summary.tax_total) }}</span>
        <strong>合計 {{ formatYen(summary.total) }}</strong>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-editor-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  gap: 8px;
  flex-wrap: wrap;
}

.line-editor {
  width: 100%;
  min-width: 0;
}

.line-editor-add {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.line-editor-summary {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px 16px;
  margin-left: auto;
}
</style>
