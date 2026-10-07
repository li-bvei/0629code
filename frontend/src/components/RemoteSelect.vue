<script setup lang="ts" generic="T extends { id: number }">
import { onMounted, watch } from 'vue'
import { createRemoteSearch, type RemoteFetchResult } from './remoteSearch'

interface OptionRow {
  value: number
  label: string
  sublabel?: string
}

const props = defineProps<{
  modelValue: number | null | undefined
  /** 検索キーワードを受け取り、候補一覧（または {results, count}）を返す。サーバー側で検索・件数制限を行うこと。 */
  fetcher: (search: string) => Promise<RemoteFetchResult<T>>
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

const { options, loading, error, rowCache, runSearch, ensureInitial, hiddenCount } = createRemoteSearch<T>({
  fetcher: (search) => props.fetcher(search),
  fetchOne: props.fetchOne ? (id) => props.fetchOne!(id) : undefined,
  toOption: (row) => props.toOption(row),
  getModelValue: () => props.modelValue,
  getInitialOption: () => props.initialOption,
})

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
    <template #empty>
      <p class="remote-select-empty" :class="{ 'is-error': error }">{{ error || (loading ? '読み込み中…' : '該当する候補がありません') }}</p>
    </template>
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
    <!-- 取得失敗は候補が残っていても（選択中の値を残している場合も）ここで知らせる -->
    <template v-if="(error && options.length) || hiddenCount() > 0" #footer>
      <p v-if="error && options.length" class="remote-select-more is-error" role="alert">{{ error }}</p>
      <p v-else class="remote-select-more">ほかに {{ hiddenCount() }} 件あります。名前などを入力して絞り込んでください。</p>
    </template>
  </el-select>
</template>

<style scoped>
.remote-select-empty {
  margin: 0;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.remote-select-more {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.remote-select-more.is-error,
.remote-select-empty.is-error {
  color: var(--el-color-danger);
}
</style>
