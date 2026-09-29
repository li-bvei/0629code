<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Briefcase,
  Coin,
  DataAnalysis,
  Document,
  EditPen,
  Expand,
  Fold,
  Files,
  List,
  Menu,
  OfficeBuilding,
  Money,
  Notebook,
  Reading,
  Setting,
  Tickets,
  Upload,
  User,
  Van,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isSidebarOpen = ref(false)
const isSidebarCollapsed = ref(localStorage.getItem('sidebarCollapsed') === '1')

const activeMenu = computed(() => route.path)

const closeSidebar = () => {
  isSidebarOpen.value = false
}

const toggleSidebarCollapsed = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
  localStorage.setItem('sidebarCollapsed', isSidebarCollapsed.value ? '1' : '0')
}

const handleLogout = async () => {
  try {
    await auth.logout()
    router.push('/login')
  } catch {
    ElMessage.error('ログアウトに失敗しました')
  }
}
</script>

<template>
  <div class="admin-layout">
    <aside class="sidebar" :class="{ 'is-open': isSidebarOpen, 'is-collapsed': isSidebarCollapsed }">
      <div class="sidebar-brand">
        <div class="brand-mark">S</div>
        <div v-if="!isSidebarCollapsed">
          <div class="brand-name">SUNRISE</div>
        </div>
        <button class="collapse-toggle" type="button" aria-label="サイドバー折りたたみ" @click="toggleSidebarCollapsed">
          <el-icon><Fold v-if="!isSidebarCollapsed" /><Expand v-else /></el-icon>
        </button>
      </div>

      <el-menu
        class="sidebar-menu"
        :default-active="activeMenu"
        :collapse="isSidebarCollapsed"
        router
        @select="closeSidebar"
      >
        <el-sub-menu v-if="auth.can('cases.use_cases')" index="cases">
          <template #title>
            <el-icon><Briefcase /></el-icon>
            <span>案件業務</span>
          </template>
          <el-menu-item index="/dashboard">
            <el-icon><DataAnalysis /></el-icon>
            <span>ダッシュボード</span>
          </el-menu-item>
          <el-menu-item index="/workbench">
            <el-icon><List /></el-icon>
            <span>今日の作業台</span>
          </el-menu-item>
          <el-menu-item index="/reception/new">
            <el-icon><EditPen /></el-icon>
            <span>新規受付</span>
          </el-menu-item>
          <el-menu-item index="/cases">
            <el-icon><Tickets /></el-icon>
            <span>案件一覧</span>
          </el-menu-item>
          <el-menu-item index="/customers">
            <el-icon><User /></el-icon>
            <span>顧客管理</span>
          </el-menu-item>
          <el-menu-item index="/companies">
            <el-icon><OfficeBuilding /></el-icon>
            <span>会社管理</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="auth.can('accounting.use_expense')" index="accounting">
          <template #title>
            <el-icon><Coin /></el-icon>
            <span>会計管理</span>
          </template>
          <el-menu-item index="/accounting">
            <el-icon><DataAnalysis /></el-icon>
            <span>会計ダッシュボード</span>
          </el-menu-item>
          <el-menu-item index="/accounting/expenses">
            <el-icon><Money /></el-icon>
            <span>支出記録</span>
          </el-menu-item>
          <el-menu-item index="/accounting/expense-categories">
            <el-icon><List /></el-icon>
            <span>支出カテゴリ</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_income')" index="/accounting/income-sources">
            <el-icon><Coin /></el-icon>
            <span>収入元</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_vehicle')" index="/accounting/vehicle-usages">
            <el-icon><Van /></el-icon>
            <span>車両使用記録</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_project')" index="/accounting/projects">
            <el-icon><Notebook /></el-icon>
            <span>プロジェクト収支表</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="auth.canAny('accounting.use_voucher', 'accounting.use_estimate', 'accounting.use_contract', 'accounting.use_visa', 'accounting.use_tax_renewal', 'accounting.use_seifu')" index="vouchers">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>帳票管理</span>
          </template>
          <el-menu-item v-if="auth.can('accounting.use_voucher')" index="/vouchers/invoices">
            <el-icon><Document /></el-icon>
            <span>請求書・領収書</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_visa')" index="/vouchers/visa-return">
            <el-icon><Files /></el-icon>
            <span>返签 visa 表</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_tax_renewal')" index="/vouchers/tax-renewal">
            <el-icon><Reading /></el-icon>
            <span>税务证明更新用</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_seifu')" index="/vouchers/seifu-notice">
            <el-icon><Document /></el-icon>
            <span>清風合格通知書</span>
            <el-tag size="small" type="info">暂停</el-tag>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_estimate')" index="/vouchers/estimates">
            <el-icon><Document /></el-icon>
            <span>見積書</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_contract')" index="/vouchers/contracts">
            <el-icon><Document /></el-icon>
            <span>契約書</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_voucher')" index="/vouchers/certificates">
            <el-icon><Document /></el-icon>
            <span>証明書</span>
            <el-tag size="small" type="info">準備中</el-tag>
          </el-menu-item>
          <el-menu-item v-if="auth.can('accounting.use_voucher')" index="/vouchers/others">
            <el-icon><Document /></el-icon>
            <span>その他帳票</span>
            <el-tag size="small" type="info">準備中</el-tag>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu v-if="auth.canAny('real_estate.use_real_estate', 'real_estate.real_estate_view_all', 'real_estate.real_estate_change_all')" index="real-estate">
          <template #title>
            <el-icon><OfficeBuilding /></el-icon>
            <span>不動産</span>
          </template>
          <el-menu-item index="/real-estate">
            <el-icon><OfficeBuilding /></el-icon>
            <span>取引一覧</span>
          </el-menu-item>
          <el-menu-item v-if="auth.can('real_estate.real_estate_change_all')" index="/real-estate/import">
            <el-icon><Upload /></el-icon>
            <span>LIST 取込（dry-run）</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>システム</span>
          </template>
          <el-menu-item v-if="auth.can('cases.use_cases')" index="/case-checklists">
            <el-icon><List /></el-icon>
            <span>案件・担当設定管理</span>
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            <span>設定</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </aside>

    <div class="mobile-mask" :class="{ 'is-open': isSidebarOpen }" @click="closeSidebar" />

    <section class="workspace">
      <header class="topbar">
        <button class="menu-button" type="button" aria-label="メニュー" @click="isSidebarOpen = true">
          <el-icon><Menu /></el-icon>
        </button>
        <div>
          <div class="topbar-title">バックオフィス</div>
          <div class="topbar-subtitle">案件を中心に日々の業務を管理します</div>
        </div>
        <div class="topbar-spacer" />
        <div class="topbar-user">
          <span>{{ auth.user?.last_name || auth.user?.username }}</span>
          <el-button text type="primary" @click="handleLogout">ログアウト</el-button>
        </div>
      </header>

      <main class="main-content">
        <router-view />
      </main>
    </section>
  </div>
</template>
