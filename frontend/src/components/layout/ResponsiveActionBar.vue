<script setup lang="ts">
// 詳細画面・ヘッダーの操作列。
// 広い画面：collapse が 'always' 以外はボタンで並べ、折り返す。
// 640px 未満：collapse 'never' のボタンだけ全幅で縦に並べ、残りは「その他」メニューへ入れる。
// 表示の切り替えは CSS だけで行う（画面幅の監視はしない）。
import { computed } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { splitBarActions, type ActionItem } from './actions'

const props = withDefaults(defineProps<{
  actions: ActionItem[]
  moreLabel?: string
  label?: string
}>(), {
  moreLabel: 'その他',
  label: '操作',
})

const split = computed(() => splitBarActions(props.actions))
const menuItems = computed(() => [...split.value.collapsible, ...split.value.overflow])
const hasDesktopMenu = computed(() => split.value.overflow.length > 0)
const byKey = computed(() => new Map(menuItems.value.map((action) => [action.key, action])))

const run = (key: string) => {
  const action = byKey.value.get(key)
  if (action && !action.disabled) action.onClick()
}
</script>

<template>
  <div class="responsive-action-bar" role="toolbar" :aria-label="label">
    <el-button
      v-for="action in split.pinned"
      :key="action.key"
      :type="action.type || undefined"
      :plain="action.plain"
      :disabled="action.disabled"
      :loading="action.loading"
      @click="action.onClick"
    >{{ action.label }}</el-button>
    <el-button
      v-for="action in split.collapsible"
      :key="action.key"
      class="rab-collapsible"
      :type="action.type || undefined"
      :plain="action.plain"
      :disabled="action.disabled"
      :loading="action.loading"
      @click="action.onClick"
    >{{ action.label }}</el-button>
    <el-dropdown
      v-if="menuItems.length"
      trigger="click"
      class="rab-more"
      :class="{ 'is-mobile-only': !hasDesktopMenu }"
      @command="run"
    >
      <el-button>{{ moreLabel }}<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="(action, index) in menuItems"
            :key="action.key"
            :command="action.key"
            :disabled="action.disabled"
            :divided="action.danger && index > 0"
            :class="{ 'danger-item': action.danger, 'rab-mobile-only': split.collapsible.includes(action) }"
          >{{ action.label }}</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>
