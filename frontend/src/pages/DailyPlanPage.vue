<script setup lang="ts">
// 毎日の計画（P3）：案件の作業と社内作業を 1 日の計画として並べ、完了（打ち消し線）・結果メモ・結転を行う。
// 項目は Task の拡張（別のタスク仕組みは作らない）。自分の計画だけ変更でき、全件閲覧権限があれば他の人の計画を
// 読むだけで見られる（後端の TaskRule で判定）。旧「今日の作業台」の内容は右側の「案件の作業」に統合した。
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  carryOverPlanItem, carryOverPlanItems, createPlanItem, deletePlanItem, getCalendarDay, listPlanItems, reorderPlanItems,
  updatePlanItem, type CalendarDayInfo, type CarryBatchResult,
} from '../api/dailyPlan'
import RemoteCaseSelect from '../components/RemoteCaseSelect.vue'
import RemoteStaffSelect from '../components/RemoteStaffSelect.vue'
import CaseWorkPanel from '../components/workbench/CaseWorkPanel.vue'
import { useAuthStore } from '../stores/auth'
import type { Task, TaskPriority, WorkbenchCaseRow } from '../types/api'
import {
  PRIORITY_OPTIONS, addDays, canEditItem, carryBatchSummary, carryDateHint, isConflict, isDone, isOpen, moveItem, nextWeekday,
  planErrorText, planSummary, sortPlan, todayIso, versionPayload,
} from '../utils/dailyPlan'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const workDate = ref(typeof route.query.date === 'string' ? route.query.date : todayIso())
const ownEmployeeId = computed(() => auth.user?.employee_id ?? null)
const canViewOthers = computed(() => auth.canAny('cases.case_view_all', 'cases.case_change_all'))
const viewEmployeeId = ref<number | null>(null)  // null＝自分
const readOnly = computed(() => viewEmployeeId.value !== null && viewEmployeeId.value !== ownEmployeeId.value)
const employeeLinked = computed(() => ownEmployeeId.value !== null)

const items = ref<Task[]>([])
const loading = ref(false)
const loadError = ref('')
const busyId = ref<number | null>(null)  // 1 行ずつの処理中（成功・失敗のどちらでも finally で戻す）
const reordering = ref(false)

const ordered = computed(() => sortPlan(items.value))
const summary = computed(() => planSummary(items.value))

const load = async () => {
  loading.value = true
  loadError.value = ''
  try {
    items.value = await listPlanItems(workDate.value, readOnly.value ? viewEmployeeId.value! : 'me')
  } catch (error) {
    loadError.value = planErrorText(error, '計画を読み込めませんでした。')
  } finally {
    loading.value = false
  }
}

watch(workDate, (value) => {
  router.replace({ query: { ...route.query, date: value } })
  selectedIds.value = []
  load()
})
watch(viewEmployeeId, () => {
  selectedIds.value = []
  load()
})
onMounted(load)

const replaceItem = (updated: Task) => {
  items.value = items.value.map((item) => (item.id === updated.id ? updated : item))
}

const handleError = async (error: unknown, fallback?: string) => {
  ElMessage.error({ message: planErrorText(error, fallback), duration: 6000 })
  if (isConflict(error)) await load()  // 他の操作で変わっていれば最新を読み直す
}

// --- 追加（失敗しても入力は残す） ---------------------------------------------------------
const addForm = reactive({ title: '', priority: 'normal' as TaskPriority, case: null as number | null, description: '' })
const adding = ref(false)
const addItem = async () => {
  if (!addForm.title.trim()) {
    ElMessage.warning('内容を入力してください。')
    return
  }
  adding.value = true
  try {
    const created = await createPlanItem({
      title: addForm.title.trim(), work_date: workDate.value, priority: addForm.priority,
      case: addForm.case, description: addForm.description.trim(),
    })
    items.value = [...items.value, created]
    Object.assign(addForm, { title: '', priority: 'normal', case: null, description: '' })
  } catch (error) {
    await handleError(error, '追加できませんでした。')
  } finally {
    adding.value = false
  }
}

const addFromCase = async (row: WorkbenchCaseRow) => {
  try {
    const created = await createPlanItem({ title: row.next_action || `${row.case_number} の対応`, work_date: workDate.value, case: row.id })
    items.value = [...items.value, created]
    ElMessage.success('計画に追加しました。')
  } catch (error) {
    await handleError(error, '計画に追加できませんでした。')
  }
}

