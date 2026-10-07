<script setup lang="ts">
// 案件の作業（旧「今日の作業台」の内容）：自分の次の対応・待機案件・担当案件。全体表示は case_view_all（後端で判定）。
// P3 で「毎日の計画」画面へ統合した。次の対応はボタンで計画の項目として追加できる（add-to-plan）。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { completeCaseNextAction, endCaseWaiting, getTodayWorkbench } from '../../api/cases'
import { useAuthStore } from '../../stores/auth'
import { formatDate } from '../../utils/date'
import type { TodayWorkbench, WorkbenchCaseRow } from '../../types/api'

const props = defineProps<{ canAddToPlan?: boolean }>()
const emit = defineEmits<{ (e: 'add-to-plan', row: WorkbenchCaseRow): void }>()

const auth = useAuthStore()
const scope = ref<'mine' | 'all'>('mine')
const activeTab = ref<'actions' | 'waiting' | 'cases'>('actions')
const loading = ref(false)
const errorMessage = ref('')
const data = ref<TodayWorkbench | null>(null)
const canViewAll = computed(() => auth.canAny('cases.case_view_all', 'cases.case_change_all'))

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    data.value = await getTodayWorkbench(scope.value)
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    errorMessage.value = status === 403 ? '全体表示の権限がありません。' : '作業台を読み込めませんでした。'
    data.value = null
  } finally {
    loading.value = false
  }
}

const changeScope = async (value: 'mine' | 'all') => {
  scope.value = value
  await load()
}

const dueTag = (row: WorkbenchCaseRow) => {
  if (row.due_status === 'overdue') return { type: 'danger' as const, label: '期限超過' }
  if (row.due_status === 'today') return { type: 'warning' as const, label: '今日まで' }
  return null
}

const completeAction = async (row: WorkbenchCaseRow) => {
  try {
    await ElMessageBox.confirm(`「${row.next_action}」を完了にしますか？`, '次の対応を完了', { type: 'info' })
  } catch {
    return
  }
  try {
    await completeCaseNextAction(row.id)
    ElMessage.success('完了にしました。')
    await load()
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    ElMessage.error(status === 403 ? '担当外の案件は変更できません。' : '完了にできませんでした。')
  }
}

