import http from '../services/http'
import type {
  CreateCustomerPayload,
  Customer,
  CustomerDetail,
  ListParams,
  PaginatedResponse,
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
