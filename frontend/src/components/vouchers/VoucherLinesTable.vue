<script setup lang="ts">
// 請求書・領収書の明細の連続入力（2026-10 P1）。
// 列の順序：項目／説明・数量・単位・単価・税区分・金額・備考・操作（狭い画面の行カードも同じ順序）。
// Enter で次の欄へ、最後の欄（備考）で次の行へ（最終行なら行を追加）。Shift+Enter は項目内の改行。
// 誤りは該当の行にだけ表示し、他の行の入力は消さない。金額・税額は入力のたびに計算する（保存値は後端が再計算）。
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { ArrowDown, ArrowUp, CopyDocument, Delete } from '@element-plus/icons-vue'
import type { InternalLineCost, ServiceItem, VoucherItemTemplate } from '../../types/accounting'
import ServiceItemPicker from '../services/ServiceItemPicker.vue'
import ServiceLineBadge from '../services/ServiceLineBadge.vue'
import { lineFromServiceItem, unlinkServiceItem } from '../../utils/serviceItems'
import { formatYen, lineAmounts, summarizeLines } from '../../utils/voucherCalc'
import {
  createLine, duplicateLine, isBlankLine, moveLine, nextFocus, removeLine, type LineField, type VoucherLine,
} from '../../utils/voucherLines'

const props = defineProps<{
  disabled?: boolean
  templates?: VoucherItemTemplate[]
  errors?: Record<number, string>
  /** P4：サービス項目から追加できる帳票（請求書）。領収書では使わない */
  allowServiceItems?: boolean
  /** P4：底価権限者への応答にだけある委託底価（社内表示用） */
  internalCosts?: InternalLineCost[]
}>()
const emit = defineEmits<{ (e: 'save-template', line: VoucherLine): void }>()
const lines = defineModel<VoucherLine[]>({ required: true })

const root = ref<HTMLElement>()
const narrow = ref(false)
let media: MediaQueryList | null = null
const syncMedia = () => { narrow.value = Boolean(media?.matches) }
onMounted(() => {
  media = window.matchMedia('(max-width: 767px)')
  syncMedia()
  media.addEventListener('change', syncMedia)
})
onBeforeUnmount(() => media?.removeEventListener('change', syncMedia))

const summary = computed(() => summarizeLines(lines.value))
const amountsOf = (line: VoucherLine) => lineAmounts(line)
const templateNames = computed(() => (props.templates ?? []).filter((t) => t.is_active !== false))
const isNewTemplateName = (line: VoucherLine) => {
  const name = String(line.item_name ?? '').trim()
  return Boolean(name) && !(props.templates ?? []).some((t) => t.name === name)
}

const focusCell = async (rowIndex: number, field: LineField) => {
  await nextTick()
  const cell = root.value?.querySelector<HTMLElement>(`[data-cell="${rowIndex}-${field}"]`)
  const target = cell?.querySelector<HTMLInputElement | HTMLTextAreaElement>('textarea, input')
  target?.focus()
  // 既定値（数量 1 など）を上書き入力できるよう、移動先の文字を選択しておく
  if (target && target.tagName === 'INPUT' && !target.readOnly) target.select()
}

const addLine = async (focus = true) => {
  lines.value = [...lines.value, createLine()]
  if (focus) await focusCell(lines.value.length - 1, 'item_name')
}

const onEnter = async (event: KeyboardEvent, rowIndex: number, field: LineField) => {
  if (event.isComposing || (field === 'item_name' && event.shiftKey)) return // 変換確定・項目内の改行
  event.preventDefault()
  const next = nextFocus(field, rowIndex, lines.value.length)
  if (next.append) {
    await addLine(false)
  }
  await focusCell(next.rowIndex, next.field)
}

// 税区分（選択欄）：一覧が閉じていれば Enter で次の欄へ。↓ で一覧を開き Enter で選ぶと、選択後に次の欄へ進む
const onSelectEnter = async (event: KeyboardEvent, rowIndex: number) => {
  if (event.isComposing) return
  const input = event.target as HTMLElement | null
  if (input?.getAttribute('aria-expanded') === 'true') {
    // 選択の確定は el-select 側が行う。確定より先にフォーカスを外すと選択が捨てられるため、次のタスクで移動する
    window.setTimeout(() => { void focusCell(...nextCell(rowIndex)) }, 0)
    return
  }
  event.preventDefault()
  event.stopPropagation()
  await focusCell(...nextCell(rowIndex))
}
const nextCell = (rowIndex: number): [number, LineField] => {
  const next = nextFocus('tax_category', rowIndex, lines.value.length)
  return [next.rowIndex, next.field]
}

