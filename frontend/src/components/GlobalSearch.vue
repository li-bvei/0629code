<script setup lang="ts">
// 全体検索：後端が権限範囲だけを返す。範囲外の顧客・会社は開けない（最小識別情報のみ）。
import { onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { globalSearch, type SearchGroup, type SearchItem } from '../api/search'

const router = useRouter()
const q = ref('')
const groups = ref<SearchGroup[]>([])
const open = ref(false)
const loading = ref(false)
const hint = ref('')
let timer: ReturnType<typeof setTimeout> | null = null
let requestId = 0

const run = async () => {
  const text = q.value.trim()
  if (text.length < 2) {
    groups.value = []
    hint.value = text ? '2 文字以上で検索します' : ''
    return
  }
  const current = ++requestId
  loading.value = true
  try {
    const data = await globalSearch(text)
    if (current !== requestId) return
    groups.value = data.groups.filter((g) => g.items.length)
    hint.value = groups.value.length ? '' : '該当するものはありません（閲覧できる範囲だけを検索します）'
  } catch {
    if (current === requestId) hint.value = '検索できませんでした'
  } finally {
    if (current === requestId) loading.value = false
  }
}
const onInput = () => {
  open.value = true
  if (timer) clearTimeout(timer)
  timer = setTimeout(run, 300)
}
const go = (item: SearchItem) => {
  if (!item.can_open || !item.url) return
  open.value = false
  q.value = ''
  groups.value = []
  router.push(item.url)
}
const close = () => setTimeout(() => { open.value = false }, 150)
onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
</script>

<template>
  <div class="global-search">
    <el-input v-model="q" clearable placeholder="案件・顧客・会社・書類・不動産を検索"
              @input="onInput" @focus="open = Boolean(q)" @blur="close" @keyup.esc="open = false" />
    <div v-if="open && (groups.length || hint || loading)" class="panel">
      <div v-if="loading" class="hint">検索中…</div>
      <div v-else-if="hint" class="hint">{{ hint }}</div>
      <div v-for="group in groups" :key="group.type" class="group">
        <div class="group-label">{{ group.label }}</div>
        <div v-for="item in group.items" :key="`${group.type}-${item.id}`" class="item"
             :class="{ disabled: !item.can_open }" @mousedown.prevent="go(item)">
          <div class="title">{{ item.title }}</div>
          <div class="sub">{{ item.subtitle }}<span v-if="item.note" class="note">{{ item.note }}</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.global-search {
  position: relative;
  width: min(360px, 40vw);
}

.panel {
  position: absolute;
  top: 38px;
  left: 0;
  right: 0;
  z-index: 3000;
  max-height: 60vh;
  overflow: auto;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
  padding: 6px 0;
}

.hint {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.group-label {
  padding: 6px 12px 2px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
}

.item {
  padding: 6px 12px;
  cursor: pointer;
}

.item:hover {
  background: var(--el-fill-color-light);
}

.item.disabled {
  cursor: default;
  opacity: 0.7;
}

.title {
  font-size: 13px;
}

.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.note {
  margin-left: 6px;
  color: var(--el-color-warning);
}
</style>
