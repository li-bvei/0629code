<script setup lang="ts">
// 見積書・契約書の作成・編集ダイアログ。入力欄の共通部分（宛先・明細・関連案件）だけを共有し、
// 状態や番号は各帳票の後端 Workflow が決める。発行後は備考と関連案件だけ変更できる。
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import RemoteCaseSelect from '../RemoteCaseSelect.vue'
import FormActions from '../layout/FormActions.vue'
import VoucherLineItemsEditor from './VoucherLineItemsEditor.vue'
import { saveContract, saveEstimate } from '../../api/accounting'
import type { AccountingVoucherLineItem, BusinessDocumentPayload, Contract, Estimate } from '../../types/accounting'
import { apiErrorText } from './voucherErrors'

const props = defineProps<{ kind: 'estimate' | 'contract'; doc: Estimate | Contract | null }>()
const visible = defineModel<boolean>('visible', { required: true })
const emit = defineEmits<{ (e: 'saved'): void }>()

const label = computed(() => (props.kind === 'estimate' ? '見積書' : '契約書'))
const locked = computed(() => Boolean(props.doc && !props.doc.is_editable))
const saving = ref(false)

const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const DEFAULT_CONTRACT_BODY = [
  '第1条（委託業務）甲は乙に対し、上記件名に係る書類作成及び申請取次業務（以下「本業務」という。）を委託し、乙はこれを受託する。',
  '第2条（報酬）甲は乙に対し、本契約に定める報酬を支払条件に従って支払う。',
  '第3条（秘密保持）乙は、本業務により知り得た甲の情報を、甲の承諾なく第三者に開示しない。',
  '第4条（協議）本契約に定めのない事項は、甲乙誠意をもって協議のうえ解決する。',
].join('\n')

const emptyForm = () => ({
  issue_date: today(),
  recipient_name: '',
  recipient_honorific: props.kind === 'contract' ? '様' : '御中',
  recipient_postal_code: '',
  recipient_address: '',
  title: props.kind === 'contract' ? '業務委託契約書' : '',
  line_items: [{ item_name: '', quantity: 1, unit_price: 0, tax_category: 'tax_10', price_type: 'tax_included' }] as AccountingVoucherLineItem[],
  note: '',
  case: null as number | null,
  valid_until: null as string | null,
  start_date: null as string | null,
  end_date: null as string | null,
  payment_terms: '',
  body: props.kind === 'contract' ? DEFAULT_CONTRACT_BODY : '',
})

const form = reactive(emptyForm())

watch(visible, (open) => {
  if (!open) return
  const base = emptyForm()
  const doc = props.doc as (Partial<Estimate & Contract> | null)
  Object.assign(form, base, doc ? {
    issue_date: doc.issue_date, recipient_name: doc.recipient_name, recipient_honorific: doc.recipient_honorific ?? '',
    recipient_postal_code: doc.recipient_postal_code, recipient_address: doc.recipient_address, title: doc.title,
    line_items: (doc.line_items ?? []).map((item) => ({ ...item })), note: doc.note, case: doc.case ?? null,
    valid_until: doc.valid_until ?? null, start_date: doc.start_date ?? null, end_date: doc.end_date ?? null,
    payment_terms: doc.payment_terms ?? '', body: doc.body ?? '',
  } : {})
})

const caseOption = computed(() => (props.doc?.case ? { value: props.doc.case, label: props.doc.case_number } : null))

const buildPayload = (): Partial<BusinessDocumentPayload> => {
  if (locked.value) return { note: form.note, case: form.case }
  const common = {
    issue_date: form.issue_date, recipient_name: form.recipient_name, recipient_honorific: form.recipient_honorific,
    recipient_postal_code: form.recipient_postal_code, recipient_address: form.recipient_address, title: form.title,
    line_items: form.line_items.filter((item) => (item.item_name || '').trim()), note: form.note, case: form.case,
  }
  if (props.kind === 'estimate') return { ...common, valid_until: form.valid_until }
  return { ...common, start_date: form.start_date, end_date: form.end_date, payment_terms: form.payment_terms, body: form.body }
}

