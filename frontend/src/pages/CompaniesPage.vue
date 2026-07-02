<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createCompany,
  deleteCompany,
  listCompanies,
  updateCompany,
} from '../api/companies'
import { listCustomers } from '../api/customers'
import { bankAccountTypeOptions, fiscalMonthOptions } from '../constants/options'
import type { Company, CreateCompanyPayload, Customer } from '../types/api'
import { formatDateTime } from '../utils/date'

const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref('')
const companies = ref<Company[]>([])
const customers = ref<Customer[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const dialogVisible = ref(false)
const editingCompanyId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const companyForm = ref<CreateCompanyPayload>({
  name: '',
  name_kana: '',
  representative_customer: null,
  representative_name: '',
  representative_name_kana: '',
  corporate_number: '',
  email: '',
  phone: '',
  postal_code: '',
  address: '',
  fiscal_month: '',
  bank_name: '',
  bank_branch: '',
  bank_account_type: '',
  bank_account_number: '',
})

const rules: FormRules<CreateCompanyPayload> = {
  name: [{ required: true, message: '会社名を入力してください。', trigger: 'blur' }],
}

const getCorporateRegistrationNumber = (corporateNumber?: string) => {
  if (corporateNumber && /^\d{13}$/.test(corporateNumber)) {
    return corporateNumber.slice(1)
  }
  return '自動生成'
}

const fetchCompanies = async (page = currentPage.value) => {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await listCompanies({ page })
    companies.value = data.results
    total.value = data.count
    currentPage.value = page
  } catch {
    errorMessage.value = 'データの取得に失敗しました。'
  } finally {
    loading.value = false
  }
}

const fetchCustomers = async () => {
  try {
    const data = await listCustomers()
    customers.value = data.results
  } catch {
    ElMessage.error('顧客一覧の取得に失敗しました。')
  }
}

onMounted(() => {
  fetchCompanies()
  fetchCustomers()
})

const resetForm = () => {
  editingCompanyId.value = null
  companyForm.value = {
    name: '',
    name_kana: '',
    representative_customer: null,
    representative_name: '',
    representative_name_kana: '',
    corporate_number: '',
    email: '',
    phone: '',
    postal_code: '',
    address: '',
    fiscal_month: '',
    bank_name: '',
    bank_branch: '',
    bank_account_type: '',
    bank_account_number: '',
  }
  formRef.value?.clearValidate()
}

const openCreateDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (company: Company) => {
  editingCompanyId.value = company.id
  companyForm.value = {
    name: company.name,
    name_kana: company.name_kana,
    representative_customer: company.representative_customer,
    representative_name: company.representative_name,
    representative_name_kana: company.representative_name_kana,
    corporate_number: company.corporate_number,
    email: company.email,
    phone: company.phone,
    postal_code: company.postal_code,
    address: company.address,
    fiscal_month: company.fiscal_month,
    bank_name: company.bank_name,
    bank_branch: company.bank_branch,
    bank_account_type: company.bank_account_type,
    bank_account_number: company.bank_account_number,
  }
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

const submitCompany = async () => {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingCompanyId.value) {
      await updateCompany(editingCompanyId.value, companyForm.value)
      ElMessage.success('会社を更新しました。')
    } else {
      await createCompany(companyForm.value)
      ElMessage.success('会社を作成しました。')
    }
    dialogVisible.value = false
    await fetchCompanies(editingCompanyId.value ? currentPage.value : 1)
  } catch {
    ElMessage.error(editingCompanyId.value ? '会社の更新に失敗しました。' : '会社の作成に失敗しました。')
  } finally {
    submitting.value = false
  }
}

const confirmDeleteCompany = async (company: Company) => {
  try {
    await ElMessageBox.confirm(
      `「${company.name}」を削除します。よろしいですか？`,
      '削除確認',
      {
        confirmButtonText: '削除',
        cancelButtonText: 'キャンセル',
        type: 'warning',
      },
    )
    await deleteCompany(company.id)
    ElMessage.success('会社を削除しました。')
    await fetchCompanies(currentPage.value)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('会社の削除に失敗しました。')
    }
  }
}
</script>

