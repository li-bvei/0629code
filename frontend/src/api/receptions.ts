import http from '../services/http'
import type { ReceptionCreatePayload, ReceptionResponse } from '../types/api'

export const createReception = async (payload: ReceptionCreatePayload) => {
  const response = await http.post<ReceptionResponse>('/receptions/', payload)
  return response.data
}
