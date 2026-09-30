<script setup lang="ts">
// 本文と操作・補助情報の列を並べるレイアウト。
// 広い画面：本文 minmax(0, 1fr) と右列（既定 300px）。1100px 未満：右列を本文の下へ移す。
// 右列は sticky だが、下へ移ったときは通常の配置に戻る（位置の調整を各ページで行わない）。
withDefaults(defineProps<{
  sideWidth?: string
  sticky?: boolean
}>(), {
  sideWidth: '300px',
  sticky: true,
})
</script>

<template>
  <div class="record-form-layout" :class="{ 'has-side': $slots.side }" :style="{ '--record-side-width': sideWidth }">
    <div class="record-form-main">
      <slot />
    </div>
    <aside v-if="$slots.side" class="record-form-side" :class="{ 'is-sticky': sticky }">
      <slot name="side" />
    </aside>
  </div>
</template>
