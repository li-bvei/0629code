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
      <el-empty description="準備中">
        <el-tag type="info">この機能は今後追加予定です。</el-tag>
      </el-empty>
    </el-card>
  </section>
</template>
