<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Briefcase,
  Calendar,
  Coin,
  DataAnalysis,
  Document,
  EditPen,
  Expand,
  Fold,
  FolderOpened,
  Files,
  List,
  Menu,
  OfficeBuilding,
  Money,
  Notebook,
  Reading,
  Setting,
  Tickets,
  User,
  Van,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { NAVIGATION, filterNavigation, isGroup, type NavIcon, type NavItem } from '../utils/navigation'
import GlobalSearch from '../components/GlobalSearch.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isSidebarOpen = ref(false)
const isSidebarCollapsed = ref(localStorage.getItem('sidebarCollapsed') === '1')

const activeMenu = computed(() => route.path)
const navigation = computed(() => filterNavigation(NAVIGATION, auth.can))
const icons: Record<NavIcon, unknown> = {
  Calendar, Notebook, DataAnalysis, Briefcase, Tickets, EditPen, User, OfficeBuilding, FolderOpened, Coin, Money, List,
  Van, Files, Document, Reading, Setting,
}

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
        <!-- 構成は utils/navigation.ts（権限で絞り込み済み）。同じ画面への入口は 1 つだけ -->
        <el-sub-menu v-for="group in navigation" :key="group.key" :index="group.key">
          <template #title>
            <el-icon><component :is="icons[group.icon]" /></el-icon>
            <span>{{ group.label }}</span>
          </template>
          <template v-for="entry in group.children" :key="isGroup(entry) ? entry.key : entry.path">
            <el-sub-menu v-if="isGroup(entry)" :index="entry.key">
              <template #title>
                <el-icon><component :is="icons[entry.icon]" /></el-icon>
                <span>{{ entry.label }}</span>
              </template>
              <el-menu-item v-for="item in entry.children as NavItem[]" :key="item.path" :index="item.path">
                <el-icon><component :is="icons[item.icon]" /></el-icon>
                <span>{{ item.label }}</span>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="entry.path">
              <el-icon><component :is="icons[entry.icon]" /></el-icon>
              <span>{{ entry.label }}</span>
              <el-tag v-if="entry.tag" size="small" type="info">{{ entry.tag }}</el-tag>
            </el-menu-item>
          </template>
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
        <GlobalSearch class="topbar-search" />
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
