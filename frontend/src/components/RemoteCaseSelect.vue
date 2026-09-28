<script setup lang="ts">
// 案件の選択（範囲内の案件だけを後端が返す）。
import RemoteSelect from './RemoteSelect.vue'
import http from '../services/http'
import type { Case, PaginatedResponse } from '../types/api'

defineProps<{
  modelValue: number | null | undefined
  placeholder?: string
  clearable?: boolean
  disabled?: boolean
  initialOption?: { value: number, label: string, sublabel?: string } | null
}>()

defineEmits<{
  (e: 'update:modelValue', value: number | null): void
  (e: 'change', row: Case | null): void
}>()

const fetcher = async (search: string) => {
  const response = await http.get<PaginatedResponse<Case>>('/cases/', {
    params: { search: search || undefined, page_size: 20, view: 'all' },
  })
  return response.data.results
}

const fetchOne = async (id: number) => {
  try {
    const response = await http.get<Case>(`/cases/${id}/`)
    return response.data
  } catch {
    return null
  }
}

const toOption = (row: Case) => ({
  value: row.id,
  label: row.case_number,
  sublabel: [row.customer_name, row.status_display].filter(Boolean).join(' / '),
})
</script>

<template>
  <RemoteSelect
    :model-value="modelValue"
    :fetcher="fetcher"
    :fetch-one="fetchOne"
    :to-option="toOption"
    :placeholder="placeholder || '案件番号・顧客名で検索'"
    :clearable="clearable"
    :disabled="disabled"
    :initial-option="initialOption"
    @update:model-value="(v: number | null) => $emit('update:modelValue', v)"
    @change="(row: Case | null) => $emit('change', row)"
  />
</template>
