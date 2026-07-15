<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createCustomer,
  deleteCustomer,
  listCustomers,
  updateCustomer,
} from '../api/customers'
import { residenceStatusOptions } from '../constants/options'
import type { CreateCustomerPayload, Customer } from '../types/api'
import { formatDate, formatDateTime } from '../utils/date'

const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const customers = ref<Customer[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const searchKeyword = ref('')
const residenceStatusFilter = ref('')
const dialogVisible = ref(false)
const editingCustomerId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const customerForm = ref<CreateCustomerPayload>({
  name: '',
  name_kana: '',
  birth_date: '',
  gender: '',
  nationality: '',
  residence_status: '',
  residence_card_no: '',
  residence_expiry: null,
  passport_no: '',
  passport_expiry: null,
  email: '',
  phone: '',
  postal_code: '',
  address: '',
  my_number: '',
  note: '',
})

const rules: FormRules<CreateCustomerPayload> = {
  name: [{ required: true, message: '氏名を入力してください。', trigger: 'blur' }],
  birth_date: [{ required: true, message: '生年月日を入力してください。', trigger: 'change' }],
}

const fetchCustomers = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const keyword = searchKeyword.value.trim()
    const data = await listCustomers({
      page,
      search: keyword || undefined,
      residence_status: residenceStatusFilter.value || undefined,
    })
    customers.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = 'データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchCustomers()
})

const searchCustomers = () => {
  fetchCustomers(1)
}

const clearSearch = () => {
  searchKeyword.value = ''
  residenceStatusFilter.value = ''
  fetchCustomers(1)
}

const resetForm = () => {
  editingCustomerId.value = null
  customerForm.value = {
    name: '',
    name_kana: '',
    birth_date: '',
    gender: '',
    nationality: '',
    residence_status: '',
    residence_card_no: '',
    residence_expiry: null,
    passport_no: '',
    passport_expiry: null,
    email: '',
    phone: '',
    postal_code: '',
    address: '',
    my_number: '',
    note: '',
  }
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (customer: Customer) => {
  editingCustomerId.value = customer.id
  customerForm.value = {
    name: customer.name,
    name_kana: customer.name_kana,
    birth_date: customer.birth_date,
    gender: customer.gender,
    nationality: customer.nationality,
    residence_status: customer.residence_status,
    residence_card_no: customer.residence_card_no,
    residence_expiry: customer.residence_expiry,
    passport_no: customer.passport_no,
    passport_expiry: customer.passport_expiry,
    email: customer.email,
    phone: customer.phone,
    postal_code: customer.postal_code,
    address: customer.address,
    my_number: customer.my_number,
    note: customer.note,
  }
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

const submitCustomer = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingCustomerId.value) {
      await updateCustomer(editingCustomerId.value, customerForm.value)
      ElMessage.success('顧客を更新しました。')
    } else {
      await createCustomer(customerForm.value)
      ElMessage.success('顧客を作成しました。')
    }
    dialogVisible.value = false
    await fetchCustomers(editingCustomerId.value ? currentPage.value : 1)
  } catch {
    errorMessage.value = editingCustomerId.value
      ? '顧客の更新に失敗しました。'
      : '顧客の作成に失敗しました。'
  } finally {
    submitting.value = false
  }
}

const confirmDeleteCustomer = async (customer: Customer) => {
  try {
    await ElMessageBox.confirm(
      `「${customer.name}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteCustomer(customer.id)
    ElMessage.success('顧客を削除しました。')
    await fetchCustomers(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      errorMessage.value = '顧客の削除に失敗しました。'
    }
  }
}
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>顧客管理</h1>
      <el-button type="primary" @click="openCreateDialog">新規顧客</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never" class="search-card">
      <div class="search-row">
        <el-input
          v-model="searchKeyword"
          placeholder="氏名・電話・メールで検索"
          clearable
          @keyup.enter="searchCustomers"
        />
        <el-select
          v-model="residenceStatusFilter"
          clearable
          placeholder="在留資格"
          class="search-select"
        >
          <el-option
            v-for="status in residenceStatusOptions"
            :key="status"
            :label="status"
            :value="status"
          />
        </el-select>
        <el-button type="primary" @click="searchCustomers">検索</el-button>
        <el-button @click="clearSearch">クリア</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="customers" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="氏名" min-width="160">
          <template #default="{ row }">
            <router-link class="text-link" :to="`/customers/${row.id}`">{{ row.name }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="生年月日" width="130">
          <template #default="{ row }">{{ formatDate(row.birth_date) }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="電話番号" min-width="140" />
        <el-table-column prop="email" label="メール" min-width="180" />
        <el-table-column prop="address" label="住所" min-width="220" show-overflow-tooltip />
        <el-table-column prop="cases_count" label="案件数" width="100" />
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
                  <el-dropdown-item divided class="danger-item" @click="confirmDeleteCustomer(row)">削除</el-dropdown-item>
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
          @current-change="fetchCustomers"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingCustomerId ? '顧客編集' : '新規顧客'"
      width="520px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="customerForm" :rules="rules" label-position="top">
        <el-form-item label="フリガナ" prop="name_kana">
          <el-input v-model="customerForm.name_kana" />
        </el-form-item>
        <el-form-item label="氏名" prop="name">
          <el-input v-model="customerForm.name" />
        </el-form-item>
        <el-form-item label="生年月日" prop="birth_date">
          <el-date-picker
            v-model="customerForm.birth_date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="YYYY-MM-DD"
            class="form-control"
          />
        </el-form-item>
        <el-form-item label="国籍" prop="nationality">
          <el-input v-model="customerForm.nationality" />
        </el-form-item>
        <el-form-item label="在留資格" prop="residence_status">
          <el-select
            v-model="customerForm.residence_status"
            clearable
            filterable
            allow-create
            default-first-option
            placeholder="選択してください"
            class="form-control"
          >
            <el-option
              v-for="status in residenceStatusOptions"
              :key="status"
              :label="status"
              :value="status"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="在留カード番号" prop="residence_card_no">
          <el-input v-model="customerForm.residence_card_no" />
        </el-form-item>
        <el-form-item label="在留期限" prop="residence_expiry">
          <el-date-picker
            v-model="customerForm.residence_expiry"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="YYYY-MM-DD"
            class="form-control"
          />
        </el-form-item>
        <el-form-item label="パスポート番号" prop="passport_no">
          <el-input v-model="customerForm.passport_no" />
        </el-form-item>
        <el-form-item label="パスポート期限" prop="passport_expiry">
          <el-date-picker
            v-model="customerForm.passport_expiry"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="YYYY-MM-DD"
            class="form-control"
          />
        </el-form-item>
        <el-form-item label="メール" prop="email">
          <el-input v-model="customerForm.email" />
        </el-form-item>
        <el-form-item label="電話番号" prop="phone">
          <el-input v-model="customerForm.phone" />
        </el-form-item>
        <el-form-item label="郵便番号" prop="postal_code" class="form-grid-start">
          <el-input v-model="customerForm.postal_code" />
        </el-form-item>
        <el-form-item label="住所" prop="address" class="form-grid-full">
          <el-input v-model="customerForm.address" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="マイナンバー" prop="my_number">
          <el-input v-model="customerForm.my_number" />
        </el-form-item>
        <el-form-item label="備考" prop="note">
          <el-input v-model="customerForm.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCustomer">
          {{ editingCustomerId ? '保存' : '作成' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
