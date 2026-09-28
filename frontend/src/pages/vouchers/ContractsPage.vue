<script setup lang="ts">
// 契約書：状態（下書き→送付済み→締結済み→終了、取消）は契約書だけのもの。請求書は内容を写して別に作る。
import { onMounted, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import BusinessDocumentDialog from '../../components/vouchers/BusinessDocumentDialog.vue'
import VoucherStatusActions from '../../components/vouchers/VoucherStatusActions.vue'
import { useDocumentList } from '../../components/vouchers/useDocumentList'
import { listContracts } from '../../api/accounting'
import { useAuthStore } from '../../stores/auth'
import type { Contract } from '../../types/accounting'
import { formatDate } from '../../utils/date'
import { formatYen } from '../../utils/voucherCalc'
import '../accounting/accounting.css'

const auth = useAuthStore()
const list = useDocumentList<Contract>('contracts', '契約書', listContracts)
const { rows, total, page, loading, errorMessage, filters } = list
const dialogVisible = ref(false)
const editing = ref<Contract | null>(null)

const STATUS_OPTIONS = [
  { value: 'draft', label: '下書き' }, { value: 'sent', label: '送付済み' }, { value: 'signed', label: '締結済み' },
  { value: 'terminated', label: '終了' }, { value: 'cancelled', label: '取消' },
]

const openCreate = () => { editing.value = null; dialogVisible.value = true }
const openEdit = (row: Contract) => { editing.value = row; dialogVisible.value = true }
const period = (row: Contract) =>
  row.start_date || row.end_date ? `${row.start_date ? formatDate(row.start_date) : ''} 〜 ${row.end_date ? formatDate(row.end_date) : ''}` : '-'

const onCommand = (row: Contract, command: string) => {
  if (command === 'edit') openEdit(row)
  else if (command === 'pdf') list.downloadPdf(row.id, false)
  else if (command === 'pdf-seal') list.downloadPdf(row.id, true)
  else if (command === 'invoice') list.createFrom(row.id, 'create-invoice')
  else if (command === 'delete') list.remove(row.id, row.contract_number)
}

onMounted(() => list.fetch(1))
</script>

<template>
  <section class="accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>契約書</h1>
          <p>契約書を作成し、送付・締結・終了の状態を管理します。締結しても請求書は自動では作られません。</p>
        </div>
        <div class="accounting-toolbar">
          <el-button type="primary" @click="openCreate">新規作成</el-button>
        </div>
      </div>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon class="page-alert" />

    <el-card class="accounting-filter-card" shadow="never">
      <div class="accounting-filter-row">
        <el-select v-model="filters.status" clearable placeholder="状態" class="accounting-filter-select">
          <el-option v-for="o in STATUS_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-date-picker v-model="filters.issue_date_from" type="date" value-format="YYYY-MM-DD" placeholder="発行日 From" class="accounting-filter-date" />
        <el-date-picker v-model="filters.issue_date_to" type="date" value-format="YYYY-MM-DD" placeholder="発行日 To" class="accounting-filter-date" />
        <el-input v-model="filters.keyword" clearable placeholder="番号・委託者・件名" class="accounting-filter-search" @keyup.enter="list.fetch(1)" />
        <div class="accounting-filter-actions">
          <el-button type="primary" @click="list.fetch(1)">検索</el-button>
          <el-button @click="list.resetFilters">リセット</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="accounting-card" shadow="never">
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="contract_number" label="契約番号" width="170" />
        <el-table-column label="発行日" width="110"><template #default="{ row }">{{ formatDate(row.issue_date) }}</template></el-table-column>
        <el-table-column label="委託者（甲）" min-width="150"><template #default="{ row }">{{ row.recipient_name || '-' }}</template></el-table-column>
        <el-table-column prop="title" label="件名" min-width="160" show-overflow-tooltip />
        <el-table-column label="報酬（税込）" width="130" align="right"><template #default="{ row }">{{ formatYen(row.total_amount) }}</template></el-table-column>
        <el-table-column label="契約期間" width="210"><template #default="{ row }">{{ period(row) }}</template></el-table-column>
        <el-table-column label="状態" width="150">
          <template #default="{ row }">
            <VoucherStatusActions endpoint="contracts" :doc="row" @changed="list.fetch()" />
            <div v-if="row.signed_date" class="sub">締結日 {{ formatDate(row.signed_date) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="元の見積書" width="160">
          <template #default="{ row }">
            <router-link v-if="row.source_estimate_number" class="text-link"
                         :to="{ path: '/vouchers/estimates', query: { keyword: row.source_estimate_number } }">{{ row.source_estimate_number }}</router-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="関連案件" width="140">
          <template #default="{ row }">
            <router-link v-if="row.case" class="text-link" :to="`/cases/${row.case}`">{{ row.case_number }}</router-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown trigger="click" @command="onCommand(row, $event)">
              <el-button text type="primary">操作<el-icon><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">{{ row.is_editable ? '編集' : '表示・備考' }}</el-dropdown-item>
                  <el-dropdown-item command="pdf">PDF（印章なし）</el-dropdown-item>
                  <el-dropdown-item command="pdf-seal">PDF（印章あり）</el-dropdown-item>
                  <el-dropdown-item v-if="auth.can('accounting.use_voucher')" command="invoice" divided>請求書を作成</el-dropdown-item>
                  <el-dropdown-item v-if="row.is_editable" command="delete" divided class="danger-item">削除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <el-pagination layout="prev, pager, next" :current-page="page" :page-size="20" :total="total" @current-change="list.fetch" />
      </div>
    </el-card>

    <BusinessDocumentDialog v-model:visible="dialogVisible" kind="contract" :doc="editing" @saved="list.fetch()" />
  </section>
</template>

<style scoped>
.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
