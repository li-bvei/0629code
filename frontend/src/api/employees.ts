import http from '../services/http'
import type { Employee, ListParams, PaginatedResponse } from '../types/api'

export const listEmployees = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Employee>>('/employees/', { params })
  return response.data
}
