<script setup lang="ts">
// 事務所全体の「事業年度末月」。参照は全員、変更は system_admin（office.manage_office_settings）だけ（判定は後端）。
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOfficeSettings, updateFiscalYearEndMonth, type OfficeSettings } from '../api/office'
import { useAuthStore } from '../stores/auth'
import { formatDateTime } from '../utils/date'

const auth = useAuthStore()
const canManage = computed(() => auth.can('office.manage_office_settings'))
const current = ref<OfficeSettings | null>(null)
const month = ref<number | null>(null)
const saving = ref(false)
const months = Array.from({ length: 12 }, (_, i) => i + 1)

const load = async () => {
  try {
    current.value = await getOfficeSettings()
    month.value = current.value.fiscal_year_end_month
  } catch {
    current.value = null
  }
}
const save = async () => {
  if (!current.value || month.value === null) return
  if (!Number.isInteger(month.value) || month.value < 1 || month.value > 12) return ElMessage.warning('1〜12 の月を選択してください。')
  if (month.value === current.value.fiscal_year_end_month && current.value.source === 'database') return ElMessage.info('変更はありません。')
  try {
    await ElMessageBox.confirm(
      `事業年度末月を ${current.value.fiscal_year_end_month} 月から ${month.value} 月に変更します。` +
      '新しく作成・締めを行う不動産台帳から適用されます。年度締め済みの台帳の事業年度・保存期限は変わりません。',
      '事業年度末月の変更', { confirmButtonText: '変更する', cancelButtonText: 'キャンセル', type: 'warning' },
    )
  } catch {
    return
  }
  saving.value = true
  try {
    current.value = await updateFiscalYearEndMonth(month.value)
    ElMessage.success('変更しました（監査記録に残ります）。')
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    ElMessage.error(status === 403 ? '変更の権限がありません。' : '変更できませんでした。')
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<template>
  <el-card v-if="current" shadow="never" class="settings-card">
    <template #header>事務所設定：事業年度末月</template>
    <p class="hint">
      事務所全体で 1 つの値です（顧客・会社ごとの設定ではありません）。不動産の法定台帳の事業年度と保存期限の計算に使います。
      台帳は作成時・年度締め時の末月を快照として保存するため、ここを変更しても年度締め済みの台帳には遡って影響しません。
    </p>
    <div class="row">
      <el-select v-model="month" :disabled="!canManage" style="width: 120px">
        <el-option v-for="m in months" :key="m" :label="`${m} 月`" :value="m" />
      </el-select>
      <el-button v-if="canManage" type="primary" :loading="saving" @click="save">保存</el-button>
      <span v-if="current.source === 'fallback'" class="hint">未設定のため初期値（{{ current.fiscal_year_end_month }} 月）を使用中</span>
      <span v-else class="hint">最終更新：{{ current.updated_by || '-' }}（{{ current.updated_at ? formatDateTime(current.updated_at) : '-' }}）</span>
    </div>
    <p v-if="!canManage" class="hint">変更は system_admin の権限を持つ人だけが行えます。</p>
  </el-card>
</template>

<style scoped>
.hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
