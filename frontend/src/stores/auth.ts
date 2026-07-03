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
    fetchMe,
    login,
    logout,
  }
})
