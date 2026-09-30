<script setup lang="ts">
// 入力欄のまとまり。見出し・説明と、列数を指定したグリッド（640px 未満は 1 列）。
// 1 行全体を使う欄には class="form-grid-full" を付ける。
withDefaults(defineProps<{
  title?: string
  description?: string
  columns?: 1 | 2 | 3
}>(), {
  columns: 2,
})
</script>

<template>
  <section class="form-section">
    <header v-if="title || description || $slots.extra" class="form-section-header">
      <div class="form-section-heading">
        <h3 v-if="title">{{ title }}</h3>
        <p v-if="description">{{ description }}</p>
      </div>
      <div v-if="$slots.extra" class="form-section-extra"><slot name="extra" /></div>
    </header>
    <div class="form-section-grid" :class="`is-cols-${columns}`">
      <slot />
    </div>
  </section>
</template>
