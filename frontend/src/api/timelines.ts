import http from '../services/http'
import type { ListParams, PaginatedResponse, Timeline, TimelinePayload } from '../types/api'

export const listTimelines = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Timeline>>('/timelines/', { params })
  return response.data
}

export const createTimeline = async (payload: TimelinePayload) => {
  const response = await http.post<Timeline>('/timelines/', payload)
  return response.data
}

export const updateTimeline = async (id: number, payload: Partial<TimelinePayload>) => {
  const response = await http.patch<Timeline>(`/timelines/${id}/`, payload)
  return response.data
}