const copyLine = async (index: number) => {
  lines.value = duplicateLine(lines.value, index)
  await focusCell(index + 1, 'item_name')
}

const move = (index: number, delta: -1 | 1) => {
  lines.value = moveLine(lines.value, index, delta)
}

const deleteLine = async (index: number) => {
  const line = lines.value[index]
  if (line && !isBlankLine(line)) {
    try {
      await ElMessageBox.confirm(`${index + 1} 行目「${line.item_name || '（項目なし）'}」を削除しますか？`, '明細の削除', {
        confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning',
      })
    } catch {
      return
    }
  }
  lines.value = removeLine(lines.value, index)
}

// よく使う項目を選ぶと、空の最終行に入れる（無ければ行を追加する）
const pickTemplate = async (name: string) => {
  const template = (props.templates ?? []).find((t) => t.name === name)
  if (!template) return
  const last = lines.value[lines.value.length - 1]
  const target = last && isBlankLine(last) ? last : null
  const filled = {
    item_name: template.name,
    unit_price: template.default_unit_price != null ? Number(template.default_unit_price) : '',
  }
  if (target) Object.assign(target, filled)
  else lines.value = [...lines.value, { ...createLine(), ...filled }]
  await focusCell(lines.value.length - 1, 'quantity')
}
// サービス項目を選ぶと、空の最終行に入れる（無ければ行を追加する）。値は選んだ後も編集できる
const pickService = async (item: ServiceItem) => {
  const filled = lineFromServiceItem(item)
  const last = lines.value[lines.value.length - 1]
  if (last && isBlankLine(last)) Object.assign(last, filled)
  else lines.value = [...lines.value, { ...createLine(), ...filled }]
  await focusCell(lines.value.length - 1, 'quantity')
}
const unlinkService = (index: number) => {
  const line = lines.value[index]
  if (!line) return
  const next = [...lines.value]
  next[index] = { ...unlinkServiceItem(line), key: line.key }
  lines.value = next
}
const pickedTemplate = ref<string | null>(null)
const onPickTemplate = async (name: string) => {
  await pickTemplate(name)
  pickedTemplate.value = null
}

defineExpose({ summary, focusCell, addLine })
</script>

