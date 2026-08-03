import http from '../services/http'
import type { ListParams, PaginatedResponse, SystemUser, SystemUserCreatePayload } from '../types/api'

export const listUsers = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<SystemUser>>('/users/', { params })
  return response.data
}

export const createUser = async (payload: SystemUserCreatePayload) => {
  const response = await http.post<SystemUser>('/users/', payload)
  return response.data
}

export const setUserActive = async (id: number, isActive: boolean) => {
  const response = await http.patch<SystemUser>(`/users/${id}/`, { is_active: isActive })
  return response.data
}

export const resetUserPassword = async (id: number, newPassword: string) => {
  const response = await http.post<{ detail: string }>(`/users/${id}/reset-password/`, {
    new_password: newPassword,
  })
  return response.data
}

export const changeOwnPassword = async (oldPassword: string, newPassword: string) => {
  const response = await http.post<{ detail: string }>('/users/change-password/', {
    old_password: oldPassword,
    new_password: newPassword,
  })
  return response.data
}
