// 毎日の計画（Task の拡張）と業務報告（P3）。変更系はすべて版（version＝updated_at）を送る。
import http from '../services/http'
import type { DailyWorkReport, PaginatedResponse, Task, TaskPriority } from '../types/api'

export interface PlanItemPayload {
  title?: string
  description?: string
  case?: number | null
  priority?: TaskPriority
  status?: string
  result_note?: string
  work_date?: string
}

export const listPlanItems = async (workDate: string, employee: number | 'me' = 'me') => (
  await http.get<PaginatedResponse<Task>>('/tasks/', { params: { plan: 1, work_date: workDate, employee, page_size: 200 } })
).data.results

export const createPlanItem = async (payload: PlanItemPayload & { title: string; work_date: string }) => (
  await http.post<Task>('/tasks/', payload)
).data

export const updatePlanItem = async (id: number, payload: PlanItemPayload, version: string) => (
  await http.patch<Task>(`/tasks/${id}/`, { ...payload, version })
).data

export const deletePlanItem = async (id: number, version: string) => {
  await http.delete(`/tasks/${id}/`, { params: { version } })
}

export const carryOverPlanItem = async (id: number, targetDate: string, version: string) => (
  await http.post<{ original: Task; created: Task }>(`/tasks/${id}/carry-over/`, { target_date: targetDate, version })
).data

export interface CarryBatchResult {
  batch_id: string
  target_date: string
  requested: number
  succeeded: number
  failed: number
  results: Array<{ id: number; status: 'success' | 'failed'; code?: string; detail?: string; new_id?: number }>
}

export const carryOverPlanItems = async (targetDate: string, items: Array<{ id: number; version: string }>) => (
  await http.post<CarryBatchResult>('/tasks/carry-over-batch/', { target_date: targetDate, items })
).data

// P6：日本の祝日（振替休日・国民の休日を含む。後端のローカル暦で判定、外部通信なし）
export interface CalendarDayInfo {
  date: string
  is_weekend: boolean
  holiday_name: string
  is_business_day: boolean
  next_business_day: string
  supported: boolean
  supported_years: [number, number]
  notice: string
}

export const getCalendarDay = async (date: string) => (
  await http.get<CalendarDayInfo>('/tasks/calendar/', { params: { date } })
).data

export const reorderPlanItems = async (workDate: string, items: Array<{ id: number; version: string }>) => (
  await http.post<Task[]>('/tasks/reorder/', { work_date: workDate, items })
).data

// --- 業務報告 ---
export const findDailyReport = async (reportDate: string, employee: number | 'me' = 'me') => (
  await http.get<PaginatedResponse<DailyWorkReport>>('/daily-reports/', { params: { report_date: reportDate, employee } })
).data.results[0] ?? null

export const listDailyReports = async (params: { employee?: number | 'me'; date_from?: string; date_to?: string }) => (
  await http.get<PaginatedResponse<DailyWorkReport>>('/daily-reports/', { params: { page_size: 60, ...params } })
).data.results

export const generateDailyReport = async (reportDate: string, options: { version?: string; overwriteEdits?: boolean } = {}) => (
  await http.post<DailyWorkReport>('/daily-reports/generate/', {
    report_date: reportDate, version: options.version, overwrite_edits: options.overwriteEdits || undefined,
  })
).data

export const updateDailyReportText = async (id: number, finalText: string, version: string) => (
  await http.patch<DailyWorkReport>(`/daily-reports/${id}/`, { final_text: finalText, version })
).data

export const confirmDailyReport = async (id: number, version: string) => (
  await http.post<DailyWorkReport>(`/daily-reports/${id}/confirm/`, { version })
).data
