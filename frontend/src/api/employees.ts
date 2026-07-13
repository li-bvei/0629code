import http from '../services/http'
import type { Employee, EmployeePayload, ListParams, PaginatedResponse } from '../types/api'

type EmployeeListParams = ListParams & {
  is_active?: boolean | string
}

export const listEmployees = async (params?: EmployeeListParams) => {
  const response = await http.get<PaginatedResponse<Employee>>('/employees/', { params })
  return response.data
}

export const createEmployee = async (payload: EmployeePayload) => {
  const response = await http.post<Employee>('/employees/', payload)
  return response.data
}

export const updateEmployee = async (id: number, payload: Partial<EmployeePayload>) => {
  const response = await http.patch<Employee>(`/employees/${id}/`, payload)
  return response.data
}
