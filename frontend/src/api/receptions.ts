import http from '../services/http'
import type { ReceptionPayload, ReceptionResponse } from '../types/api'

export const createReception = async (payload: ReceptionPayload) => {
  const response = await http.post<ReceptionResponse>('/receptions/', payload)
  return response.data
}
