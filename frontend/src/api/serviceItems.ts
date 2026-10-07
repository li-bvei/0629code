// サービス価格マスタ（P4）。委託底価は底価権限者への応答にだけ含まれる（後端が出し分ける）。
import http from '../services/http'
import type { BusinessDocumentEndpoint, InternalCostsResponse, ServiceItem, ServiceItemPayload } from '../types/accounting'
import type { PaginatedResponse } from '../types/api'

export interface ServiceItemListParams {
  search?: string
  active?: '1' | '0'
  category?: string
  page?: number
  page_size?: number
}

export const listServiceItems = async (params?: ServiceItemListParams) => {
  const response = await http.get<PaginatedResponse<ServiceItem>>('/accounting/service-items/', { params })
  return response.data
}

export const saveServiceItem = async (id: number | null, payload: ServiceItemPayload) => {
  const response = id
    ? await http.patch<ServiceItem>(`/accounting/service-items/${id}/`, payload)
    : await http.post<ServiceItem>('/accounting/service-items/', payload)
  return response.data
}

// P6：暫定価格を確定する（管理権限と底価権限の両方が必要。version は最後に読んだ updated_at、古ければ 409）
export const confirmServiceItemPrice = async (id: number, version: string) => {
  const response = await http.post<ServiceItem>(`/accounting/service-items/${id}/confirm-price/`, { version })
  return response.data
}

export const deleteServiceItem = async (id: number) => {
  await http.delete(`/accounting/service-items/${id}/`)
}

export const getInternalCosts = async (endpoint: BusinessDocumentEndpoint, id: number) => {
  const response = await http.get<InternalCostsResponse>(`/accounting/${endpoint}/${id}/internal-costs/`)
  return response.data
}
