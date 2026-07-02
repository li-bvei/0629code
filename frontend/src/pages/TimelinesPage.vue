<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listTimelines } from '../api/timelines'
import type { Timeline } from '../types/api'
import { formatDateTime } from '../utils/date'

const loading = ref(false)
const errorMessage = ref('')
const timelines = ref<Timeline[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

const fetchTimelines = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listTimelines({ page })
    timelines.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = 'データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTimelines()
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>タイムライン</h1>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never">
      <el-table v-loading="loading" :data="timelines" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="case_number" label="案件番号" min-width="150" />
        <el-table-column prop="title" label="タイトル" min-width="180" />
        <el-table-column prop="is_visible_to_client" label="顧客表示" width="110" />
        <el-table-column label="作成日時" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchTimelines"
        />
      </div>
    </el-card>
  </section>
</template>
