<script setup lang="ts" generic="T extends { id: number }">
import { onMounted, ref, watch } from 'vue'

interface OptionRow {
  value: number
  label: string
  sublabel?: string
}

const props = defineProps<{
  modelValue: number | null | undefined
  /** 検索キーワードを受け取り、候補一覧を返す。サーバー側で検索・件数制限を行うこと。 */
  fetcher: (search: string) => Promise<T[]>
  /** 1件を id から取得（既存の選択値を初期表示するため）。無ければ resolveByList を使う。 */
  fetchOne?: (id: number) => Promise<T | null>
  toOption: (row: T) => OptionRow
  placeholder?: string
  clearable?: boolean
  disabled?: boolean
  /** 呼び出し側が既に対象オブジェクトを持っている場合、fetchOne を省略できる。 */
  initialOption?: OptionRow | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number | null): void
  (e: 'change', row: T | null): void
}>()

const options = ref<OptionRow[]>([])
const loading = ref(false)
const rowCache = new Map<number, T>()

const runSearch = async (search: string) => {
  loading.value = true
  try {
    const rows = await props.fetcher(search.trim())
    rows.forEach((row) => rowCache.set(row.id, row))
    const mapped = rows.map((row) => props.toOption(row))
    // 選択中の値が候補に含まれない場合でもラベルが消えないよう先頭に維持する。
    const selected = options.value.find((o) => o.value === props.modelValue)
    if (selected && !mapped.some((o) => o.value === selected.value)) {
      options.value = [selected, ...mapped]
    } else {
      options.value = mapped
    }
  } catch {
    options.value = []
  } finally {
    loading.value = false
  }
}

const ensureInitial = async () => {
  const id = props.modelValue
  if (!id) return
  if (options.value.some((o) => o.value === id)) return
  if (props.initialOption && props.initialOption.value === id) {
    options.value = [props.initialOption, ...options.value]
    return
  }
  if (props.fetchOne) {
    try {
      const row = await props.fetchOne(id)
      if (row) {
        rowCache.set(row.id, row)
        options.value = [props.toOption(row), ...options.value]
      }
    } catch {
      /* 取得失敗時は id のみ表示 */
    }
  }
}

const onChange = (value: number | null) => {
  emit('update:modelValue', value)
  emit('change', value ? rowCache.get(value) ?? null : null)
}

watch(() => props.modelValue, ensureInitial)
watch(() => props.initialOption, ensureInitial)

onMounted(async () => {
  await ensureInitial()
  await runSearch('')
})
</script>

<template>
  <el-select
    :model-value="modelValue ?? undefined"
    filterable
    remote
    :remote-method="runSearch"
    :loading="loading"
    :placeholder="placeholder || '検索して選択'"
    :clearable="clearable ?? true"
    :disabled="disabled"
    remote-show-suffix
    style="width: 100%"
    @change="onChange"
    @visible-change="(visible: boolean) => visible && !options.length && runSearch('')"
  >
    <el-option
      v-for="option in options"
      :key="option.value"
      :value="option.value"
      :label="option.label"
    >
      <span>{{ option.label }}</span>
      <span v-if="option.sublabel" style="color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px;">
        {{ option.sublabel }}
      </span>
    </el-option>
  </el-select>
</template>
