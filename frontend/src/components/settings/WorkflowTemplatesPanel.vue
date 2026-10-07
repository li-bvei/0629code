<script setup lang="ts">
// 業務フローと段階の設定（P4）。変更は案件設定の権限者のみ（後端で判定し、変更前後を監査に残す）。
// 既存案件は作成時のフローと段階を持ち続ける：案件で使われたフローは、名称・系統・有効状態と全段階（追加・名称・
// 順番・有効状態・削除）を変更できない。変えたいときは「複製」で新しいフローを作り、案件種別を結び付け直す。
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteWorkflowStage, duplicateWorkflowTemplate, listWorkflowTemplates, saveWorkflowStage } from '../../api/cases'
import type { CaseStatus, WorkflowStage, WorkflowTemplate } from '../../types/api'
import { caseStatusOptions } from '../../utils/caseStatus'
import { responseOf } from '../../utils/apiErrors'

defineProps<{ canEdit: boolean }>()
const emit = defineEmits<{ (e: 'changed'): void }>()

const templates = ref<WorkflowTemplate[]>([])
const loading = ref(false)

const fetch = async () => {
  loading.value = true
  try {
    templates.value = (await listWorkflowTemplates({ ordering: 'sort_order', page_size: 100 })).results
  } catch {
    ElMessage.error('業務フローの取得に失敗しました。')
  } finally {
    loading.value = false
  }
}

const errorText = (error: unknown, fallback: string) => {
  const { status, data } = responseOf(error)
  if (status === 403) return '案件設定を変更する権限がありません。'
  if (data && typeof data === 'object') {
    const values = Object.values(data as Record<string, unknown>).flat().map(String)
    if (values.length) return values.join(' ')
  }
  return fallback
}

const dialogVisible = ref(false)
const saving = ref(false)
const editingStage = ref<WorkflowStage | null>(null)
const form = reactive({ template: 0, code: '', name: '', base_status: 'preparing_documents' as CaseStatus, sort_order: 0, is_active: true })

const openCreate = (template: WorkflowTemplate) => {
  editingStage.value = null
  const last = template.stages[template.stages.length - 1]
  Object.assign(form, { template: template.id, code: '', name: '', base_status: 'preparing_documents', sort_order: (last?.sort_order ?? 0) + 5, is_active: true })
  dialogVisible.value = true
}
const openEdit = (stage: WorkflowStage) => {
  editingStage.value = stage
  Object.assign(form, { template: stage.template, code: stage.code, name: stage.name, base_status: stage.base_status, sort_order: stage.sort_order, is_active: stage.is_active })
  dialogVisible.value = true
}

const submit = async () => {
  if (!form.name.trim()) return ElMessage.warning('段階名を入力してください。')
  if (!editingStage.value && !/^[a-z0-9_-]+$/.test(form.code)) return ElMessage.warning('コードは半角英小文字・数字・_・- で入力してください。')
  saving.value = true
  try {
    const payload = editingStage.value
      ? { name: form.name.trim(), base_status: form.base_status, sort_order: form.sort_order, is_active: form.is_active }
      : { ...form, name: form.name.trim() }
    await saveWorkflowStage(editingStage.value?.id ?? null, payload)
    ElMessage.success('段階を保存しました。')
    dialogVisible.value = false
    await fetch()
    emit('changed')
  } catch (error) {
    ElMessage.error({ message: errorText(error, '段階を保存できませんでした。'), duration: 6000 })
  } finally {
    saving.value = false
  }
}

