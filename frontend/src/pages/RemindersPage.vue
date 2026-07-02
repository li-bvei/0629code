<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listReminders } from '../api/reminders'
import type { Reminder } from '../types/api'
import { formatDateTime } from '../utils/date'

const loading = ref(false)
const errorMessage = ref('')
const reminders = ref<Reminder[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20

const fetchReminders = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listReminders({ page })
    reminders.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = 'データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchReminders()
})
</script>

<template>
  <section class="page">
    <div class="page-header">
      <h1>リマインダー</h1>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never">
      <el-table v-loading="loading" :data="reminders" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="case_number" label="案件番号" min-width="150" />
        <el-table-column prop="title" label="タイトル" min-width="180" />
        <el-table-column label="提醒日時" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.remind_at) }}</template>
        </el-table-column>
        <el-table-column prop="is_done" label="完了" width="90" />
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
          @current-change="fetchReminders"
        />
      </div>
    </el-card>
  </section>
</template>
