import http from '../services/http'
import type { DashboardDeadline } from '../types/api'

export const listDashboardDeadlines = async () => {
  const response = await http.get<DashboardDeadline[]>('/dashboard/deadlines/')
  return response.data
}
