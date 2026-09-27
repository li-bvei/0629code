import http from '../services/http'

export interface AuthUser {
  id: number
  username: string
  first_name?: string
  last_name?: string
  is_staff: boolean
  is_superuser: boolean
  is_protected?: boolean
  groups: string[]
  permissions: string[]
  // 表示制御専用（安全の根拠ではない。判定は常に後端の BusinessAccessPolicy）。
  business_permissions?: string[]
  employee_id?: number | null
  employee_name?: string
  dev_tools_enabled?: boolean
}

export const getCsrf = async () => {
  const response = await http.get<{ detail: string }>('/auth/csrf/')
  return response.data
}

export const login = async (username: string, password: string) => {
  const response = await http.post<AuthUser>('/auth/login/', { username, password })
  return response.data
}

export const logout = async () => {
  const response = await http.post<{ detail: string }>('/auth/logout/')
  return response.data
}

export const getMe = async () => {
  const response = await http.get<AuthUser>('/auth/me/')
  return response.data
}
