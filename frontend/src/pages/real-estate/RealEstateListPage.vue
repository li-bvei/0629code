<script setup lang="ts">
// 不動産取引の総覧。見える範囲は後端が決める（一般職員は本人担当、業務管理者は全件閲覧）。
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { createTransaction, listTransactions } from '../../api/realEstate'
import { listEmployees } from '../../api/employees'
import RemoteCustomerSelect from '../../components/RemoteCustomerSelect.vue'
import { useAuthStore } from '../../stores/auth'
import type { Employee } from '../../types/api'
import type { RealEstateTransaction, RealEstateTransactionPayload } from '../../types/realEstate'
import { PAYMENT_OPTIONS, STAGE_OPTIONS, TYPE_OPTIONS } from '../../types/realEstate'
import { formatDate } from '../../utils/date'

const router = useRouter()
const auth = useAuthStore()
const rows = ref<RealEstateTransaction[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const errorMessage = ref('')
const employees = ref<Employee[]>([])
const filters = reactive({
  responsible_employee: '' as number | '', stage: '', management_company: '', payment_status: '', transaction_type: '',
  missing: false, keyword: '',
})

const fetchRows = async (target = page.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listTransactions({ page: target, ...filters })
    rows.value = data.results
    total.value = data.count
    page.value = target
  } catch {
    errorMessage.value = '不動産記録の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}
const resetFilters = () => {
  Object.assign(filters, { responsible_employee: '', stage: '', management_company: '', payment_status: '', transaction_type: '', missing: false, keyword: '' })
  fetchRows(1)
}
const yen = (v: string | null) => (v === null || v === '' ? '-' : `￥${Number(v).toLocaleString()}`)

// --- 新規（首画面は 7 項目だけ。法定項目は詳細で段階的に補充） ---
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const emptyForm = (): RealEstateTransactionPayload => ({
  party_name: '', customer: null, property_name: '', room_number: '', management_company_name: '',
  responsible_employee: auth.user?.employee_id ?? null, transaction_type: 'rental', stage: 'inquiry',
})
const form = ref<RealEstateTransactionPayload>(emptyForm())
const rules: FormRules = {
  party_name: [{ required: true, message: '顧客・当事者名を入力してください。', trigger: 'blur' }],
  property_name: [{ required: true, message: '物件名を入力してください。', trigger: 'blur' }],
}
const openCreate = () => {
  form.value = emptyForm()
  formRef.value?.clearValidate()
  dialogVisible.value = true
}
const submit = async () => {
  if (!(await formRef.value?.validate().catch(() => false))) return
  saving.value = true
  try {
    const created = await createTransaction(form.value)
    ElMessage.success(`${created.transaction_number} を作成しました。`)
    dialogVisible.value = false
    router.push(`/real-estate/${created.id}`)
  } catch (error) {
    const data = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
    ElMessage.error(data?.status === 403 ? '他の担当者の記録は作成できません。' : '作成できませんでした。')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  fetchRows(1)
  try {
    employees.value = (await listEmployees({ page_size: 200 })).results
  } catch {
    employees.value = []
  }
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <div>
        <h1>不動産取引</h1>
        <p class="sub">賃貸を中心とした取引の総覧です。法定項目は各記録の画面で段階的に補充します。</p>
      </div>
      <el-button type="primary" @click="openCreate">新規登録</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="filter-card">
      <div class="filters">
        <el-select v-model="filters.responsible_employee" clearable filterable placeholder="担当" style="width: 140px">
          <el-option v-for="e in employees" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <el-select v-model="filters.stage" clearable placeholder="段階" style="width: 130px">
          <el-option v-for="o in STAGE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-input v-model="filters.management_company" clearable placeholder="管理会社" style="width: 150px" />
        <el-select v-model="filters.payment_status" clearable placeholder="支払状態" style="width: 130px">
          <el-option v-for="o in PAYMENT_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="filters.transaction_type" clearable placeholder="取引種別" style="width: 150px">
          <el-option v-for="o in TYPE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-input v-model="filters.keyword" clearable placeholder="番号・当事者・物件" style="width: 180px" @keyup.enter="fetchRows(1)" />
        <el-checkbox v-model="filters.missing">要補充のみ</el-checkbox>
        <el-button type="primary" @click="fetchRows(1)">検索</el-button>
        <el-button @click="resetFilters">リセット</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" stripe @row-click="(row: RealEstateTransaction) => router.push(`/real-estate/${row.id}`)">
        <el-table-column prop="transaction_number" label="番号" width="150" />
        <el-table-column label="当事者" min-width="130"><template #default="{ row }">{{ row.party_name }}</template></el-table-column>
        <el-table-column label="物件" min-width="170">
          <template #default="{ row }">{{ row.property_name }}<span v-if="row.room_number"> {{ row.room_number }}</span></template>
        </el-table-column>
        <el-table-column label="管理会社" min-width="120"><template #default="{ row }">{{ row.management_company_name || '-' }}</template></el-table-column>
        <el-table-column prop="responsible_employee_name" label="担当" width="90" />
        <el-table-column label="種別・段階" width="140">
          <template #default="{ row }">
            <el-tag size="small" :type="row.transaction_type === 'sale' ? 'warning' : 'info'">{{ row.transaction_type_display }}</el-tag>
            {{ row.stage_display }}
          </template>
        </el-table-column>
        <el-table-column label="取引日" width="105"><template #default="{ row }">{{ row.transaction_date ? formatDate(row.transaction_date) : '-' }}</template></el-table-column>
        <el-table-column label="仲介・広告" width="150" align="right">
          <template #default="{ row }">{{ yen(row.brokerage_fee) }} / {{ yen(row.advertising_fee) }}</template>
        </el-table-column>
        <el-table-column label="支払・振込" width="130">
          <template #default="{ row }">{{ row.payment_status_display }} / {{ row.transfer_status_display }}</template>
        </el-table-column>
        <el-table-column label="要補充・台帳" min-width="170">
          <template #default="{ row }">
            <el-tag v-for="m in row.missing_items" :key="m" size="small" type="warning" class="tag">{{ m }}</el-tag>
            <el-tag v-if="row.ledger_locked" size="small" type="success" class="tag">台帳ロック</el-tag>
            <el-tag v-else-if="row.has_ledger" size="small" class="tag">台帳あり</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination layout="prev, pager, next" :current-page="page" :page-size="20" :total="total" @current-change="fetchRows" />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" title="不動産取引を登録" width="620px">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="顧客・当事者" prop="party_name">
            <el-input v-model="form.party_name" placeholder="氏名・名称（軽量入力）" />
          </el-form-item>
          <el-form-item label="顧客主档（任意・自動では結び付けません）">
            <RemoteCustomerSelect v-model="form.customer" clearable />
          </el-form-item>
          <el-form-item label="物件名" prop="property_name"><el-input v-model="form.property_name" /></el-form-item>
          <el-form-item label="部屋番号"><el-input v-model="form.room_number" /></el-form-item>
          <el-form-item label="管理会社"><el-input v-model="form.management_company_name" /></el-form-item>
          <el-form-item label="担当">
            <el-select v-model="form.responsible_employee" filterable style="width: 100%">
              <el-option v-for="e in employees" :key="e.id" :label="e.name" :value="e.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="取引種別">
            <el-radio-group v-model="form.transaction_type">
              <el-radio value="rental">賃貸</el-radio>
              <el-radio value="sale">売買（記録のみ）</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="現在の段階">
            <el-select v-model="form.stage" style="width: 100%">
              <el-option v-for="o in STAGE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="saving" @click="submit">登録して開く</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.sub {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin: 4px 0 0;
}

.filter-card {
  margin-bottom: 12px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.tag {
  margin: 0 4px 2px 0;
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
