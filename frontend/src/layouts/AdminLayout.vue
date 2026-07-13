<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Briefcase,
  CirclePlus,
  Document,
  Menu,
  OfficeBuilding,
  Setting,
  User,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isSidebarOpen = ref(false)

const activeMenu = computed(() => route.path)

const closeSidebar = () => {
  isSidebarOpen.value = false
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
    <aside class="sidebar" :class="{ 'is-open': isSidebarOpen }">
      <div class="sidebar-brand">
        <div class="brand-mark">S</div>
        <div>
          <div class="brand-name">SUNRISE</div>
        </div>
      </div>

      <el-menu
        class="sidebar-menu"
        :default-active="activeMenu"
        router
        @select="closeSidebar"
      >
        <el-sub-menu index="cases">
          <template #title>
            <el-icon><Briefcase /></el-icon>
            <span>案件業務</span>
          </template>
          <el-menu-item index="/dashboard">ダッシュボード</el-menu-item>
          <el-menu-item index="/reception/new">
            <el-icon><CirclePlus /></el-icon>
            <span>新規受付</span>
          </el-menu-item>
          <el-menu-item index="/cases">案件一覧</el-menu-item>
          <el-menu-item index="/customers">
            <el-icon><User /></el-icon>
            <span>顧客管理</span>
          </el-menu-item>
          <el-menu-item index="/companies">
            <el-icon><OfficeBuilding /></el-icon>
            <span>会社管理</span>
          </el-menu-item>
          <el-menu-item index="/employees">担当者管理</el-menu-item>
          <el-menu-item index="/tasks">タスク一覧</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="accounting">
          <template #title>
            <span>会計管理</span>
          </template>
          <el-menu-item index="/accounting">会計ダッシュボード</el-menu-item>
          <el-menu-item index="/accounting/expenses">支出記録</el-menu-item>
          <el-menu-item index="/accounting/expense-categories">支出カテゴリ</el-menu-item>
          <el-menu-item index="/accounting/income-sources">収入元</el-menu-item>
          <el-menu-item index="/accounting/vehicle-usages">車両使用記録</el-menu-item>
          <el-menu-item index="/accounting/projects">プロジェクト収支表</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="vouchers">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>帳票管理</span>
          </template>
          <el-menu-item index="/vouchers/invoices">請求書・領収書</el-menu-item>
          <el-menu-item index="/vouchers/visa-return">返签 visa 表</el-menu-item>
          <el-menu-item index="/vouchers/tax-renewal">税务证明更新用</el-menu-item>
          <el-menu-item index="/vouchers/seifu-notice">
            <span>清風合格通知書</span>
            <el-tag size="small" type="info">暂停</el-tag>
          </el-menu-item>
          <el-menu-item index="/vouchers/estimates">
            <span>見積書</span>
            <el-tag size="small" type="info">準備中</el-tag>
          </el-menu-item>
          <el-menu-item index="/vouchers/contracts">
            <span>契約書</span>
            <el-tag size="small" type="info">準備中</el-tag>
          </el-menu-item>
          <el-menu-item index="/vouchers/certificates">
            <span>証明書</span>
            <el-tag size="small" type="info">準備中</el-tag>
          </el-menu-item>
          <el-menu-item index="/vouchers/others">
            <span>その他帳票</span>
            <el-tag size="small" type="info">準備中</el-tag>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>システム</span>
          </template>
          <el-menu-item index="/settings">設定</el-menu-item>
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
