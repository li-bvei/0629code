<script setup lang="ts">
// 業務報告（P3）：その日の計画から報告の下書きを作り、編集・コピーする。社内に保存するだけで、メール・
// チャット等へ自動送信はしない。生成時の計画項目はスナップショットとして固定され、後から計画を変えても
// 保存済みの報告は変わらない。下書きは再生成でき、確定すると再生成できない（本文の編集はできる）。
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { confirmDailyReport, findDailyReport, generateDailyReport, listDailyReports, updateDailyReportText } from '../api/dailyPlan'
import RemoteStaffSelect from '../components/RemoteStaffSelect.vue'
import { useAuthStore } from '../stores/auth'
import type { DailyWorkReport } from '../types/api'
import { addDays, errorCode, isConflict, planErrorText, todayIso } from '../utils/dailyPlan'
import { formatDateTime } from '../utils/date'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const reportDate = ref(typeof route.query.date === 'string' ? route.query.date : todayIso())
const canViewOthers = computed(() => auth.canAny('cases.case_view_all', 'cases.case_change_all'))
const ownEmployeeId = computed(() => auth.user?.employee_id ?? null)
const viewEmployeeId = ref<number | null>(null)
const readOnly = computed(() => viewEmployeeId.value !== null && viewEmployeeId.value !== ownEmployeeId.value)

const report = ref<DailyWorkReport | null>(null)
const draftText = ref('')
const loading = ref(false)
const loadError = ref('')
const busy = ref<'' | 'generate' | 'save' | 'confirm'>('')
const recent = ref<DailyWorkReport[]>([])

const dirty = computed(() => report.value !== null && draftText.value !== report.value.final_text)

const load = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const employee = readOnly.value ? viewEmployeeId.value! : 'me'
    report.value = await findDailyReport(reportDate.value, employee)
    draftText.value = report.value?.final_text ?? ''
    recent.value = await listDailyReports({ employee, date_from: addDays(reportDate.value, -14), date_to: reportDate.value })
  } catch (error) {
    loadError.value = planErrorText(error, '業務報告を読み込めませんでした。')
  } finally {
    loading.value = false
  }
}

watch(reportDate, (value) => {
  router.replace({ query: { ...route.query, date: value } })
  load()
})
watch(viewEmployeeId, load)
onMounted(load)

const generate = async () => {
  let overwriteEdits = false
  if (report.value && (report.value.is_edited || dirty.value)) {
    try {
      await ElMessageBox.confirm('編集した本文があります。再生成すると、今の計画から本文を作り直し、編集内容は失われます。続けますか？',
        '再生成の確認', { confirmButtonText: '再生成する', cancelButtonText: 'キャンセル', type: 'warning' })
      overwriteEdits = true
    } catch {
      return
    }
  }
  busy.value = 'generate'
  try {
    report.value = await generateDailyReport(reportDate.value, { version: report.value?.updated_at, overwriteEdits })
    draftText.value = report.value.final_text
    ElMessage.success('計画から報告の下書きを作成しました。')
    recent.value = await listDailyReports({ employee: 'me', date_from: addDays(reportDate.value, -14), date_to: reportDate.value })
  } catch (error) {
    ElMessage.error({ message: planErrorText(error, '報告を作成できませんでした。'), duration: 6000 })
    if (isConflict(error) && errorCode(error) !== 'edited_exists') await load()
  } finally {
    busy.value = ''
  }
}

const save = async () => {
  if (!report.value) return
  busy.value = 'save'
  try {
    report.value = await updateDailyReportText(report.value.id, draftText.value, report.value.updated_at)
    ElMessage.success('保存しました。')
  } catch (error) {
    // 入力した本文は消さない（再読み込みはしない）。他の操作で変わっている場合は知らせる
    ElMessage.error({ message: planErrorText(error, '保存できませんでした（入力した本文は残っています）。'), duration: 6000 })
  } finally {
    busy.value = ''
  }
}

const confirmReport = async () => {
  if (!report.value) return
  if (dirty.value) {
    ElMessage.warning('先に本文を保存してください。')
    return
  }
  try {
    await ElMessageBox.confirm('確定すると、この報告は再生成できなくなります（本文の編集はできます）。確定しますか？', '確定の確認',
      { confirmButtonText: '確定する', cancelButtonText: 'キャンセル', type: 'info' })
  } catch {
    return
  }
  busy.value = 'confirm'
  try {
    report.value = await confirmDailyReport(report.value.id, report.value.updated_at)
    ElMessage.success('確定しました。')
  } catch (error) {
    ElMessage.error({ message: planErrorText(error, '確定できませんでした。'), duration: 6000 })
    if (isConflict(error)) await load()
  } finally {
    busy.value = ''
  }
}

const copyText = async () => {
  try {
    await navigator.clipboard.writeText(draftText.value)
    ElMessage.success('本文をコピーしました。')
  } catch {
    ElMessage.warning('コピーできませんでした。本文を選択してコピーしてください。')
  }
}

const items = computed(() => report.value?.snapshot.items ?? [])
</script>