// --- 完了・結果メモ ----------------------------------------------------------------------
const toggleDone = async (item: Task) => {
  if (busyId.value === item.id) return
  busyId.value = item.id
  try {
    replaceItem(await updatePlanItem(item.id, { status: isDone(item) ? 'pending' : 'completed' }, item.updated_at))
  } catch (error) {
    await handleError(error)
  } finally {
    busyId.value = null
  }
}

const noteDrafts = reactive<Record<number, string>>({})
const noteValue = (item: Task) => noteDrafts[item.id] ?? item.result_note ?? ''
const saveNote = async (item: Task) => {
  const value = noteValue(item)
  // Enter と blur の二重保存を防ぐ（保存中は次の保存をしない。古い版で送って 409 になるのを避ける）
  if (busyId.value === item.id || value === (item.result_note ?? '')) return
  busyId.value = item.id
  try {
    replaceItem(await updatePlanItem(item.id, { result_note: value }, item.updated_at))
    delete noteDrafts[item.id]
  } catch (error) {
    await handleError(error, '結果メモを保存できませんでした（入力内容は残しています）。')
  } finally {
    busyId.value = null
  }
}

// --- 並べ替え（全体を 1 つの操作として保存） -------------------------------------------------
const move = async (item: Task, direction: -1 | 1) => {
  const next = moveItem(ordered.value, item.id, direction)
  if (next === ordered.value) return
  reordering.value = true
  try {
    const saved = await reorderPlanItems(workDate.value, versionPayload(next))
    const byId = new Map(saved.map((row) => [row.id, row]))
    items.value = items.value.map((row) => byId.get(row.id) ?? row)
  } catch (error) {
    await handleError(error, '並べ替えを保存できませんでした。')
  } finally {
    reordering.value = false
  }
}

// --- 編集 ---------------------------------------------------------------------------
const editVisible = ref(false)
const editTarget = ref<Task | null>(null)
const editForm = reactive({ title: '', description: '', priority: 'normal' as TaskPriority, case: null as number | null, status: 'pending' })
const saving = ref(false)
const openEdit = (item: Task) => {
  editTarget.value = item
  Object.assign(editForm, {
    title: item.title, description: item.description, priority: item.priority ?? 'normal', case: item.case, status: item.status,
  })
  editVisible.value = true
}
const caseInitialOption = computed(() => (
  editTarget.value?.case ? { value: editTarget.value.case, label: editTarget.value.case_number || `案件 #${editTarget.value.case}` } : null
))
const submitEdit = async () => {
  if (!editTarget.value) return
  saving.value = true
  try {
    replaceItem(await updatePlanItem(editTarget.value.id, { ...editForm, title: editForm.title.trim() }, editTarget.value.updated_at))
    editVisible.value = false
  } catch (error) {
    await handleError(error)  // ダイアログは閉じず、入力を残す
  } finally {
    saving.value = false
  }
}

const removeItem = async (item: Task) => {
  try {
    await ElMessageBox.confirm(`「${item.title}」を計画から削除しますか？`, '削除の確認', {
      confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning',
    })
  } catch {
    return
  }
  busyId.value = item.id
  try {
    await deletePlanItem(item.id, item.updated_at)
    items.value = items.value.filter((row) => row.id !== item.id)
  } catch (error) {
    await handleError(error, '削除できませんでした。')
  } finally {
    busyId.value = null
  }
}

