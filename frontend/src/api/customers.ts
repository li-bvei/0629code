import http from '../services/http'
import type {
  CreateCustomerPayload,
  Customer,
  CustomerDetail,
  ListParams,
  PaginatedResponse,
  ResidenceStatusMaster,
  ResidenceStatusMasterPayload,
  UpdateCustomerPayload,
} from '../types/api'

export const listCustomers = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Customer>>('/customers/', { params })
  return response.data
}

export const getCustomer = async (id: number) => {
  const response = await http.get<CustomerDetail>(`/customers/${id}/`)
  return response.data
}

export const createCustomer = async (payload: CreateCustomerPayload) => {
  const response = await http.post<Customer>('/customers/', payload)
  return response.data
}

export const updateCustomer = async (id: number, payload: UpdateCustomerPayload) => {
  const response = await http.patch<Customer>(`/customers/${id}/`, payload)
  return response.data
}

export const deleteCustomer = async (id: number) => {
  await http.delete(`/customers/${id}/`)
}

export const listResidenceStatusMasters = async (params?: ListParams & { is_active?: boolean | string }) => {
  const response = await http.get<PaginatedResponse<ResidenceStatusMaster>>('/residence-status-masters/', { params })
  return response.data
}

export const createResidenceStatusMaster = async (payload: ResidenceStatusMasterPayload) => {
  const response = await http.post<ResidenceStatusMaster>('/residence-status-masters/', payload)
  return response.data
}

export const updateResidenceStatusMaster = async (id: number, payload: Partial<ResidenceStatusMasterPayload>) => {
  const response = await http.patch<ResidenceStatusMaster>(`/residence-status-masters/${id}/`, payload)
  return response.data
}

export const seedStandardResidenceStatusMasters = async () => {
  const response = await http.post<{ success: boolean, message: string, created: number, skipped: number }>(
    '/residence-status-masters/seed-standard/',
    {},
  )
  return response.data
}
