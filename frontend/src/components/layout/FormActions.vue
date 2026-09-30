<script setup lang="ts">
// フォームの保存・取消などのボタン列。既定は右寄せ（取消 → 保存の順に書く）。
// 640px 未満：全幅の縦並びで、最後に書いたボタン（保存など）が一番上に来る。
// Dialog / Drawer では #footer に置く（本文をスクロールしてもボタンは下に固定される）。
withDefaults(defineProps<{
  align?: 'end' | 'start' | 'between'
}>(), {
  align: 'end',
})
</script>

<template>
  <div class="form-actions" :class="`is-align-${align}`">
    <div v-if="$slots.extra" class="form-actions-extra"><slot name="extra" /></div>
    <div class="form-actions-main"><slot /></div>
  </div>
</template>
