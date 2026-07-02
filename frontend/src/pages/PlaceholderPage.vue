<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>{{ title }}</h1>
    </div>

    <el-card shadow="never" class="placeholder-card">
      <p>準備中</p>
    </el-card>
  </section>
</template>
