<script setup lang="ts">
import RemoteSelect from './RemoteSelect.vue'
import { getCompany, listCompanies } from '../api/companies'
import type { Company } from '../types/api'

defineProps<{
  modelValue: number | null | undefined
  placeholder?: string
  clearable?: boolean
  disabled?: boolean
  initialOption?: { value: number, label: string, sublabel?: string } | null
}>()

defineEmits<{
  (e: 'update:modelValue', value: number | null): void
  (e: 'change', row: Company | null): void
}>()

const fetcher = async (search: string) => {
  const data = await listCompanies({ search: search || undefined, page_size: 20 })
  return data.results
}

const fetchOne = async (id: number) => {
  try {
    return await getCompany(id) as unknown as Company
  } catch {
    return null
  }
}

const toOption = (row: Company) => ({
  value: row.id,
  label: row.name,
  sublabel: [row.name_kana, row.representative_name].filter(Boolean).join(' / '),
})
</script>

<template>
  <RemoteSelect
    :model-value="modelValue"
    :fetcher="fetcher"
    :fetch-one="fetchOne"
    :to-option="toOption"
    :placeholder="placeholder || '会社を検索（会社名・フリガナ）'"
    :clearable="clearable"
    :disabled="disabled"
    :initial-option="initialOption"
    v-bind="$attrs"
    @update:model-value="(v: number | null) => $emit('update:modelValue', v)"
    @change="(row: Company | null) => $emit('change', row)"
  />
</template>
