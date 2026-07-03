import http from '../services/http'

export interface AuthUser {
  id: number
  username: string
  first_name?: string
  last_name?: string
  is_staff: boolean
  is_superuser: boolean
  groups: string[]
  permissions: string[]
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
