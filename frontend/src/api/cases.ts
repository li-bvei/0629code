import http from '../services/http'
import type { Case, CasePayload, GenerateRemindersResponse, ListParams, PaginatedResponse } from '../types/api'

export const listCases = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Case>>('/cases/', { params })
  return response.data
}

export const getCase = async (id: number) => {
  const response = await http.get<Case>(`/cases/${id}/`)
  return response.data
}

export const createCase = async (payload: CasePayload) => {
  const response = await http.post<Case>('/cases/', payload)
  return response.data
}

export const updateCase = async (id: number, payload: Partial<CasePayload>) => {
  const response = await http.patch<Case>(`/cases/${id}/`, payload)
  return response.data
}

export const deleteCase = async (id: number) => {
  await http.delete(`/cases/${id}/`)
}

export const cancelCase = async (id: number, reason: string) => {
  const response = await http.post<Case>(`/cases/${id}/cancel/`, { reason })
  return response.data
}

export const generateCaseReminders = async (id: number) => {
  const response = await http.post<GenerateRemindersResponse>(`/cases/${id}/generate-reminders/`, {})
  return response.data
}