// --- 結転（1 件・まとめて） ------------------------------------------------------------
const selectedIds = ref<number[]>([])
const carryVisible = ref(false)
const carryTargets = ref<Task[]>([])
const carryDate = ref('')
const carrying = ref(false)
const carryResult = ref<CarryBatchResult | null>(null)
const carryDayInfo = ref<CalendarDayInfo | null>(null)
const carryCalendarLoading = ref(false)
const carryHint = computed(() => carryDateHint(carryDayInfo.value))
let carryOpenToken = 0
const openCarry = async (targets: Task[]) => {
  const token = ++carryOpenToken
  carryTargets.value = targets
  const provisional = nextWeekday(workDate.value)  // 暦を読めるまでの仮の既定
  carryDate.value = provisional
  carryResult.value = null
  carryVisible.value = true
  carryCalendarLoading.value = true
  try {
    const info = await getCalendarDay(workDate.value)
    // 読み込み中に利用者が日付を変えていたら上書きしない
    if (token === carryOpenToken && carryDate.value === provisional) carryDate.value = info.next_business_day
  } catch {
    // 暦を読めなくても結転はできる（次の月〜金のまま）
  } finally {
    if (token === carryOpenToken) carryCalendarLoading.value = false
  }
}
let carryInfoToken = 0
watch([carryDate, carryVisible], async ([date, visible]) => {
  const token = ++carryInfoToken
  carryDayInfo.value = null
  if (!visible || !date) return
  try {
    const info = await getCalendarDay(date)
    if (token === carryInfoToken) carryDayInfo.value = info
  } catch {
    // 注意を出せないだけ（結転は止めない）
  }
})
const openCarrySelected = () => openCarry(ordered.value.filter((item) => selectedIds.value.includes(item.id) && isOpen(item)))
const openCarryAllOpen = () => openCarry(ordered.value.filter(isOpen))
const submitCarry = async () => {
  if (!carryDate.value || carryDate.value <= workDate.value) {
    ElMessage.warning('結転先は今日の計画より後の日付にしてください。')
    return
  }
  carrying.value = true
  try {
    if (carryTargets.value.length === 1) {
      const target = carryTargets.value[0]
      const result = await carryOverPlanItem(target.id, carryDate.value, target.updated_at)
      replaceItem(result.original)
      ElMessage.success(`${carryDate.value} に結転しました。`)
      carryVisible.value = false
    } else {
      const result = await carryOverPlanItems(carryDate.value, versionPayload(carryTargets.value))
      carryResult.value = result
      await load()
      if (result.failed) ElMessage.warning(carryBatchSummary(result))
      else {
        ElMessage.success(carryBatchSummary(result))
        carryVisible.value = false
      }
    }
    selectedIds.value = []
  } catch (error) {
    await handleError(error, '結転できませんでした。')
  } finally {
    carrying.value = false
  }
}
const carryFailures = computed(() => (carryResult.value?.results ?? []).filter((row) => row.status === 'failed').map((row) => ({
  ...row, title: items.value.find((item) => item.id === row.id)?.title ?? `ID ${row.id}`,
})))

const toggleSelected = (item: Task) => {
  selectedIds.value = selectedIds.value.includes(item.id)
    ? selectedIds.value.filter((id) => id !== item.id) : [...selectedIds.value, item.id]
}

const priorityTag = (value?: string) => PRIORITY_OPTIONS.find((option) => option.value === value) ?? PRIORITY_OPTIONS[1]
const goReport = () => router.push({ path: '/daily-reports', query: { date: workDate.value } })
</script>

