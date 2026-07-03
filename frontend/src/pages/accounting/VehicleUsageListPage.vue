<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  createAccountingVehicleUsage,
  deleteAccountingVehicleUsage,
  listAccountingVehicleUsages,
} from '../../api/accounting'
import type { AccountingListParams, VehicleUsage, VehicleUsagePayload } from '../../types/accounting'
import { formatDate } from '../../utils/date'
import './accounting.css'

const router = useRouter()
const loading = ref(false)
const errorMessage = ref('')
const vehicleUsages = ref<VehicleUsage[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filters = ref<AccountingListParams>({
  search: '',
  start_date: null,
  end_date: null,
  purpose: '',
})
const addDialogVisible = ref(false)
const addFormRef = ref<FormInstance>()
const submitting = ref(false)
const purposeOptions = ['客户拜访', '送资料', '跑役所', '银行手续', '看房', '购买物品', '公司业务', '其他']
const addForm = ref<VehicleUsagePayload>({
  usage_date: '',
  place: '',
  distance_km: '',
  usage_target: '',
  purpose: '',
  note: '',
  is_exported: false,
})

const rules: FormRules<VehicleUsagePayload> = {
  usage_date: [{ required: true, message: '日付を入力してください。', trigger: 'change' }],
  distance_km: [{ required: true, message: '走行距離を入力してください。', trigger: 'blur' }],
}

const formatDistance = (value: number | string) => `${Number(value || 0).toLocaleString()} km`

const fetchVehicleUsages = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listAccountingVehicleUsages({ ...filters.value, page })
    vehicleUsages.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = '用車記録の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const clearFilters = () => {
  filters.value = {
    search: '',
    start_date: null,
    end_date: null,
    purpose: '',
  }
  fetchVehicleUsages(1)
}

const openAddDialog = () => {
  addForm.value = {
    usage_date: '',
    place: '',
    distance_km: '',
    usage_target: '',
    purpose: '',
    note: '',
    is_exported: false,
  }
  addFormRef.value?.clearValidate()
  addDialogVisible.value = true
}

const submitAddVehicleUsage = async () => {
  if (!addFormRef.value) return
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createAccountingVehicleUsage(addForm.value)
    ElMessage.success('用車記録を作成しました。')
    addDialogVisible.value = false
    await fetchVehicleUsages(1)
  } catch {
    ElMessage.error('用車記録の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const confirmDelete = async (vehicleUsage: VehicleUsage) => {
  try {
    await ElMessageBox.confirm('この用車記録を削除します。よろしいですか？', '削除確認', {
      confirmButtonText: '削除',
      cancelButtonText: 'キャンセル',
      type: 'warning',
    })
    await deleteAccountingVehicleUsage(vehicleUsage.id)
    ElMessage.success('用車記録を削除しました。')
    await fetchVehicleUsages(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('用車記録の削除に失敗しました。')
    }
  }
}

onMounted(() => {
  fetchVehicleUsages()
})
</script>

<template>
  <section class="page accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>用車記録</h1>
          <p>業務で利用した移動距離と用途を記録します</p>
        </div>
        <div class="accounting-toolbar">
          <el-button type="primary" @click="openAddDialog">新規追加</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="accounting-card">
      <div class="accounting-filter-card">
        <div class="accounting-filter-row">
          <el-input v-model="filters.search" placeholder="場所・対象・備考で検索" clearable class="accounting-filter-search" />
          <el-date-picker
            v-model="filters.start_date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="開始日"
            class="accounting-filter-date"
          />
          <el-date-picker
            v-model="filters.end_date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="終了日"
            class="accounting-filter-date"
          />
          <el-select v-model="filters.purpose" clearable placeholder="用途" class="accounting-filter-select">
            <el-option v-for="purpose in purposeOptions" :key="purpose" :label="purpose" :value="purpose" />
          </el-select>
          <div class="accounting-filter-actions">
            <el-button type="primary" @click="fetchVehicleUsages(1)">検索</el-button>
            <el-button @click="clearFilters">クリア</el-button>
          </div>
        </div>
      </div>

      <el-table v-loading="loading" :data="vehicleUsages" stripe>
        <el-table-column label="日付" width="130">
          <template #default="{ row }">{{ formatDate(row.usage_date) }}</template>
        </el-table-column>
        <el-table-column prop="place" label="場所" min-width="150" />
        <el-table-column label="走行距離" width="130" align="right" header-align="right">
          <template #default="{ row }">{{ formatDistance(row.distance_km) }}</template>
        </el-table-column>
        <el-table-column prop="usage_target" label="利用対象" min-width="160" />
        <el-table-column prop="purpose" label="用途" min-width="140" />
        <el-table-column prop="note" label="備考" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="router.push(`/accounting/vehicle-usages/${row.id}/edit`)">編集</el-button>
            <el-button text type="danger" @click="confirmDelete(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!loading && !vehicleUsages.length" class="empty-text">データがありません</p>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchVehicleUsages"
        />
      </div>
    </el-card>

    <el-dialog v-model="addDialogVisible" title="用車記録を追加" width="720px">
      <el-form ref="addFormRef" :model="addForm" :rules="rules" label-position="top">
        <div class="accounting-dialog-form">
          <el-form-item label="日付" prop="usage_date">
            <el-date-picker
              v-model="addForm.usage_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="場所" prop="place">
            <el-input v-model="addForm.place" />
          </el-form-item>
          <el-form-item label="走行距離" prop="distance_km">
            <el-input v-model="addForm.distance_km" inputmode="decimal" />
          </el-form-item>
          <el-form-item label="利用対象" prop="usage_target">
            <el-input v-model="addForm.usage_target" />
          </el-form-item>
          <el-form-item label="用途" prop="purpose">
            <el-select v-model="addForm.purpose" clearable placeholder="選択してください" class="form-control">
              <el-option v-for="purpose in purposeOptions" :key="purpose" :label="purpose" :value="purpose" />
            </el-select>
          </el-form-item>
          <el-form-item label="備考" prop="note" class="accounting-dialog-full">
            <el-input v-model="addForm.note" type="textarea" :rows="3" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAddVehicleUsage">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
