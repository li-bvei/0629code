import http from '../services/http'
import type {
  Company,
  CreateCompanyPayload,
  ListParams,
  PaginatedResponse,
  UpdateCompanyPayload,
} from '../types/api'

export const listCompanies = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Company>>('/companies/', { params })
  return response.data
}

export const getCompany = async (id: number) => {
  const response = await http.get<Company>(`/companies/${id}/`)
  return response.data
}

export const createCompany = async (payload: CreateCompanyPayload) => {
  const response = await http.post<Company>('/companies/', payload)
  return response.data
}

export const updateCompany = async (id: number, payload: UpdateCompanyPayload) => {
  const response = await http.patch<Company>(`/companies/${id}/`, payload)
  return response.data
}

export const deleteCompany = async (id: number) => {
  await http.delete(`/companies/${id}/`)
}
