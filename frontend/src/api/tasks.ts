import http from '../services/http'
import type { ListParams, PaginatedResponse, Task, TaskPayload } from '../types/api'

export const listTasks = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Task>>('/tasks/', { params })
  return response.data
}

export const createTask = async (payload: TaskPayload) => {
  const response = await http.post<Task>('/tasks/', payload)
  return response.data
}

export const updateTask = async (id: number, payload: TaskPayload) => {
  const response = await http.patch<Task>(`/tasks/${id}/`, payload)
  return response.data
}

export const deleteTask = async (id: number) => {
  await http.delete(`/tasks/${id}/`)
}