<template>
  <div ref="root" class="voucher-lines">
    <div class="voucher-lines-toolbar">
      <el-button v-if="!disabled" type="primary" plain size="small" @click="addLine()">行を追加</el-button>
      <ServiceItemPicker v-if="!disabled && allowServiceItems" @pick="pickService" />
      <el-select v-if="!disabled && templateNames.length" v-model="pickedTemplate" filterable size="small" clearable
                 placeholder="よく使う項目から追加" class="voucher-lines-template" @change="onPickTemplate">
        <el-option v-for="t in templateNames" :key="t.id" :label="t.name" :value="t.name" />
      </el-select>
      <span class="voucher-lines-hint">Enter で次の欄・次の行へ（最後の行では行を追加）。項目内の改行は Shift+Enter。税区分は ↓ で一覧を開いて選択。</span>
    </div>

    <!-- 広い画面：全幅の表 -->
    <div v-if="!narrow" class="voucher-lines-table" role="table" aria-label="明細">
      <div class="vl-row vl-head" role="row">
        <span class="vl-no">#</span>
        <span>項目／説明</span><span>数量</span><span>単位</span><span>単価</span><span>税区分</span>
        <span class="vl-amount">金額</span><span title="入力した備考は顧客向けの PDF に印字されます">備考（PDF に表示）</span><span>操作</span>
      </div>
      <template v-for="(line, index) in lines" :key="line.key">
        <div class="vl-row" role="row" :class="{ 'has-error': errors?.[line.key] }">
          <span class="vl-no">{{ index + 1 }}</span>
          <div :data-cell="`${index}-item_name`">
            <el-input v-model="line.item_name" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" :disabled="disabled"
                      placeholder="項目・説明" @keydown.enter="onEnter($event, index, 'item_name')" />
          </div>
          <div :data-cell="`${index}-quantity`">
            <el-input v-model="line.quantity" inputmode="decimal" :disabled="disabled"
                      @keydown.enter="onEnter($event, index, 'quantity')" />
          </div>
          <div :data-cell="`${index}-unit`">
            <el-input v-model="line.unit" placeholder="件" :disabled="disabled"
                      @keydown.enter="onEnter($event, index, 'unit')" />
          </div>
          <div :data-cell="`${index}-unit_price`">
            <el-input v-model="line.unit_price" inputmode="numeric" placeholder="0" :disabled="disabled"
                      @keydown.enter="onEnter($event, index, 'unit_price')" />
          </div>
          <div :data-cell="`${index}-tax_category`" class="vl-tax">
            <el-select v-model="line.tax_category" :disabled="disabled" @keydown.enter.capture="onSelectEnter($event, index)">
              <el-option label="10％" value="tax_10" /><el-option label="8％" value="tax_8" /><el-option label="非課税" value="non_taxable" />
            </el-select>
            <el-select v-model="line.price_type" :disabled="disabled || line.tax_category === 'non_taxable'" size="small">
              <el-option label="税込" value="tax_included" /><el-option label="税抜" value="tax_excluded" />
            </el-select>
          </div>
          <div class="vl-amount">
            <strong>{{ formatYen(amountsOf(line).total) }}</strong>
            <small>税 {{ formatYen(amountsOf(line).tax) }}</small>
          </div>
          <div :data-cell="`${index}-note`">
            <el-input v-model="line.note" placeholder="顧客の PDF に表示" :disabled="disabled"
                      @keydown.enter="onEnter($event, index, 'note')" />
          </div>
          <div class="vl-actions">
            <template v-if="!disabled">
              <el-button text size="small" :icon="ArrowUp" :disabled="index === 0" title="上へ" aria-label="上へ" @click="move(index, -1)" />
              <el-button text size="small" :icon="ArrowDown" :disabled="index === lines.length - 1" title="下へ" aria-label="下へ" @click="move(index, 1)" />
              <el-button text size="small" :icon="CopyDocument" title="この行を複製" aria-label="この行を複製" @click="copyLine(index)" />
              <el-button text size="small" type="danger" :icon="Delete" title="削除" aria-label="削除" @click="deleteLine(index)" />
            </template>
          </div>
        </div>
        <div v-if="line.service_item_id" class="vl-service">
          <ServiceLineBadge :line="line" :costs="internalCosts" :disabled="disabled" @unlink="unlinkService(index)" />
        </div>
        <div v-if="errors?.[line.key]" class="vl-error" role="alert">{{ index + 1 }} 行目：{{ errors[line.key] }}</div>
        <div v-else-if="!disabled && !line.service_item_id && isNewTemplateName(line)" class="vl-save-template">
          <el-button link size="small" @click="emit('save-template', line)">「{{ line.item_name }}」をよく使う項目に保存</el-button>
        </div>
      </template>
    </div>

    <!-- 狭い画面：行ごとのカード（欄の順序と計算規則は表と同じ） -->
    <div v-else class="voucher-lines-cards">
      <div v-for="(line, index) in lines" :key="line.key" class="vl-card" :class="{ 'has-error': errors?.[line.key] }">
        <div class="vl-card-head">
          <strong>{{ index + 1 }} 行目</strong>
          <span>{{ formatYen(amountsOf(line).total) }}（税 {{ formatYen(amountsOf(line).tax) }}）</span>
        </div>
        <label :data-cell="`${index}-item_name`">項目／説明
          <el-input v-model="line.item_name" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" :disabled="disabled"
                    @keydown.enter="onEnter($event, index, 'item_name')" />
        </label>
        <ServiceLineBadge v-if="line.service_item_id" :line="line" :costs="internalCosts" :disabled="disabled" @unlink="unlinkService(index)" />
        <div class="vl-card-grid">
          <label :data-cell="`${index}-quantity`">数量<el-input v-model="line.quantity" inputmode="decimal" :disabled="disabled" @keydown.enter="onEnter($event, index, 'quantity')" /></label>
          <label :data-cell="`${index}-unit`">単位<el-input v-model="line.unit" :disabled="disabled" @keydown.enter="onEnter($event, index, 'unit')" /></label>
          <label :data-cell="`${index}-unit_price`">単価<el-input v-model="line.unit_price" inputmode="numeric" :disabled="disabled" @keydown.enter="onEnter($event, index, 'unit_price')" /></label>
          <label :data-cell="`${index}-tax_category`">税区分
            <el-select v-model="line.tax_category" :disabled="disabled" @keydown.enter.capture="onSelectEnter($event, index)">
              <el-option label="10％" value="tax_10" /><el-option label="8％" value="tax_8" /><el-option label="非課税" value="non_taxable" />
            </el-select>
            <el-select v-model="line.price_type" :disabled="disabled || line.tax_category === 'non_taxable'" size="small">
              <el-option label="税込" value="tax_included" /><el-option label="税抜" value="tax_excluded" />
            </el-select>
          </label>
        </div>
        <label :data-cell="`${index}-note`">備考（顧客の PDF に表示）<el-input v-model="line.note" :disabled="disabled" @keydown.enter="onEnter($event, index, 'note')" /></label>
        <div v-if="errors?.[line.key]" class="vl-error" role="alert">{{ errors[line.key] }}</div>
        <div v-if="!disabled" class="vl-card-actions">
          <el-button size="small" :disabled="index === 0" @click="move(index, -1)">上へ</el-button>
          <el-button size="small" :disabled="index === lines.length - 1" @click="move(index, 1)">下へ</el-button>
          <el-button size="small" @click="copyLine(index)">複製</el-button>
          <el-button size="small" type="danger" plain @click="deleteLine(index)">削除</el-button>
        </div>
      </div>
      <el-button v-if="!disabled" type="primary" plain class="vl-card-add" @click="addLine()">行を追加</el-button>
    </div>

    <div class="voucher-lines-summary">
      <span>小計（税抜） <strong>{{ formatYen(summary.subtotal) }}</strong></span>
      <span>消費税 <strong>{{ formatYen(summary.tax_total) }}</strong></span>
      <span class="is-total">合計 <strong>{{ formatYen(summary.total) }}</strong></span>
    </div>
  </div>