const endWaiting = async (row: WorkbenchCaseRow) => {
  try {
    await ElMessageBox.confirm(`${row.case_number} の待機を解除しますか？`, '待機解除', { type: 'info' })
  } catch {
    return
  }
  try {
    await endCaseWaiting(row.id)
    ElMessage.success('待機を解除しました。')
    await load()
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    ElMessage.error(status === 403 ? '担当外の案件は変更できません。' : '待機を解除できませんでした。')
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section class="case-work-panel">
    <div class="panel-header">
      <h2>案件の作業</h2>
      <el-radio-group v-if="canViewAll" :model-value="scope" @change="(v: string | number | boolean | undefined) => changeScope(v as 'mine' | 'all')">
        <el-radio-button value="mine">自分</el-radio-button>
        <el-radio-button value="all">全体</el-radio-button>
      </el-radio-group>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="panel-alert" />
    <el-alert
      v-if="data && !data.employee_linked && scope === 'mine'"
      title="このアカウントは担当者に関連付いていないため、自分の案件を表示できません。管理者に確認してください。"
      type="warning"
      show-icon
      :closable="false"
      class="panel-alert"
    />

    <div v-if="data" class="workbench-summary">
      <button type="button" class="workbench-tile" :class="{ 'is-active': activeTab === 'actions' }" @click="activeTab = 'actions'">
        <strong>{{ data.summary.next_actions }}</strong><span>次の対応</span>
      </button>
      <button type="button" class="workbench-tile is-danger" @click="activeTab = 'actions'">
        <strong>{{ data.summary.overdue }}</strong><span>期限超過</span>
      </button>
      <button type="button" class="workbench-tile" @click="activeTab = 'actions'">
        <strong>{{ data.summary.today }}</strong><span>今日まで</span>
      </button>
      <button type="button" class="workbench-tile" :class="{ 'is-active': activeTab === 'waiting' }" @click="activeTab = 'waiting'">
        <strong>{{ data.summary.waiting }}</strong><span>待機中</span>
      </button>
      <button type="button" class="workbench-tile" :class="{ 'is-active': activeTab === 'cases' }" @click="activeTab = 'cases'">
        <strong>{{ data.summary.cases }}</strong><span>{{ scope === 'all' ? '進行中案件' : '担当案件' }}</span>
      </button>
    </div>

    <el-card v-loading="loading" shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="次の対応" name="actions">
          <el-table :data="data?.next_actions ?? []" empty-text="未完了の次の対応はありません" size="small">
            <el-table-column label="期限" width="130">
              <template #default="{ row }">
                <span>{{ row.next_action_due_at ? formatDate(row.next_action_due_at) : '期限なし' }}</span>
                <el-tag v-if="dueTag(row)" :type="dueTag(row)!.type" size="small" class="due-tag">{{ dueTag(row)!.label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="次の対応" min-width="220">
              <template #default="{ row }">
                <div>{{ row.next_action }}</div>
                <el-tag v-if="row.next_action_blocked_reason" size="small" type="danger" effect="plain">阻害：{{ row.next_action_blocked_reason }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="案件" min-width="200">
              <template #default="{ row }">
                <router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link>
                <div class="sub">{{ row.customer_name }}</div>
              </template>
            </el-table-column>
            <el-table-column v-if="scope === 'all'" label="担当" width="120">
              <template #default="{ row }">{{ row.next_action_assignee_name || row.responsible_employee_name || '未割当' }}</template>
            </el-table-column>
            <el-table-column width="170">
              <template #default="{ row }">
                <el-button v-if="props.canAddToPlan" size="small" type="primary" text @click="emit('add-to-plan', row)">計画に追加</el-button>
                <el-button size="small" type="success" text @click="completeAction(row)">完了</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="待機中" name="waiting">
          <el-table :data="data?.waiting ?? []" empty-text="待機中の案件はありません" size="small">
            <el-table-column label="案件" min-width="200">
              <template #default="{ row }">
                <router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link>
                <div class="sub">{{ row.customer_name }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="waiting_reason_display" label="理由" width="140" />
            <el-table-column label="経過" width="100">
              <template #default="{ row }">{{ row.waiting_days ?? 0 }}日</template>
            </el-table-column>
            <el-table-column label="予定終了" width="120">
              <template #default="{ row }">{{ row.waiting_until ? formatDate(row.waiting_until) : '-' }}</template>
            </el-table-column>
            <el-table-column v-if="scope === 'all'" prop="responsible_employee_name" label="担当" width="120" />
            <el-table-column width="110">
              <template #default="{ row }">
                <el-button size="small" type="warning" text @click="endWaiting(row)">待機解除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="scope === 'all' ? '進行中案件' : '担当案件'" name="cases">
          <el-table :data="data?.cases ?? []" empty-text="案件はありません" size="small">
            <el-table-column label="案件" min-width="200">
              <template #default="{ row }">
                <router-link class="text-link" :to="`/cases/${row.id}`">{{ row.case_number }}</router-link>
                <div class="sub">{{ row.customer_name }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="status_display" label="進捗" width="130" />
            <el-table-column label="作業状態" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.work_status === 'waiting'" type="warning" size="small">待機中</el-tag>
                <span v-else>対応中</span>
              </template>
            </el-table-column>
            <el-table-column label="次の対応" min-width="200">
              <template #default="{ row }">{{ row.next_action_state === 'open' ? row.next_action : '-' }}</template>
            </el-table-column>
            <el-table-column v-if="scope === 'all'" prop="responsible_employee_name" label="担当" width="120" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </section>
</template>

<style scoped>
.panel-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
}

.workbench-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.workbench-tile {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
  cursor: pointer;
  text-align: left;
}

.workbench-tile strong {
  font-size: 22px;
  line-height: 1.2;
}

.workbench-tile span {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.workbench-tile.is-active {
  border-color: var(--el-color-primary);
}

.workbench-tile.is-danger strong {
  color: var(--el-color-danger);
}

.workbench-tile:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}

.panel-alert {
  margin-bottom: 12px;
}

.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.due-tag {
  margin-left: 4px;
}
</style>
