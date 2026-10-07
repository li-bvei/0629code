<script setup lang="ts">
// サービス項目（P4）を選んで追加する検索欄。有効な項目だけを出す（無効の項目は新しく選べない）。
// 選ぶと pick を出して欄を空に戻す（同じ項目を続けて追加できる）。価格は「標準（参考）」として表示する。
import { nextTick, ref } from 'vue'
import RemoteSelect from '../RemoteSelect.vue'
import { listServiceItems } from '../../api/serviceItems'
import type { ServiceItem } from '../../types/accounting'
import { serviceOptionSublabel } from '../../utils/serviceItems'

defineProps<{ placeholder?: string; disabled?: boolean }>()
const emit = defineEmits<{ (e: 'pick', item: ServiceItem): void }>()

const selected = ref<number | null>(null)

const fetcher = async (search: string) => {
  const data = await listServiceItems({ search: search || undefined, active: '1', page_size: 30 })
  return { results: data.results, count: data.count }
}

const toOption = (row: ServiceItem) => ({
  value: row.id,
  label: row.name,
  sublabel: serviceOptionSublabel(row),
})

const onChange = async (row: ServiceItem | null) => {
  if (!row) return
  emit('pick', row)
  await nextTick()
  selected.value = null
}
</script>

<template>
  <div class="service-item-picker">
    <RemoteSelect v-model="selected" :fetcher="fetcher" :to-option="toOption" :disabled="disabled" :clearable="false"
                  :placeholder="placeholder || 'サービス項目から追加（標準価格は参考）'" @change="onChange" />
  </div>
</template>

<style scoped>
.service-item-picker {
  width: 320px;
  max-width: 100%;
}
</style>
