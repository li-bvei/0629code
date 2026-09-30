<script setup lang="ts">
// 表の行操作：先頭 inline 個だけ文字ボタンで出し、残りは「その他」メニューへ。
// 危険な操作（削除など）は常にメニューの最後。操作列の幅を固定しやすくするためのもの。
import { computed } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { splitRowActions, type ActionItem } from './actions'

const props = withDefaults(defineProps<{
  actions: ActionItem[]
  inline?: number
  moreLabel?: string
}>(), {
  inline: 1,
  moreLabel: 'その他',
})

const split = computed(() => splitRowActions(props.actions, props.inline))
const run = (key: string) => {
  const action = split.value.overflow.find((item) => item.key === key)
  if (action && !action.disabled) action.onClick()
}
</script>

<template>
  <div class="table-row-actions">
    <el-button
      v-for="action in split.inline"
      :key="action.key"
      text
      size="small"
      :type="action.type || 'primary'"
      :disabled="action.disabled"
      :loading="action.loading"
      @click="action.onClick"
    >{{ action.label }}</el-button>
    <el-dropdown v-if="split.overflow.length" trigger="click" @command="run">
      <el-button text size="small" type="primary">{{ moreLabel }}<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="(action, index) in split.overflow"
            :key="action.key"
            :command="action.key"
            :disabled="action.disabled"
            :divided="action.danger && index > 0 && !split.overflow[index - 1]?.danger"
            :class="{ 'danger-item': action.danger }"
          >{{ action.label }}</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>
