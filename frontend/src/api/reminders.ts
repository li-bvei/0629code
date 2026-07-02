import http from '../services/http'
import type { ListParams, PaginatedResponse, Reminder, ReminderPayload } from '../types/api'

export const listReminders = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Reminder>>('/reminders/', { params })
  return response.data
}

export const createReminder = async (payload: ReminderPayload) => {
  const response = await http.post<Reminder>('/reminders/', payload)
  return response.data
}

export const updateReminder = async (id: number, payload: Partial<ReminderPayload>) => {
  const response = await http.patch<Reminder>(`/reminders/${id}/`, payload)
  return response.data
}

export const deleteReminder = async (id: number) => {
  await http.delete(`/reminders/${id}/`)
}