<template>
  <section class="page">
    <div class="page-header page-header-row">
      <h1>会社管理</h1>
      <el-button type="primary" @click="openCreateDialog">新規会社</el-button>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card shadow="never">
      <el-table v-loading="loading" :data="companies" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="会社名" min-width="180">
          <template #default="{ row }">
            <router-link class="text-link" :to="`/companies/${row.id}`">{{ row.name }}</router-link>
          </template>
        </el-table-column>
        <el-table-column prop="name_kana" label="会社名フリガナ" min-width="180" />
        <el-table-column prop="corporate_number" label="法人番号" min-width="150" />
        <el-table-column prop="corporate_registration_number" label="会社法人等番号" min-width="150" />
        <el-table-column prop="phone" label="電話番号" min-width="140" />
        <el-table-column prop="email" label="メール" min-width="180" />
        <el-table-column prop="postal_code" label="郵便番号" width="120" />
        <el-table-column prop="address" label="住所" min-width="220" show-overflow-tooltip />
        <el-table-column prop="cases_count" label="案件数" width="100" />
        <el-table-column label="更新日時" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEditDialog(row)">編集</el-button>
            <el-button text type="danger" @click="confirmDeleteCompany(row)">削除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination
          layout="prev, pager, next"
          :current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          @current-change="fetchCompanies"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingCompanyId ? '会社編集' : '新規会社'"
      width="520px"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="companyForm" :rules="rules" label-position="top">
        <el-form-item label="会社名フリガナ" prop="name_kana">
          <el-input v-model="companyForm.name_kana" />
        </el-form-item>
        <el-form-item label="会社名" prop="name">
          <el-input v-model="companyForm.name" />
        </el-form-item>
        <el-form-item label="代表者顧客" prop="representative_customer">
          <el-select
            v-model="companyForm.representative_customer"
            clearable
            placeholder="未設定"
            class="form-control"
          >
            <el-option
              v-for="customer in customers"
              :key="customer.id"
              :label="customer.name"
              :value="customer.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="代表者フリガナ" prop="representative_name_kana">
          <el-input v-model="companyForm.representative_name_kana" />
        </el-form-item>
        <el-form-item label="代表者氏名" prop="representative_name">
          <el-input v-model="companyForm.representative_name" />
        </el-form-item>
        <el-form-item label="法人番号" prop="corporate_number">
          <el-input v-model="companyForm.corporate_number" />
        </el-form-item>
        <el-form-item label="会社法人等番号">
          <el-input :model-value="getCorporateRegistrationNumber(companyForm.corporate_number)" disabled />
        </el-form-item>
        <el-form-item label="メール" prop="email">
          <el-input v-model="companyForm.email" />
        </el-form-item>
        <el-form-item label="電話番号" prop="phone">
          <el-input v-model="companyForm.phone" />
        </el-form-item>
        <el-form-item label="郵便番号" prop="postal_code" class="form-grid-start">
          <el-input v-model="companyForm.postal_code" />
        </el-form-item>
        <el-form-item label="住所" prop="address" class="form-grid-full">
          <el-input v-model="companyForm.address" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="決算月" prop="fiscal_month">
          <el-select v-model="companyForm.fiscal_month" clearable placeholder="選択してください" class="form-control">
            <el-option
              v-for="month in fiscalMonthOptions"
              :key="month"
              :label="`${month}月`"
              :value="month"
            />
          </el-select>
        </el-form-item>
        <div class="form-section-title">銀行情報</div>
        <el-form-item label="銀行名" prop="bank_name">
          <el-input v-model="companyForm.bank_name" />
        </el-form-item>
        <el-form-item label="支店名" prop="bank_branch">
          <el-input v-model="companyForm.bank_branch" />
        </el-form-item>
        <el-form-item label="預金種別" prop="bank_account_type">
          <el-select v-model="companyForm.bank_account_type" clearable placeholder="選択してください" class="form-control">
            <el-option
              v-for="type in bankAccountTypeOptions"
              :key="type"
              :label="type"
              :value="type"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="口座番号" prop="bank_account_number">
          <el-input v-model="companyForm.bank_account_number" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">キャンセル</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCompany">
          {{ editingCompanyId ? '保存' : '作成' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>
