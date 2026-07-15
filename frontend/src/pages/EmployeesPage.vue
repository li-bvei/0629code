<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { createEmployee, listEmployees, updateEmployee } from '../api/employees'
import type { Employee, EmployeePayload } from '../types/api'
import { formatDateTime } from '../utils/date'

const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const employees = ref<Employee[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const searchKeyword = ref('')
const activeFilter = ref('')
const dialogVisible = ref(false)
const editingEmployeeId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const employeeForm = ref<EmployeePayload>({
  name: '',
  email: '',
  phone: '',
  is_active: true,
})

const rules: FormRules<EmployeePayload> = {
  name: [{ required: true, message: '氏名を入力してください。', trigger: 'blur' }],
}

const fetchEmployees = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listEmployees({
      page,
      search: searchKeyword.value.trim() || undefined,
      is_active: activeFilter.value || undefined,
    })
    employees.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = '担当者の取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  editingEmployeeId.value = null
  employeeForm.value = {
    name: '',
    email: '',
    phone: '',
    is_active: true,
  }
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (employee: Employee) => {
  editingEmployeeId.value = employee.id
  employeeForm.value = {
    name: employee.name,
    email: employee.email,
    phone: employee.phone,
    is_active: employee.is_active,
  }
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

const submitEmployee = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload: EmployeePayload = {
      name: employeeForm.value.name.trim(),
      email: employeeForm.value.email?.trim() || '',
      phone: employeeForm.value.phone?.trim() || '',
      is_active: employeeForm.value.is_active ?? true,
    }
    if (editingEmployeeId.value) {
      await updateEmployee(editingEmployeeId.value, payload)
      ElMessage.success('担当者を更新しました。')
    } else {
      await createEmployee(payload)
      ElMessage.success('担当者を追加しました。')
    }
    dialogVisible.value = false
    await fetchEmployees(editingEmployeeId.value ? currentPage.value : 1)
  } catch {
    ElMessage.error(editingEmployeeId.value ? '担当者の更新に失敗しました。' : '担当者の追加に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const toggleEmployeeActive = async (employee: Employee) => {
  try {
    await updateEmployee(employee.id, { is_active: !employee.is_active })
    ElMessage.success(employee.is_active ? '担当者を無効にしました。' : '担当者を有効にしました。')
    await fetchEmployees(currentPage.value)
  } catch {
    ElMessage.error('有効状態の更新に失敗しました。')
  }
}

const searchEmployees = () => {
  fetchEmployees(1)
}

const clearSearch = () => {
  searchKeyword.value = ''
  activeFilter.value = ''
  fetchEmployees(1)
}

onMounted(() => {
  fetchEmployees()
})
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>担当者管理</h1>
      <el-button type="primary" @click="openCreateDialog">新規追加</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="search-card">
      <div class="search-row">
        <el-input
          v-model="searchKeyword"
          placeholder="氏名・メール・電話で検索"
          clearable
          @keyup.enter="searchEmployees"
        />
        <el-select v-model="activeFilter" clearable placeholder="有効状態" class="search-select">
          <el-option label="有効" value="true" />
          <el-option label="無効" value="false" />
        </el-select>
        <el-button type="primary" @click="searchEmployees">検索</el-button>
        <el-button @click="clearSearch">クリア</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="employees" stripe>
        <el-table-column prop="name" label="氏名" min-width="160" />
        <el-table-column prop="email" label="メール" min-width="220">
          <template #default="{ row }">{{ row.email || '-' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="電話" min-width="150">
          <template #default="{ row }">{{ row.phone || '-' }}</template>
        </el-table-column>
        <el-table-column label="有効状態" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '有効' : '無効' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新日時" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-dropdown trigger="click">
              <el-button text type="primary" class="table-action-trigger">
                操作
                <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="openEditDialog(row)">編集</el-dropdown-item>
                  <el-dropdown-item divided @click="toggleEmployeeActive(row)">
                    {{ row.is_active ? '無効化' : '有効化' }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchEmployees"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingEmployeeId ? '担当者編集' : '担当者追加'"
      width="520px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="employeeForm" :rules="rules" label-position="top">
        <el-form-item label="氏名" prop="name">
          <el-input v-model="employeeForm.name" />
        </el-form-item>
        <el-form-item label="メール" prop="email">
          <el-input v-model="employeeForm.email" />
        </el-form-item>
        <el-form-item label="電話" prop="phone">
          <el-input v-model="employeeForm.phone" />
        </el-form-item>
        <el-form-item label="有効状態" prop="is_active">
          <el-switch v-model="employeeForm.is_active" active-text="有効" inactive-text="無効" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitEmployee">
          {{ editingEmployeeId ? '保存' : '追加' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
