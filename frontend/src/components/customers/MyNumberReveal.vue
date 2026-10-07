<script setup lang="ts">
// マイナンバーの表示（P6）。既定は「登録済み」の伏せ字。表示権限のある人だけ「表示」で後端に問い合わせ、
// 値はこの部品の中だけに持つ（store・localStorage・URL・ログに残さない）。「隠す」・別の対象への切り替え・
// 画面の終了で消える。タブ（el-tab-pane は非表示でも DOM に残る）など、見えなくなる切り替えでは resetKey を変えて消す。コピーは提供しない（必要になれば監査付きで別途追加する）。
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { revealMyNumber, type MyNumberTargetKind } from '../../api/customers'
import { useAuthStore } from '../../stores/auth'
import { myNumberErrorMessage, maskMyNumber } from '../../utils/myNumber'

const props = defineProps<{ kind: MyNumberTargetKind; targetId: number; registered: boolean; resetKey?: unknown }>()

const auth = useAuthStore()
const canReveal = computed(() => auth.can('customers.reveal_my_number'))
const value = ref('')
const loading = ref(false)
const error = ref('')

let requestToken = 0  // 応答待ちの間に対象が変わる・隠す・画面を離れたら、遅れて届いた値を表示しない
const hide = () => {
  requestToken += 1
  value.value = ''
  error.value = ''
  loading.value = false
}

const reveal = async () => {
  if (loading.value) return
  const token = ++requestToken
  loading.value = true
  error.value = ''
  try {
    const result = await revealMyNumber(props.kind, props.targetId)
    if (token !== requestToken) return
    value.value = result.registered ? result.my_number : ''
    if (!result.registered) error.value = '登録されていません。'
  } catch (caught) {
    if (token !== requestToken) return
    value.value = ''
    error.value = myNumberErrorMessage(caught)
  } finally {
    if (token === requestToken) loading.value = false
  }
}

watch(() => [props.kind, props.targetId, props.resetKey], hide)
onBeforeUnmount(hide)
</script>

<template>
  <span class="my-number-reveal">
    <template v-if="!registered">未登録</template>
    <template v-else>
      <span class="value" :class="{ revealed: Boolean(value) }" data-testid="my-number-value">{{ value || maskMyNumber() }}</span>
      <span v-if="!value" class="state">登録済み</span>
      <el-button v-if="canReveal && !value" text type="primary" size="small" :loading="loading" @click="reveal">表示</el-button>
      <el-button v-if="value" text size="small" @click="hide">隠す</el-button>
      <span v-if="error" class="error" role="alert">{{ error }}</span>
    </template>
  </span>
</template>

<style scoped>
.my-number-reveal { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
.value { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0.08em; color: var(--el-text-color-secondary); }
.value.revealed { color: var(--el-text-color-primary); }
.state { font-size: 12px; color: var(--el-text-color-secondary); }
.error { font-size: 12px; color: var(--el-color-danger); }
</style>
