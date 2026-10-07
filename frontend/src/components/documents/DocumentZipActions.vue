<script setup lang="ts">
// ZIP 一括ダウンロード（P2）。案件詳細と書類管理で共通の部品。対象は 1 つの案件の中だけ。
// ファイルごとの権限は後端が判定し、権限の無いもの・実体の無いものは ZIP に入らない（除いた数を表示する）。
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadDocumentsZip, type ZipRefusal } from '../../api/documents'
import { saveBlob } from '../vouchers/voucherErrors'

const props = defineProps<{
  caseId: number | null
  selectedIds: number[]
}>()

const busy = ref<'' | 'selected' | 'all'>('')

const refusalText = (error: unknown) => {
  const refusal = (error as { refusal?: ZipRefusal })?.refusal
  if (refusal) {
    const reasons = Array.from(new Set(refusal.skipped.map((row) => row.label)))
    return reasons.length ? `${refusal.detail}（${reasons.join('、')}）` : refusal.detail
  }
  const status = (error as { response?: { status?: number }; status?: number })?.response?.status
  if (status === 404) return '案件が見つかりません。'
  if (status === 403) return 'ダウンロードの権限がありません。'
  return 'ZIP を作成できませんでした。通信状況を確認して再試行してください。'
}

const download = async (mode: 'selected' | 'all') => {
  if (!props.caseId || busy.value) return
  busy.value = mode
  try {
    const result = await downloadDocumentsZip(props.caseId, mode === 'all' ? { all: true } : { ids: props.selectedIds })
    saveBlob(result.blob, result.filename)
    if (result.skipped) {
      ElMessage.warning(`${result.included} 件を ZIP にしました。${result.skipped} 件は含めていません（理由は ZIP 内の「ダウンロード結果.txt」）。`)
    } else {
      ElMessage.success(`${result.included} 件を ZIP にしました。`)
    }
  } catch (error) {
    ElMessage.error({ message: refusalText(error), duration: 6000 })
  } finally {
    busy.value = ''
  }
}

defineExpose({ download, busy })
</script>

<template>
  <div class="zip-actions">
    <el-button :disabled="!caseId || !selectedIds.length || Boolean(busy)" :loading="busy === 'selected'" @click="download('selected')">
      選択したファイルを ZIP（{{ selectedIds.length }} 件）
    </el-button>
    <el-button :disabled="!caseId || Boolean(busy)" :loading="busy === 'all'" @click="download('all')">
      この案件のファイルをすべて ZIP
    </el-button>
  </div>
</template>

<style scoped>
.zip-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.zip-actions .el-button + .el-button {
  margin-left: 0;
}
</style>