<template>
  <section class="page daily-plan-page">
    <div class="page-header">
      <h1>毎日の計画</h1>
      <div class="header-actions">
        <el-button @click="router.push('/cases')">案件一覧へ</el-button>
        <el-button type="primary" plain :disabled="readOnly" @click="goReport">この日の業務報告</el-button>
      </div>
    </div>

    <div class="plan-toolbar">
      <el-button-group>
        <el-button @click="workDate = addDays(workDate, -1)">前日</el-button>
        <el-button @click="workDate = todayIso()">今日</el-button>
        <el-button @click="workDate = addDays(workDate, 1)">翌日</el-button>
      </el-button-group>
      <el-date-picker v-model="workDate" type="date" value-format="YYYY-MM-DD" :clearable="false" class="plan-date" />
      <div v-if="canViewOthers" class="plan-employee">
        <RemoteStaffSelect v-model="viewEmployeeId" clearable placeholder="自分の計画（他の担当者を選ぶと閲覧のみ）" />
      </div>
      <span class="plan-summary">全 {{ summary.total }} 件・完了 {{ summary.done }}・未完了 {{ summary.open }}・結転 {{ summary.carried }}</span>
    </div>

    <el-alert v-if="!employeeLinked && !readOnly" type="warning" show-icon :closable="false" class="page-alert"
              title="このアカウントは担当者に関連付いていないため、計画を作成できません。管理者に確認してください。" />
    <el-alert v-if="readOnly" type="info" show-icon :closable="false" class="page-alert" title="他の担当者の計画を閲覧しています（変更はできません）。" />
    <el-alert v-if="loadError" :title="loadError" type="error" show-icon class="page-alert" />

    <div class="plan-layout" :class="{ 'is-single': readOnly }">
      <el-card shadow="never" class="plan-card">
        <form v-if="!readOnly && employeeLinked" class="plan-add" @submit.prevent="addItem">
          <el-input v-model="addForm.title" placeholder="やること（例：在留申請の書類確認）" maxlength="150" class="plan-add-title" />
          <el-select v-model="addForm.priority" class="plan-add-priority" aria-label="優先度">
            <el-option v-for="option in PRIORITY_OPTIONS" :key="option.value" :label="`優先度 ${option.label}`" :value="option.value" />
          </el-select>
          <div class="plan-add-case"><RemoteCaseSelect v-model="addForm.case" clearable placeholder="関連案件（任意・社内作業は空）" /></div>
          <el-input v-model="addForm.description" placeholder="備考（任意）" class="plan-add-note" />
          <el-button type="primary" native-type="submit" :loading="adding">追加</el-button>
        </form>

        <div v-if="!readOnly && ordered.some(isOpen)" class="plan-bulk">
          <el-button size="small" :disabled="!selectedIds.length" @click="openCarrySelected">選択した未完了を結転（{{ selectedIds.length }}）</el-button>
          <el-button size="small" @click="openCarryAllOpen">未完了をすべて結転</el-button>
        </div>

        <div v-loading="loading || reordering" class="plan-list">
          <el-empty v-if="!ordered.length && !loading" description="この日の計画はありません" />
          <div v-for="(item, index) in ordered" :key="item.id" class="plan-item"
               :class="{ 'is-done': item.status === 'completed', 'is-carried': item.status === 'carried_over', 'is-cancelled': item.status === 'cancelled' }">
            <div class="plan-item-check">
              <el-checkbox v-if="!readOnly && isOpen(item)" :model-value="selectedIds.includes(item.id)" aria-label="結転の対象に選ぶ"
                           @change="toggleSelected(item)" />
            </div>
            <div class="plan-item-main">
              <div class="plan-item-title">
                <el-checkbox :model-value="isDone(item)" :disabled="!canEditItem(item, readOnly) || busyId === item.id || item.status === 'cancelled'"
                             :aria-label="isDone(item) ? '未完了に戻す' : '完了にする'" @change="toggleDone(item)" />
                <el-tag size="small" :type="priorityTag(item.priority).tag" effect="plain">{{ priorityTag(item.priority).label }}</el-tag>
                <span class="plan-title-text">{{ item.title }}</span>
                <router-link v-if="item.case" class="text-link plan-case" :to="`/cases/${item.case}`">
                  {{ item.case_number }}<template v-if="item.case_customer_name">（{{ item.case_customer_name }}）</template>
                </router-link>
                <el-tag v-else size="small" type="info">社内</el-tag>
                <el-tag v-if="item.status === 'carried_over'" size="small" type="warning">→ {{ item.carried_to?.work_date }} に結転</el-tag>
                <el-tag v-if="item.carried_from_date" size="small" type="info">{{ item.carried_from_date }} から結転</el-tag>
                <el-tag v-if="['in_progress', 'paused', 'cancelled'].includes(item.status)" size="small">{{ item.status_display }}</el-tag>
              </div>
              <p v-if="item.description" class="plan-item-desc">{{ item.description }}</p>
              <div v-if="isDone(item) || item.result_note" class="plan-item-note">
                <el-input :model-value="noteValue(item)" size="small" placeholder="結果メモ（完了後の補足）" :disabled="readOnly || busyId === item.id"
                          @update:model-value="(v: string) => (noteDrafts[item.id] = v)" @keyup.enter="saveNote(item)" @blur="saveNote(item)" />
              </div>
            </div>
            <div v-if="!readOnly" class="plan-item-actions">
              <el-button text size="small" :disabled="index === 0 || reordering" aria-label="上へ" @click="move(item, -1)">↑</el-button>
              <el-button text size="small" :disabled="index === ordered.length - 1 || reordering" aria-label="下へ" @click="move(item, 1)">↓</el-button>
              <el-button v-if="isOpen(item)" text size="small" type="warning" :disabled="busyId === item.id" @click="openCarry([item])">結転</el-button>
              <el-button v-if="canEditItem(item, readOnly)" text size="small" :disabled="busyId === item.id" @click="openEdit(item)">編集</el-button>
              <el-button text size="small" type="danger" :loading="busyId === item.id" @click="removeItem(item)">削除</el-button>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 他の担当者の計画を見ているときは出さない（右側だけ自分の案件の作業になり、混同しやすいため） -->
      <el-card v-if="!readOnly" shadow="never" class="plan-side">
        <CaseWorkPanel :can-add-to-plan="employeeLinked" @add-to-plan="addFromCase" />
      </el-card>
    </div>

    <el-dialog v-model="editVisible" title="計画の項目を編集" width="min(520px, 96vw)">
      <el-form label-position="top">
        <el-form-item label="内容" required><el-input v-model="editForm.title" maxlength="150" /></el-form-item>
        <el-form-item label="優先度">
          <el-radio-group v-model="editForm.priority">
            <el-radio v-for="option in PRIORITY_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状態">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="未開始" value="pending" /><el-option label="進行中" value="in_progress" />
            <el-option label="一時停止" value="paused" /><el-option label="完了" value="completed" /><el-option label="取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="関連案件（変更できる案件だけ）">
          <RemoteCaseSelect v-model="editForm.case" clearable :initial-option="caseInitialOption" placeholder="社内作業は空" />
        </el-form-item>
        <el-form-item label="備考"><el-input v-model="editForm.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="carryVisible" title="結転" width="min(480px, 96vw)">
      <p>未完了の {{ carryTargets.length }} 件を次の日の計画へ送ります。元の項目は {{ workDate }} に「結転済み」として残ります。</p>
      <el-form label-position="top">
        <el-form-item label="結転先の日付（既定は次の営業日：土日・祝日・振替休日・国民の休日を除く）">
          <el-date-picker v-model="carryDate" type="date" value-format="YYYY-MM-DD" :clearable="false" style="width: 100%" />
          <div v-if="carryCalendarLoading" class="carry-hint">次の営業日を確認しています…</div>
          <div v-else-if="carryHint" class="carry-hint is-warning">{{ carryHint }}</div>
        </el-form-item>
      </el-form>
      <el-alert v-if="carryFailures.length" type="warning" :closable="false" show-icon :title="`結転できなかった項目（${carryFailures.length} 件）`">
        <ul class="carry-failures">
          <li v-for="row in carryFailures" :key="row.id">{{ row.title }}：{{ row.detail }}</li>
        </ul>
      </el-alert>
      <template #footer>
        <el-button @click="carryVisible = false">閉じる</el-button>
        <el-button type="primary" :loading="carrying" :disabled="!carryTargets.length" @click="submitCarry">結転する</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.header-actions .el-button + .el-button {
  margin-left: 0;
}

