<script setup lang="ts">
// 見積書：状態（下書き→提出済み→受注／失注、取消）は見積書だけのもの。契約書・請求書は内容を写して別に作る。
import { onMounted, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import BusinessDocumentDialog from '../../components/vouchers/BusinessDocumentDialog.vue'
import VoucherStatusActions from '../../components/vouchers/VoucherStatusActions.vue'
import { useDocumentList } from '../../components/vouchers/useDocumentList'
import { listEstimates } from '../../api/accounting'
import { useAuthStore } from '../../stores/auth'
import type { Estimate } from '../../types/accounting'
import { formatDate } from '../../utils/date'
import { formatYen } from '../../utils/voucherCalc'
import '../accounting/accounting.css'

const auth = useAuthStore()
const list = useDocumentList<Estimate>('estimates', '見積書', listEstimates)
const { rows, total, page, loading, errorMessage, filters } = list
const dialogVisible = ref(false)
const editing = ref<Estimate | null>(null)

const STATUS_OPTIONS = [
  { value: 'draft', label: '下書き' }, { value: 'submitted', label: '提出済み' }, { value: 'accepted', label: '受注' },
  { value: 'declined', label: '失注' }, { value: 'cancelled', label: '取消' },
]

const openCreate = () => { editing.value = null; dialogVisible.value = true }
const openEdit = (row: Estimate) => { editing.value = row; dialogVisible.value = true }

const onCommand = (row: Estimate, command: string) => {
  if (command === 'edit') openEdit(row)
  else if (command === 'pdf') list.downloadPdf(row.id, false)
  else if (command === 'pdf-seal') list.downloadPdf(row.id, true)
  else if (command === 'contract') list.createFrom(row.id, 'create-contract')
  else if (command === 'invoice') list.createFrom(row.id, 'create-invoice')
  else if (command === 'delete') list.remove(row.id, row.estimate_number)
}

onMounted(() => list.fetch(1))
</script>

<template>
  <section class="accounting-page">
    <div class="accounting-hero">
      <div class="page-header-row">
        <div>
          <h1>見積書</h1>
          <p>見積書を作成し、提出・受注などの状態を管理します。受注しても契約書・請求書は自動では作られません。</p>
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
        <el-input v-model="filters.keyword" clearable placeholder="番号・宛先・件名" class="accounting-filter-search" @keyup.enter="list.fetch(1)" />
        <div class="accounting-filter-actions">
          <el-button type="primary" @click="list.fetch(1)">検索</el-button>
          <el-button @click="list.resetFilters">リセット</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="accounting-card" shadow="never">
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="estimate_number" label="見積番号" width="170" />
        <el-table-column label="発行日" width="110"><template #default="{ row }">{{ formatDate(row.issue_date) }}</template></el-table-column>
        <el-table-column label="宛先" min-width="160"><template #default="{ row }">{{ row.recipient_name || '-' }}</template></el-table-column>
        <el-table-column prop="title" label="件名" min-width="180" show-overflow-tooltip />
        <el-table-column label="金額（税込）" width="130" align="right"><template #default="{ row }">{{ formatYen(row.total_amount) }}</template></el-table-column>
        <el-table-column label="有効期限" width="110"><template #default="{ row }">{{ row.valid_until ? formatDate(row.valid_until) : '-' }}</template></el-table-column>
        <el-table-column label="状態" width="150">
          <template #default="{ row }"><VoucherStatusActions endpoint="estimates" :doc="row" @changed="list.fetch()" /></template>
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
                  <el-dropdown-item v-if="auth.can('accounting.use_contract')" command="contract" divided>契約書を作成</el-dropdown-item>
                  <el-dropdown-item v-if="auth.can('accounting.use_voucher')" command="invoice">請求書を作成</el-dropdown-item>
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

    <BusinessDocumentDialog v-model:visible="dialogVisible" kind="estimate" :doc="editing" @saved="list.fetch()" />
  </section>
</template>