const submit = async () => {
  if (!form.issue_date) return ElMessage.warning('発行日を入力してください。')
  saving.value = true
  try {
    const id = props.doc?.id ?? null
    if (props.kind === 'estimate') await saveEstimate(id, buildPayload())
    else await saveContract(id, buildPayload())
    ElMessage.success(`${label.value}を保存しました。`)
    visible.value = false
    emit('saved')
  } catch (error) {
    ElMessage.error(apiErrorText(error, `${label.value}を保存できませんでした。`))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" :title="doc ? `${label}を編集` : `${label}を作成`" width="860px" class="accounting-expense-dialog">
    <el-alert v-if="locked" type="info" show-icon :closable="false" class="dialog-alert"
              :title="`発行後の${label}です。宛先・金額などは変更できません（備考と関連案件のみ変更できます）。`" />
    <el-form label-position="top">
      <div class="accounting-dialog-form">
        <el-form-item label="発行日" required>
          <el-date-picker v-model="form.issue_date" type="date" value-format="YYYY-MM-DD" :disabled="locked" class="form-control" />
        </el-form-item>
        <el-form-item v-if="kind === 'estimate'" label="有効期限">
          <el-date-picker v-model="form.valid_until" type="date" value-format="YYYY-MM-DD" :disabled="locked" class="form-control" />
        </el-form-item>
        <el-form-item v-else label="契約期間">
          <div class="period">
            <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" placeholder="開始日" :disabled="locked" />
            <span>〜</span>
            <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" placeholder="終了日" :disabled="locked" />
          </div>
        </el-form-item>
        <el-form-item :label="kind === 'contract' ? '委託者（甲）' : '宛先'" class="accounting-dialog-full">
          <div class="recipient">
            <el-input v-model="form.recipient_name" placeholder="会社名または個人名" :disabled="locked" />
            <el-select v-model="form.recipient_honorific" :disabled="locked" style="width: 100px">
              <el-option label="御中" value="御中" />
              <el-option label="様" value="様" />
              <el-option label="なし" value="" />
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="郵便番号">
          <el-input v-model="form.recipient_postal_code" :disabled="locked" />
        </el-form-item>
        <el-form-item label="住所">
          <el-input v-model="form.recipient_address" :disabled="locked" />
        </el-form-item>
        <el-form-item label="件名" class="accounting-dialog-full">
          <el-input v-model="form.title" :disabled="locked" />
        </el-form-item>
        <el-form-item :label="kind === 'contract' ? '報酬の明細' : '明細'" class="accounting-dialog-full">
          <VoucherLineItemsEditor v-model="form.line_items" :disabled="locked" style="width: 100%" />
        </el-form-item>
        <template v-if="kind === 'contract'">
          <el-form-item label="支払条件" class="accounting-dialog-full">
            <el-input v-model="form.payment_terms" :disabled="locked" placeholder="例：着手時に全額を指定口座へ振込" />
          </el-form-item>
          <el-form-item label="契約条項" class="accounting-dialog-full">
            <el-input v-model="form.body" type="textarea" :rows="8" :disabled="locked" />
          </el-form-item>
        </template>
        <el-form-item label="関連案件（任意）">
          <RemoteCaseSelect v-model="form.case" clearable :initial-option="caseOption" placeholder="担当案件から選択" />
        </el-form-item>
        <el-form-item label="備考" class="accounting-dialog-full">
          <el-input v-model="form.note" type="textarea" :rows="2" />
        </el-form-item>
      </div>
    </el-form>
    <template #footer>
      <FormActions>
        <el-button @click="visible = false">キャンセル</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </FormActions>
    </template>
  </el-dialog>
</template>

<style scoped>
.recipient,
.period {
  display: flex;
  gap: 8px;
  width: 100%;
  align-items: center;
  min-width: 0;
}

.recipient .el-input {
  flex: 1 1 auto;
  min-width: 0;
}

.period {
  flex-wrap: wrap;
}

.period :deep(.el-date-editor) {
  flex: 1 1 140px;
  min-width: 0;
}

.dialog-alert {
  margin-bottom: 12px;
}
</style>
