<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  createAccountingVehicleUsage,
  getAccountingVehicleUsage,
  updateAccountingVehicleUsage,
} from '../../api/accounting'
import type { VehicleUsagePayload } from '../../types/accounting'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)
const vehicleUsageId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => Boolean(vehicleUsageId.value))
const purposeOptions = ['客户拜访', '送资料', '跑役所', '银行手续', '看房', '购买物品', '公司业务', '其他']
const form = ref<VehicleUsagePayload>({
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

const fetchVehicleUsage = async () => {
  if (!vehicleUsageId.value) return
  const vehicleUsage = await getAccountingVehicleUsage(vehicleUsageId.value)
  form.value = {
    usage_date: vehicleUsage.usage_date,
    place: vehicleUsage.place,
    distance_km: vehicleUsage.distance_km,
    usage_target: vehicleUsage.usage_target,
    purpose: vehicleUsage.purpose,
    note: vehicleUsage.note,
    is_exported: false,
  }
}

const submit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (vehicleUsageId.value) {
      await updateAccountingVehicleUsage(vehicleUsageId.value, form.value)
      ElMessage.success('用車記録を更新しました。')
    } else {
      await createAccountingVehicleUsage(form.value)
      ElMessage.success('用車記録を作成しました。')
    }
    router.push('/accounting/vehicle-usages')
  } catch {
    ElMessage.error(isEdit.value ? '用車記録の更新に失敗しました。' : '用車記録の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchVehicleUsage()
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
      <h1>{{ isEdit ? '用車記録編集' : '新規用車記録' }}</h1>
      <el-button @click="router.push('/accounting/vehicle-usages')">戻る</el-button>
    </div>

    <el-card v-loading="loading" shadow="never">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <div class="form-grid">
          <el-form-item label="日付" prop="usage_date">
            <el-date-picker
              v-model="form.usage_date"
              type="date"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              placeholder="YYYY-MM-DD"
              class="form-control"
            />
          </el-form-item>
          <el-form-item label="場所" prop="place">
            <el-input v-model="form.place" />
          </el-form-item>
          <el-form-item label="走行距離" prop="distance_km">
            <el-input v-model="form.distance_km" inputmode="decimal" />
          </el-form-item>
          <el-form-item label="利用対象" prop="usage_target">
            <el-input v-model="form.usage_target" />
          </el-form-item>
          <el-form-item label="用途" prop="purpose">
            <el-select v-model="form.purpose" clearable placeholder="選択してください" class="form-control">
              <el-option v-for="purpose in purposeOptions" :key="purpose" :label="purpose" :value="purpose" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="備考" prop="note">
          <el-input v-model="form.note" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <el-button @click="router.push('/accounting/vehicle-usages')">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </div>
    </el-card>
  </section>
</template>