<template>
  <section class="page daily-reports-page">
    <div class="page-header">
      <h1>業務報告</h1>
      <div class="header-actions">
        <el-button @click="router.push({ path: '/daily-plan', query: { date: reportDate } })">この日の計画へ</el-button>
      </div>
    </div>

    <div class="report-toolbar">
      <el-button-group>
        <el-button @click="reportDate = addDays(reportDate, -1)">前日</el-button>
        <el-button @click="reportDate = todayIso()">今日</el-button>
        <el-button :disabled="reportDate >= todayIso()" @click="reportDate = addDays(reportDate, 1)">翌日</el-button>
      </el-button-group>
      <el-date-picker v-model="reportDate" type="date" value-format="YYYY-MM-DD" :clearable="false" class="report-date" />
      <div v-if="canViewOthers" class="report-employee">
        <RemoteStaffSelect v-model="viewEmployeeId" clearable placeholder="自分の報告（他の担当者を選ぶと閲覧のみ）" />
      </div>
    </div>

    <el-alert type="info" :closable="false" show-icon class="page-alert"
              title="報告は社内に保存するだけで、メール・チャット等へ自動送信はしません。必要な場合は本文をコピーして使ってください。" />
    <el-alert v-if="readOnly" type="info" :closable="false" show-icon class="page-alert" title="他の担当者の報告を閲覧しています（変更はできません）。" />
    <el-alert v-if="loadError" :title="loadError" type="error" show-icon class="page-alert" />

    <div class="report-layout">
      <el-card v-loading="loading" shadow="never">
        <template #header>
          <div class="report-header">
            <span>{{ reportDate }} の報告</span>
            <el-tag v-if="report" :type="report.status === 'confirmed' ? 'success' : 'info'" size="small">{{ report.status_display }}</el-tag>
            <el-tag v-if="report?.is_edited" size="small" type="warning">編集あり</el-tag>
          </div>
        </template>
        <el-empty v-if="!report && !loading" :description="readOnly ? 'この日の報告はありません' : 'まだ報告がありません。計画から下書きを作成できます。'">
          <el-button v-if="!readOnly" type="primary" :loading="busy === 'generate'" @click="generate">計画から作成</el-button>
        </el-empty>
        <template v-else-if="report">
          <el-input v-model="draftText" type="textarea" :autosize="{ minRows: 12, maxRows: 30 }" :readonly="readOnly" class="report-text" />
          <p class="report-meta">生成：{{ formatDateTime(report.generated_at) }}<template v-if="report.confirmed_at">・確定：{{ formatDateTime(report.confirmed_at) }}</template></p>
          <div class="report-actions">
            <el-button @click="copyText">本文をコピー</el-button>
            <template v-if="!readOnly">
              <el-button type="primary" :loading="busy === 'save'" :disabled="!dirty || Boolean(busy)" @click="save">保存</el-button>
              <el-button v-if="report.status === 'draft'" :loading="busy === 'generate'" :disabled="Boolean(busy)" @click="generate">計画から再生成</el-button>
              <el-button v-if="report.status === 'draft'" type="success" plain :loading="busy === 'confirm'" :disabled="Boolean(busy)" @click="confirmReport">確定</el-button>
            </template>
          </div>
        </template>
      </el-card>

      <el-card shadow="never">
        <template #header>生成時の計画（スナップショット）</template>
        <el-table :data="items" size="small" empty-text="報告を作成すると表示されます">
          <el-table-column label="内容" min-width="180">
            <template #default="{ row }">
              <span :class="{ 'is-done': row.status === 'completed' }">{{ row.title }}</span>
              <div v-if="row.case" class="sub">{{ row.case.case_number }} {{ row.case.customer_name }}</div>
            </template>
          </el-table-column>
          <el-table-column label="状態" width="140">
            <template #default="{ row }">
              {{ row.status_display }}<span v-if="row.carried_to_date" class="sub">（→ {{ row.carried_to_date }}）</span>
            </template>
          </el-table-column>
        </el-table>
        <h4 class="recent-title">最近の報告</h4>
        <el-table :data="recent" size="small" empty-text="ありません">
          <el-table-column prop="report_date" label="日付" width="120" />
          <el-table-column prop="status_display" label="状態" width="90" />
          <el-table-column width="80">
            <template #default="{ row }"><el-button link type="primary" @click="reportDate = row.report_date">表示</el-button></template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </section>
</template>

<style scoped>
.page-header,
.report-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}

.page-header {
  justify-content: space-between;
}

.report-toolbar {
  margin-bottom: 12px;
}

.report-date {
  width: 160px;
}

.report-employee {
  width: 280px;
  max-width: 100%;
}

.report-layout {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: 16px;
  align-items: start;
}

.report-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-text :deep(textarea) {
  font-family: inherit;
  line-height: 1.7;
}

.report-meta {
  margin: 6px 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.report-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.report-actions .el-button + .el-button {
  margin-left: 0;
}

.is-done {
  text-decoration: line-through;
  color: var(--el-text-color-secondary);
}

.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.recent-title {
  margin: 16px 0 8px;
  font-size: 14px;
}

@media (max-width: 1100px) {
  .report-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
