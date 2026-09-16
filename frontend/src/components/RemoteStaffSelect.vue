<script setup lang="ts">
import RemoteSelect from './RemoteSelect.vue'
import { listEmployees } from '../api/employees'
import type { Employee } from '../types/api'

defineProps<{
  modelValue: number | null | undefined
  placeholder?: string
  clearable?: boolean
  disabled?: boolean
  initialOption?: { value: number, label: string, sublabel?: string } | null
}>()

defineEmits<{
  (e: 'update:modelValue', value: number | null): void
  (e: 'change', row: Employee | null): void
}>()

const fetcher = async (search: string) => {
  const data = await listEmployees({ search: search || undefined, is_active: true, page_size: 20 })
  return data.results
}

const fetchOne = async (id: number) => {
  const data = await listEmployees({ page_size: 100 })
  return data.results.find((row) => row.id === id) ?? null
}

const toOption = (row: Employee) => ({
  value: row.id,
  label: row.name,
  sublabel: row.email || '',
})
</script>

<template>
  <RemoteSelect
    :model-value="modelValue"
    :fetcher="fetcher"
    :fetch-one="fetchOne"
    :to-option="toOption"
    :placeholder="placeholder || '担当者を検索（氏名）'"
    :clearable="clearable"
    :disabled="disabled"
    :initial-option="initialOption"
    v-bind="$attrs"
    @update:model-value="(v: number | null) => $emit('update:modelValue', v)"
    @change="(row: Employee | null) => $emit('change', row)"
  />
</template>
