<script setup lang="ts">
// 業務フローを持つ案件（P4）の進捗表示と段階変更。入管の 13 段階は使わず、作成時に固定したフローの段階だけを出す。
// どの段階へも人工で変更でき（取下げ・取下げからの復帰を含む）、前後の段階は経過と監査に残る（後端）。
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Check, Close } from '@element-plus/icons-vue'
import { changeCaseStage } from '../../api/cases'
import type { Case } from '../../types/api'
import { currentStepIndex, isWithdrawnStage, stageChoices, stageSteps } from '../../utils/caseWorkflow'
import { responseOf } from '../../utils/apiErrors'

const props = defineProps<{ caseDetail: Case; disabled?: boolean }>()
const emit = defineEmits<{ (e: 'changed', value: Case): void }>()

const steps = computed(() => stageSteps(props.caseDetail))
const currentIndex = computed(() => currentStepIndex(props.caseDetail))
const withdrawn = computed(() => isWithdrawnStage(props.caseDetail))
const choices = computed(() => stageChoices(props.caseDetail))

const dialogVisible = ref(false)
const saving = ref(false)
const target = ref<number | null>(null)
const note = ref('')

const open = (stageId?: number | null) => {
  if (props.disabled) return
  target.value = stageId ?? choices.value[0]?.id ?? null
  note.value = ''
  dialogVisible.value = true
}

/** 13 段階の進捗コード（完了・再開など）に対応する段階で開く */
const openForStatus = (status: string) => {
  const stages = props.caseDetail.workflow_stages ?? []
  const match = status === 'completed'
    ? stages.find((stage) => stage.base_status === 'completed' && stage.is_active)
    : stages.find((stage) => !stage.is_withdrawn && stage.is_active && stage.base_status !== 'completed')
  open(match?.id)
}

const submit = async () => {
  if (!target.value) return ElMessage.warning('変更先の段階を選択してください。')
  saving.value = true
  try {
    const updated = await changeCaseStage(props.caseDetail.id, {
      stage: target.value, expected_stage: props.caseDetail.workflow_stage ?? null, note: note.value,
    })
    ElMessage.success(`段階を「${updated.workflow_stage_name}」に変更しました。`)
    dialogVisible.value = false
    emit('changed', updated)
  } catch (error) {
    const { status, data } = responseOf(error)
    const detail = (data as { detail?: string } | undefined)?.detail
    if (status === 409) ElMessage.error({ message: detail || '他の操作で段階が変わりました。画面を更新してください。', duration: 6000 })
    else if (status === 403) ElMessage.error('権限がありません（担当外の案件は変更できません）。')
    else ElMessage.error(detail || '段階を変更できませんでした。')
  } finally {
    saving.value = false
  }
}

defineExpose({ open, openForStatus })
</script>

<template>
  <div class="case-workflow">
    <p class="workflow-name">業務フロー：{{ caseDetail.workflow_template_name }}（作成時に固定。入管の 13 段階は使いません）</p>
    <div class="workflow-steps">
      <template v-for="(stage, index) in steps" :key="stage.id">
        <button type="button" class="workflow-step" :disabled="disabled || stage.id === caseDetail.workflow_stage || !stage.is_active"
                :class="{ 'is-done': !withdrawn && index < currentIndex, 'is-current': stage.id === caseDetail.workflow_stage }"
                @click="open(stage.id)">
          <span class="dot"><el-icon v-if="!withdrawn && index < currentIndex"><Check /></el-icon></span>
          <span class="label">{{ stage.name }}</span>
        </button>
        <span v-if="index < steps.length - 1" class="connector" :class="{ 'is-done': !withdrawn && index < currentIndex }" />
      </template>
      <template v-if="withdrawn">
        <span class="connector" />
        <span class="workflow-step is-withdrawn"><span class="dot"><el-icon><Close /></el-icon></span><span class="label">取下げ</span></span>
      </template>
    </div>
    <p v-if="withdrawn" class="workflow-note">取下げになっています。必要があれば「段階を変更」から他の段階へ戻せます（経過に残ります）。</p>

    <el-dialog v-model="dialogVisible" title="段階を変更" width="460px" :close-on-click-modal="false" append-to-body>
      <el-form label-position="top">
        <el-form-item label="現在の段階"><span>{{ caseDetail.workflow_stage_name }}</span></el-form-item>
        <el-form-item label="変更先">
          <el-select v-model="target" class="form-control">
            <el-option v-for="stage in choices" :key="stage.id" :label="stage.name" :value="stage.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="備考（任意。経過に残ります）">
          <el-input v-model="note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="saving" @click="submit">変更する</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.workflow-name,
.workflow-note {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.workflow-steps {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 0;
}

.workflow-step {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 72px;
  padding: 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--el-text-color-regular);
  font: inherit;
}

.workflow-step:disabled {
  cursor: default;
}

.dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--el-border-color);
  background: var(--el-bg-color);
  color: #fff;
}

.label {
  font-size: 12px;
}

.is-done .dot {
  background: var(--el-color-success);
  border-color: var(--el-color-success);
}

.is-current .dot {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-8);
}

.is-current .label {
  color: var(--el-color-primary-dark-2);
  font-weight: 600;
}

.is-withdrawn .dot {
  background: var(--el-color-info);
  border-color: var(--el-color-info);
}

.connector {
  width: 24px;
  height: 2px;
  background: var(--el-border-color);
}

.connector.is-done {
  background: var(--el-color-success);
}
</style>
