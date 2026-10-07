import http from '../services/http'
import type {
  CreateCustomerPayload,
  Customer,
  CustomerDetail,
  CustomerMatchCandidate,
  CustomerMatchPayload,
  ListParams,
  PaginatedResponse,
  ResidenceStatusMaster,
  ResidenceStatusMasterPayload,
  UpdateCustomerPayload,
} from '../types/api'

export const listCustomers = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Customer>>('/customers/', { params })
  return response.data
}

export const getCustomer = async (id: number) => {
  const response = await http.get<CustomerDetail>(`/customers/${id}/`)
  // 基本情報レベル（案件の無い顧客など）では関連データが返らないため既定値で補う。
  const data = response.data
  return {
    ...data,
    related_cases: data.related_cases ?? [],
    related_companies: data.related_companies ?? [],
    recent_activities: data.recent_activities ?? [],
    summary: data.summary ?? {
      active_cases_count: 0,
      historical_cases_count: 0,
      family_count: 0,
      company_count: 0,
      primary_case: null,
    },
  } as CustomerDetail
}

export const matchCustomers = async (payload: CustomerMatchPayload) => {
  const response = await http.post<{ candidates: CustomerMatchCandidate[] }>('/customers/match/', payload)
  return response.data.candidates
}

export const createCustomer = async (payload: CreateCustomerPayload) => {
  const response = await http.post<Customer>('/customers/', payload)
  return response.data
}

export const updateCustomer = async (id: number, payload: UpdateCustomerPayload) => {
  const response = await http.patch<Customer>(`/customers/${id}/`, payload)
  return response.data
}

export const deleteCustomer = async (id: number) => {
  await http.delete(`/customers/${id}/`)
}

export const listResidenceStatusMasters = async (params?: ListParams & { is_active?: boolean | string }) => {
  const response = await http.get<PaginatedResponse<ResidenceStatusMaster>>('/residence-status-masters/', { params })
  return response.data
}

export const createResidenceStatusMaster = async (payload: ResidenceStatusMasterPayload) => {
  const response = await http.post<ResidenceStatusMaster>('/residence-status-masters/', payload)
  return response.data
}

export const updateResidenceStatusMaster = async (id: number, payload: Partial<ResidenceStatusMasterPayload>) => {
  const response = await http.patch<ResidenceStatusMaster>(`/residence-status-masters/${id}/`, payload)
  return response.data
}

export const seedStandardResidenceStatusMasters = async () => {
  const response = await http.post<{ success: boolean, message: string, created: number, skipped: number }>(
    '/residence-status-masters/seed-standard/',
    {},
  )
  return response.data
}

// P6：マイナンバーの表示（専用操作）。返った値は画面の一時表示だけに使い、保存・記録しない
export interface MyNumberRevealResponse {
  registered: boolean
  my_number: string
}

export type MyNumberTargetKind = 'customer' | 'family_member' | 'company_staff'

const REVEAL_BASES: Record<MyNumberTargetKind, string> = {
  customer: '/customers/',
  family_member: '/family-members/',
  company_staff: '/company-staff/',
}

// 会社職員：既存顧客に関連付いていればその顧客の値（後端が判定）、旧形式の職員は職員自身の値
export const revealMyNumber = async (kind: MyNumberTargetKind, id: number) => {
  const base = REVEAL_BASES[kind]
  const response = await http.post<MyNumberRevealResponse>(`${base}${id}/reveal-my-number/`, {})
  return response.data
}
