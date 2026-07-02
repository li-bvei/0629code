import http from '../services/http'
import type { FamilyMember, FamilyMemberPayload, ListParams, PaginatedResponse } from '../types/api'

export const listFamilyMembers = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<FamilyMember>>('/family-members/', { params })
  return response.data
}

export const createFamilyMember = async (payload: FamilyMemberPayload) => {
  const response = await http.post<FamilyMember>('/family-members/', payload)
  return response.data
}

export const updateFamilyMember = async (id: number, payload: FamilyMemberPayload) => {
  const response = await http.patch<FamilyMember>(`/family-members/${id}/`, payload)
  return response.data
}

export const deleteFamilyMember = async (id: number) => {
  await http.delete(`/family-members/${id}/`)
}
