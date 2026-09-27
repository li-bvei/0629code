import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getCsrf,
  getMe,
  login as loginRequest,
  logout as logoutRequest,
  type AuthUser,
} from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const loading = ref(false)
  const isAuthenticated = computed(() => Boolean(user.value))
  const businessPermissions = computed(() => new Set(user.value?.business_permissions ?? []))
  // 画面の表示・非表示にのみ使う。権限の実際の判定は後端で行われる。
  const can = (code: string) => businessPermissions.value.has(code)
  const canAny = (...codes: string[]) => codes.some((code) => businessPermissions.value.has(code))
  const devToolsEnabled = computed(() => Boolean(user.value?.dev_tools_enabled))
  const canManageUsers = computed(() => Boolean(user.value?.is_superuser) && can('authentication.manage_users'))

  const fetchMe = async () => {
    loading.value = true

    try {
      user.value = await getMe()
      return user.value
    } catch (error) {
      user.value = null
      throw error
    } finally {
      loading.value = false
    }
  }

  const login = async (username: string, password: string) => {
    loading.value = true

    try {
      await getCsrf()
      user.value = await loginRequest(username, password)
      return user.value
    } finally {
      loading.value = false
    }
  }

  const logout = async () => {
    loading.value = true

    try {
      await getCsrf()
      await logoutRequest()
    } finally {
      user.value = null
      loading.value = false
    }
  }

  return {
    user,
    loading,
    isAuthenticated,
    can,
    canAny,
    devToolsEnabled,
    canManageUsers,
    fetchMe,
    login,
    logout,
  }
})
