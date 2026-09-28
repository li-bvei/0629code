<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  createAccountingIncomeSource,
  getAccountingIncomeSource,
  updateAccountingIncomeSource,
} from '../../api/accounting'
import type { IncomeSourcePayload } from '../../types/accounting'
import RemoteCaseSelect from '../../components/RemoteCaseSelect.vue'
import RemoteCompanySelect from '../../components/RemoteCompanySelect.vue'
import RemoteCustomerSelect from '../../components/RemoteCustomerSelect.vue'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)
const incomeSourceId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => Boolean(incomeSourceId.value))
const form = ref<IncomeSourcePayload>({
  source_date: '',
  source_target: '',
  amount: '',
  note: '',
  is_exported: false,
  customer: null,
  company: null,
  case: null,
})
const caseInitial = ref<{ value: number, label: string } | null>(null)

const rules: FormRules<IncomeSourcePayload> = {
  source_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  amount: [{ required: true, message: '金額を入力してください。', trigger: 'blur' }],
}

const fetchIncomeSource = async () => {
  if (!incomeSourceId.value) return
  const incomeSource = await getAccountingIncomeSource(incomeSourceId.value)
  form.value = {
    source_date: incomeSource.source_date,
    source_target: incomeSource.source_target,
    amount: incomeSource.amount,
    note: incomeSource.note,
    is_exported: false,
    customer: incomeSource.customer ?? null,
    company: incomeSource.company ?? null,
    case: incomeSource.case ?? null,
  }
  caseInitial.value = incomeSource.case
    ? { value: incomeSource.case, label: incomeSource.case_number || `#${incomeSource.case}` }
    : null
}

const submit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (incomeSourceId.value) {
      await updateAccountingIncomeSource(incomeSourceId.value, form.value)
      ElMessage.success('収入来源を更新しました。')
    } else {
      await createAccountingIncomeSource(form.value)
      ElMessage.success('収入来源を作成しました。')
    }
    router.push('/accounting/income-sources')
  } catch {
    ElMessage.error(isEdit.value ? '収入来源の更新に失敗しました。' : '収入来源の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchIncomeSource()
  } catch {
    ElMessage.error('データの取得に失敗しました。')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>{{ isEdit ? '収入来源編集' : '新規収入来源' }}</h1>
      <el-button @click="router.push('/accounting/income-sources')">戻る</el-button>
    </div>

    <el-card v-loading="loading" shadow="never">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="日付" prop="source_date">
            <el-date-picker
              v-model="form.source_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="対象" prop="source_target">
            <el-input v-model="form.source_target" />
          </el-form-item>
          <el-form-item label="金額" prop="amount">
            <el-input v-model="form.amount" inputmode="numeric" />
          </el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="関連案件（任意）" prop="case">
            <RemoteCaseSelect v-model="form.case" :initial-option="caseInitial" />
          </el-form-item>
          <el-form-item label="関連顧客（任意）" prop="customer">
            <RemoteCustomerSelect v-model="form.customer" />
          </el-form-item>
          <el-form-item label="関連会社（任意）" prop="company">
            <RemoteCompanySelect v-model="form.company" />
          </el-form-item>
        </div>
        <el-form-item label="備考" prop="note">
          <el-input v-model="form.note" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <el-button @click="router.push('/accounting/income-sources')">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-card>
  </section>
</template>
