<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listTasks } from '../api/tasks'
import type { Task } from '../types/api'
import { formatDate, formatDateTime } from '../utils/date'

const loading = ref(false)
const errorMessage = ref('')
const tasks = ref<Task[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

const fetchTasks = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listTasks({ page })
    tasks.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = 'データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTasks()
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>タスク</h1>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never">
      <el-table v-loading="loading" :data="tasks" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="case_number" label="案件番号" min-width="150" />
        <el-table-column prop="title" label="タイトル" min-width="180" />
        <el-table-column prop="status" label="ステータス" width="130" />
        <el-table-column label="期限" width="130">
          <template #default="{ row }">{{ formatDate(row.due_date) }}</template>
        </el-table-column>
        <el-table-column label="更新日時" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchTasks"
        />
      </div>
    </el-card>
  </section>
</template>
