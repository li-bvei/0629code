<script setup lang="ts">
// 帳票の状態表示と遷移（遷移先は後端がその帳票の Workflow から返す。帳票どうしの状態は連動しない）。
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { transitionBusinessDocument } from '../../api/accounting'
import type { BusinessDocumentEndpoint } from '../../types/accounting'
import { apiErrorText } from './voucherErrors'

const props = defineProps<{
  endpoint: BusinessDocumentEndpoint
  doc: { id: number; status_value: string; status_display: string; allowed_transitions: { value: string; label: string }[] }
}>()
const emit = defineEmits<{ (e: 'changed'): void }>()

const DATE_TARGETS: Record<string, string> = { paid: '入金日', signed: '締結日' }
const VOID_TARGETS = new Set(['cancelled', 'voided', 'declined', 'terminated'])

const tagType = (value: string) => {
  if (!value) return 'info'
  if (value === 'draft') return 'info'
  if (['paid', 'accepted', 'signed'].includes(value)) return 'success'
  if (VOID_TARGETS.has(value)) return 'danger'
  return 'primary'
}

const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const run = async (target: string) => {
  const option = props.doc.allowed_transitions.find((t) => t.value === target)
  const label = option?.label ?? target
  let reason = ''
  let date: string | null = null
  try {
    if (DATE_TARGETS[target]) {
      const result = await ElMessageBox.prompt(`${DATE_TARGETS[target]}を入力してください（YYYY-MM-DD）。`, `「${label}」に変更`, {
        inputValue: today(), inputPattern: /^\d{4}-\d{2}-\d{2}$/, inputErrorMessage: 'YYYY-MM-DD で入力してください',
        confirmButtonText: '変更', cancelButtonText: 'キャンセル',
      })
      date = result.value
    } else {
      const leavingDraft = ['', 'draft'].includes(props.doc.status_value) && !VOID_TARGETS.has(target)
      const note = leavingDraft ? '変更後は宛先・金額などを編集できなくなります（発行時の内容を記録します）。' : ''
      const result = await ElMessageBox.prompt(`${note}理由・メモ（任意）`, `「${label}」に変更`, {
        confirmButtonText: '変更', cancelButtonText: 'キャンセル', inputPlaceholder: '例：郵送で提出',
      })
      reason = result.value || ''
    }
  } catch {
    return
  }
  try {
    await transitionBusinessDocument(props.endpoint, props.doc.id, { status: target, reason, date })
    ElMessage.success(`「${label}」に変更しました。`)
    emit('changed')
  } catch (error) {
    ElMessage.error(apiErrorText(error, '状態を変更できませんでした。'))
  }
}
</script>

<template>
  <div class="voucher-status">
    <el-tag :type="tagType(doc.status_value)" size="small">{{ doc.status_display }}</el-tag>
    <el-dropdown v-if="doc.allowed_transitions.length" trigger="click" @command="run">
      <el-button text size="small" type="primary">変更<el-icon><ArrowDown /></el-icon></el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item v-for="t in doc.allowed_transitions" :key="t.value" :command="t.value">{{ t.label }}</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<style scoped>
.voucher-status {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
}
</style>
