import type { PaginatedResponse } from './api'

export interface AccountingListParams {
  page?: number
  search?: string
  start_date?: string | null
  end_date?: string | null
  project?: number | string
  category?: string
  payment_method?: string
  purpose?: string
  is_active?: boolean | string
  is_reimbursed?: boolean | string
  is_exported?: boolean | string
}

export interface ExpenseCategory {
  id: number
  name: string
  is_active: boolean
  sort_order: number
  created_at?: string
  updated_at?: string
}

export interface ExpenseCategoryPayload {
  name: string
  is_active: boolean
  sort_order: number
}

export interface Expense {
  id: number
  expense_date: string
  place: string
  category: string
  amount: string | number
  payment_method: string
  expense_target: string
  note: string
  is_reimbursed: boolean
  is_exported: boolean
  created_at?: string
  updated_at?: string
}

export interface ExpensePayload {
  expense_date: string
  place?: string
  category: string
  amount: string | number
  payment_method?: string
  expense_target?: string
  note?: string
  is_reimbursed: boolean
  is_exported: boolean
}

export interface ExpenseTargetChartItem {
  name: string
  amount: number | string
}

export interface IncomeSource {
  id: number
  source_date: string
  source_target: string
  amount: string | number
  note: string
  is_exported: boolean
  created_at?: string
  updated_at?: string
}

export interface IncomeSourcePayload {
  source_date: string
  source_target?: string
  amount: string | number
  note?: string
  is_exported: boolean
}

export interface VehicleUsage {
  id: number
  usage_date: string
  place: string
  distance_km: string | number
  usage_target: string
  purpose: string
  note: string
  is_exported: boolean
  created_at?: string
  updated_at?: string
}

export interface VehicleUsagePayload {
  usage_date: string
  place?: string
  distance_km: string | number
  usage_target?: string
  purpose?: string
  note?: string
  is_exported: boolean
}

export interface AccountingDashboard {
  monthly_expense_total: number | string
  monthly_income_source_total: number | string
  monthly_vehicle_km_total: number | string
  monthly_unreimbursed_total: number | string
  total_expense_amount: number | string
  total_income_source_amount: number | string
  current_balance: number | string
  expense_target_chart: ExpenseTargetChartItem[]
  expense_category_chart: ExpenseTargetChartItem[]
  recent_expenses: Expense[]
  recent_income_sources: IncomeSource[]
  recent_vehicle_usages: VehicleUsage[]
}

export interface AccountingProject {
  id: number
  name: string
  description?: string
  start_date?: string | null
  end_date?: string | null
  is_active: boolean
  note?: string
  created_at?: string
  updated_at?: string
}

export interface AccountingProjectPayload {
  name: string
  description?: string
  start_date?: string | null
  end_date?: string | null
  is_active: boolean
  note?: string
}

export interface AccountingProjectDetail extends AccountingProject {
  income_total: number | string
  expense_total: number | string
  balance: number | string
  income_count: number
  expense_count: number
}

export interface AccountingProjectIncome {
  id: number
  project: number
  income_date: string
  income_target?: string
  amount: number | string
  note?: string
  created_at?: string
  updated_at?: string
}

export interface AccountingProjectIncomePayload {
  project: number
  income_date: string
  income_target?: string
  amount: number | string
  note?: string
}

export interface AccountingProjectExpense {
  id: number
  project: number
  expense_date: string
  place?: string
  category_name?: string
  amount: number | string
  payment_method?: string
  expense_target?: string
  note?: string
  source_expense?: number | null
  created_at?: string
  updated_at?: string
}

export interface AccountingProjectExpensePayload {
  project: number
  expense_date: string
  place?: string
  category_name?: string
  amount: number | string
  payment_method?: string
  expense_target?: string
  note?: string
  source_expense?: number | null
}

export type AccountingPaginatedResponse<T> = PaginatedResponse<T>
