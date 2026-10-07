<script setup lang="ts">
import RemoteSelect from './RemoteSelect.vue'
import { getCustomer, listCustomers } from '../api/customers'
import type { Customer } from '../types/api'

const props = defineProps<{
  modelValue: number | null | undefined
  /** 関連付けできる顧客だけを候補にする（会社の従業員・代表者など。判定は後端の check_link と同じ） */
  linkableOnly?: boolean
  placeholder?: string
  clearable?: boolean
  disabled?: boolean
  initialOption?: { value: number, label: string, sublabel?: string } | null
}>()

defineEmits<{
  (e: 'update:modelValue', value: number | null): void
  (e: 'change', row: Customer | null): void
}>()

// 一覧 API の件数（count）も返し、候補に出ていない分があれば「絞り込んでください」と案内する
const fetcher = async (search: string) => {
  const data = await listCustomers({ search: search || undefined, page_size: 20, linkable: props.linkableOnly || undefined })
  return { results: data.results, count: data.count }
}

const fetchOne = async (id: number) => {
  try {
    return await getCustomer(id) as unknown as Customer
  } catch {
    return null
  }
}

const toOption = (row: Customer) => ({
  value: row.id,
  label: row.name,
  sublabel: [row.name_kana, row.phone].filter(Boolean).join(' / '),
})
</script>

<template>
  <RemoteSelect
    :model-value="modelValue"
    :fetcher="fetcher"
    :fetch-one="fetchOne"
    :to-option="toOption"
    :placeholder="placeholder || '顧客を検索（氏名・カナ・電話・案件番号）'"
    :clearable="clearable"
    :disabled="disabled"
    :initial-option="initialOption"
    v-bind="$attrs"
    @update:model-value="(v: number | null) => $emit('update:modelValue', v)"
    @change="(row: Customer | null) => $emit('change', row)"
  />
</template>