</template>

<style scoped>
.voucher-lines {
  width: 100%;
  min-width: 0;
}

.voucher-lines-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 8px;
}

.voucher-lines-template {
  width: 220px;
}

.voucher-lines-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.voucher-lines-table {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow-x: auto;
}

.vl-row {
  display: grid;
  grid-template-columns: 32px minmax(200px, 3fr) 72px 64px 110px 150px 120px minmax(120px, 1.5fr) 128px;
  gap: 6px;
  align-items: start;
  padding: 6px 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  min-width: 1000px;
}

.vl-head {
  border-top: none;
  background: var(--el-fill-color-light);
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-regular);
}

.vl-row.has-error {
  background: var(--el-color-danger-light-9);
}

.vl-no {
  padding-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  text-align: right;
}

.vl-tax {
  display: grid;
  gap: 4px;
}

.vl-amount {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  padding-top: 6px;
}

.vl-amount small {
  color: var(--el-text-color-secondary);
}

.vl-actions {
  display: flex;
  flex-wrap: nowrap;
}

.vl-actions .el-button + .el-button {
  margin-left: 0;
}

.vl-service {
  padding: 0 8px 4px 46px;
  min-width: 1000px;
}

.vl-error {
  padding: 2px 8px 6px 46px;
  font-size: 12px;
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}

.vl-save-template {
  padding: 0 8px 4px 46px;
}

.voucher-lines-cards {
  display: grid;
  gap: 10px;
}

.vl-card {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}

.vl-card.has-error {
  border-color: var(--el-color-danger-light-5);
}

.vl-card label {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.vl-card-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.vl-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.vl-card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.vl-card-actions .el-button + .el-button {
  margin-left: 0;
}

.voucher-lines-summary {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 4px 20px;
  margin-top: 10px;
}

.voucher-lines-summary .is-total strong {
  font-size: 16px;
}
</style>