.plan-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 12px;
}

.plan-date {
  width: 160px;
}

.plan-employee {
  width: 280px;
  max-width: 100%;
}

.plan-summary {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.plan-layout {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: 16px;
  align-items: start;
}

.plan-layout.is-single {
  grid-template-columns: minmax(0, 1fr);
}

.plan-add {
  display: grid;
  grid-template-columns: 120px minmax(0, 1.5fr) minmax(0, 1fr) auto;
  gap: 8px;
  margin-bottom: 12px;
}

.plan-add-title {
  grid-column: 1 / -1;
}

.plan-bulk {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.plan-bulk .el-button + .el-button {
  margin-left: 0;
}

.plan-list {
  min-height: 80px;
}

.plan-item {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
  padding: 8px 4px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.plan-item-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.plan-title-text {
  font-weight: 500;
}

.plan-item.is-done .plan-title-text,
.plan-item.is-cancelled .plan-title-text {
  text-decoration: line-through;
  color: var(--el-text-color-secondary);
}

.plan-item.is-carried {
  opacity: 0.7;
}

.plan-case {
  font-size: 12px;
}

.plan-item-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: pre-wrap;
}

.plan-item-note {
  margin-top: 6px;
  max-width: 520px;
}

.plan-item-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.plan-item-actions .el-button + .el-button {
  margin-left: 0;
}

.carry-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.carry-hint.is-warning {
  color: var(--el-color-warning-dark-2);
}

.carry-failures {
  margin: 4px 0 0;
  padding-left: 18px;
}

@media (max-width: 1100px) {
  .plan-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 767px) {
  .plan-add {
    grid-template-columns: minmax(0, 1fr);
  }

  .plan-item {
    grid-template-columns: 24px minmax(0, 1fr);
  }

  .plan-item-actions {
    grid-column: 2;
    justify-content: flex-start;
  }
}
</style>
