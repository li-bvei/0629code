import http from '../services/http'
import type { CompanyStaff, CompanyStaffPayload, ListParams, PaginatedResponse } from '../types/api'

export const listCompanyStaff = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<CompanyStaff>>('/company-staff/', { params })
  return response.data
}

export const createCompanyStaff = async (payload: CompanyStaffPayload) => {
  const response = await http.post<CompanyStaff>('/company-staff/', payload)
  return response.data
}

export const updateCompanyStaff = async (id: number, payload: CompanyStaffPayload) => {
  const response = await http.patch<CompanyStaff>(`/company-staff/${id}/`, payload)
  return response.data
}

export const deleteCompanyStaff = async (id: number) => {
  await http.delete(`/company-staff/${id}/`)
}
