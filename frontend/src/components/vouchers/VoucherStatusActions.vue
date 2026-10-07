<script setup lang="ts">
// 帳票の状態表示と遷移（遷移先は後端がその帳票の Workflow から返す。帳票どうしの状態は連動しない）。
// 請求書・領収書（2026-10 P1）：有効な状態の間で自由に切り替えられ、発行済み・取消・無効からも下書きに戻せる。
// 変更中は二重送信を防ぐが、失敗しても必ず操作可能な状態に戻す（永久に無効・読み込み中にしない）。
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { transitionBusinessDocument } from '../../api/accounting'
import type { BusinessDocumentEndpoint } from '../../types/accounting'
import { apiErrorText, provisionalPriceNotice } from './voucherErrors'
import { transitionNotice } from './voucherStatus'

const props = defineProps<{
  endpoint: BusinessDocumentEndpoint
  doc: { id: number; status_value: string; status_display: string; allowed_transitions: { value: string; label: string }[] }
}>()
const emit = defineEmits<{ (e: 'changed'): void }>()

const DATE_TARGETS: Record<string, string> = { paid: '入金日', signed: '締結日' }
const VOID_TARGETS = new Set(['cancelled', 'voided', 'declined', 'terminated'])
const busy = ref(false)
const lastError = ref('')

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
  if (busy.value) return
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
      const note = transitionNotice(props.endpoint, props.doc.status_value, target)
      const result = await ElMessageBox.prompt(`${note}理由・メモ（任意）`, `「${label}」に変更`, {
        confirmButtonText: '変更', cancelButtonText: 'キャンセル', inputPlaceholder: '例：郵送で提出',
      })
      reason = result.value || ''
    }
  } catch {
    return
  }
  busy.value = true
  lastError.value = ''
  const send = (confirmProvisional = false) => transitionBusinessDocument(props.endpoint, props.doc.id, {
    status: target, reason, date, expected_status: props.doc.status_value, confirm_provisional: confirmProvisional,
  })
  try {
    try {
      await send()
    } catch (error) {
      // P6：暫定価格の行がある場合は、確認してから発行する（止めはしない）。キャンセルなら何も変えない
      const notice = provisionalPriceNotice(error)
      if (!notice) throw error
      try {
        await ElMessageBox.confirm(`${notice}\n暫定価格のまま「${label}」に変更しますか？`, '暫定価格の確認', {
          confirmButtonText: '暫定価格のまま変更', cancelButtonText: 'キャンセル', type: 'warning',
        })
      } catch {
        return
      }
      await send(true)
    }
    ElMessage.success(`「${label}」に変更しました。`)
    emit('changed')
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    lastError.value = apiErrorText(error, '状態を変更できませんでした。もう一度お試しください。')
    ElMessage.error({ message: lastError.value, duration: 6000 })
    if (status === 409) emit('changed') // 他の操作で状態が変わった：最新の状態を読み直す
  } finally {
    busy.value = false // 失敗しても必ず操作できる状態に戻す
  }
}
</script>

<template>
  <div class="voucher-status">
    <el-tag :type="tagType(doc.status_value)" size="small">{{ doc.status_display }}</el-tag>
    <el-dropdown v-if="doc.allowed_transitions.length" trigger="click" :disabled="busy" @command="run">
      <el-button text size="small" type="primary" :loading="busy">変更<el-icon v-if="!busy"><ArrowDown /></el-icon></el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item v-for="t in doc.allowed_transitions" :key="t.value" :command="t.value">{{ t.label }}</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
    <span v-if="lastError" class="voucher-status-error" :title="lastError">変更失敗</span>
  </div>
</template>

<style scoped>
.voucher-status {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
}

.voucher-status-error {
  font-size: 12px;
  color: var(--el-color-danger);
}
</style>
