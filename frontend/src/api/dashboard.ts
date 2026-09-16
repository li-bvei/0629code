import http from '../services/http'
import type { DashboardDeadline, DismissedDeadlinePayload } from '../types/api'

export const listDashboardDeadlines = async () => {
  const response = await http.get<DashboardDeadline[]>('/dashboard/deadlines/')
  return response.data
}

export const dismissDeadline = async (payload: DismissedDeadlinePayload) => {
  const response = await http.post('/dismissed-deadlines/', payload)
  return response.data
}

export const bulkDismissOverdueDeadlines = async () => {
  const response = await http.post<{ dismissed_count: number, checked_count: number }>(
    '/dismissed-deadlines/bulk-dismiss-overdue/',
    {},
  )
  return response.data
}