const remove = async (stage: WorkflowStage) => {
  try {
    await ElMessageBox.confirm(`段階「${stage.name}」を削除しますか？（案件で使われていない段階だけ削除できます）`, '削除の確認',
      { confirmButtonText: '削除', cancelButtonText: 'キャンセル', type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteWorkflowStage(stage.id)
    ElMessage.success('削除しました。')
    await fetch()
  } catch (error) {
    ElMessage.error({ message: errorText(error, '削除できませんでした。'), duration: 6000 })
  }
}

const duplicate = async (template: WorkflowTemplate) => {
  let code = ''
  let name = ''
  try {
    code = (await ElMessageBox.prompt('新しいフローのコード（半角英小文字・数字・_・-）', `「${template.name}」を複製`, {
      confirmButtonText: '次へ', cancelButtonText: 'キャンセル', inputPattern: /^[a-z0-9_-]+$/, inputErrorMessage: 'コードの形式が正しくありません',
      inputValue: `${template.code}_v2`,
    })).value
    name = (await ElMessageBox.prompt('新しいフローの名称', `「${template.name}」を複製`, {
      confirmButtonText: '複製する', cancelButtonText: 'キャンセル', inputValue: `${template.name}（新）`,
    })).value
  } catch {
    return
  }
  try {
    await duplicateWorkflowTemplate(template.id, { code, name })
    ElMessage.success('複製しました。案件種別の設定で新しいフローに結び付け直してください（既存の案件は元のフローのまま）。')
    await fetch()
    emit('changed')
  } catch (error) {
    ElMessage.error({ message: errorText(error, '複製できませんでした。'), duration: 6000 })
  }
}

onMounted(fetch)
defineExpose({ fetch, templates })
</script>

<template>
  <div v-loading="loading" class="workflow-panel">
    <p class="workflow-panel-note">
      案件種別に業務フローを結び付けると、その種別の新しい案件は入管の 13 段階ではなく、ここで定めた段階で管理します。
      既存の案件は作成時のフローのまま変わりません。「対応する進捗」は一覧・期限などの集計用です。
    </p>
    <el-card v-for="template in templates" :key="template.id" shadow="never" class="workflow-template-card">
      <template #header>
        <div class="setting-card-header">
          <span class="setting-card-title">
            {{ template.name }}
            <el-tag size="small" effect="plain">{{ template.family_display }}</el-tag>
            <el-tag v-if="!template.is_active" size="small" type="info">無効</el-tag>
          </span>
          <span v-if="canEdit" class="workflow-actions">
            <el-button v-if="!template.in_use" size="small" @click="openCreate(template)">段階を追加</el-button>
            <el-button size="small" @click="duplicate(template)">複製</el-button>
          </span>
        </div>
        <div class="workflow-types">使用している案件種別：{{ template.case_type_names.join('、') || 'なし' }}</div>
        <div v-if="template.in_use" class="workflow-types">
          <el-tag size="small" type="warning">案件で使用中（{{ template.case_count }} 件）</el-tag>
          このフローは変更できません。変える場合は「複製」して、案件種別を新しいフローに結び付け直してください。
        </div>
      </template>
      <el-table :data="template.stages" size="small">
        <el-table-column prop="sort_order" label="順番" width="70" />
        <el-table-column label="段階名" min-width="160">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="!row.is_active" size="small" type="info">無効</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="コード" width="150" />
        <el-table-column prop="base_status_display" label="対応する進捗（集計用）" width="170" />
        <el-table-column prop="case_count" label="使用中の案件" width="110" />
        <el-table-column v-if="canEdit && !template.in_use" label="操作" width="170">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">編集</el-button>
            <el-button text type="danger" @click="remove(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingStage ? '段階を編集' : '段階を追加'" width="480px" append-to-body
               :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="段階名" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="コード（作成後は変更できません）">
          <el-input v-model="form.code" :disabled="Boolean(editingStage)" placeholder="例：document_check" />
        </el-form-item>
        <el-form-item label="対応する進捗（集計用）">
          <el-select v-model="form.base_status" class="form-control">
            <el-option v-for="option in caseStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="順番"><el-input-number v-model="form.sort_order" :min="0" /></el-form-item>
        <el-form-item label="状態"><el-switch v-model="form.is_active" active-text="有効" inactive-text="無効（新しくは選べない）" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.workflow-panel-note,
.workflow-types {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.workflow-types {
  margin: 6px 0 0;
}

.workflow-actions {
  display: inline-flex;
  gap: 8px;
}

.workflow-template-card + .workflow-template-card {
  margin-top: 12px;
}
</style>
