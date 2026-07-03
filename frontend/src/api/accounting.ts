import http from '../services/http'
import type {
  AccountingDashboard,
  AccountingListParams,
  AccountingPaginatedResponse,
  Expense,
  ExpenseCategory,
  ExpenseCategoryPayload,
  ExpensePayload,
  IncomeSource,
  IncomeSourcePayload,
  VehicleUsage,
  VehicleUsagePayload,
} from '../types/accounting'

const cleanParams = (params?: AccountingListParams) => {
  if (!params) return undefined
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== '' && value !== undefined && value !== null),
  )
}

export const getAccountingDashboard = async () => {
  const response = await http.get<AccountingDashboard>('/accounting/dashboard/')
  return response.data
}

export const listAccountingExpenses = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<Expense>>('/accounting/expenses/', {
    params: cleanParams(params),
  })
  return response.data
}

export const getAccountingExpense = async (id: number | string) => {
  const response = await http.get<Expense>(`/accounting/expenses/${id}/`)
  return response.data
}

export const createAccountingExpense = async (payload: ExpensePayload) => {
  const response = await http.post<Expense>('/accounting/expenses/', payload)
  return response.data
}

export const updateAccountingExpense = async (id: number | string, payload: Partial<ExpensePayload>) => {
  const response = await http.patch<Expense>(`/accounting/expenses/${id}/`, payload)
  return response.data
}

export const deleteAccountingExpense = async (id: number) => {
  await http.delete(`/accounting/expenses/${id}/`)
}

export const listAccountingExpenseCategories = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<ExpenseCategory>>('/accounting/expense-categories/', {
    params: cleanParams(params),
  })
  return response.data
}

export const getAccountingExpenseCategory = async (id: number | string) => {
  const response = await http.get<ExpenseCategory>(`/accounting/expense-categories/${id}/`)
  return response.data
}

export const createAccountingExpenseCategory = async (payload: ExpenseCategoryPayload) => {
  const response = await http.post<ExpenseCategory>('/accounting/expense-categories/', payload)
  return response.data
}

export const updateAccountingExpenseCategory = async (
  id: number | string,
  payload: Partial<ExpenseCategoryPayload>,
) => {
  const response = await http.patch<ExpenseCategory>(`/accounting/expense-categories/${id}/`, payload)
  return response.data
}

export const deleteAccountingExpenseCategory = async (id: number) => {
  await http.delete(`/accounting/expense-categories/${id}/`)
}

export const listAccountingIncomeSources = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<IncomeSource>>('/accounting/income-sources/', {
    params: cleanParams(params),
  })
  return response.data
}

export const getAccountingIncomeSource = async (id: number | string) => {
  const response = await http.get<IncomeSource>(`/accounting/income-sources/${id}/`)
  return response.data
}

export const createAccountingIncomeSource = async (payload: IncomeSourcePayload) => {
  const response = await http.post<IncomeSource>('/accounting/income-sources/', payload)
  return response.data
}

export const updateAccountingIncomeSource = async (id: number | string, payload: Partial<IncomeSourcePayload>) => {
  const response = await http.patch<IncomeSource>(`/accounting/income-sources/${id}/`, payload)
  return response.data
}

export const deleteAccountingIncomeSource = async (id: number) => {
  await http.delete(`/accounting/income-sources/${id}/`)
}

export const listAccountingVehicleUsages = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<VehicleUsage>>('/accounting/vehicle-usages/', {
    params: cleanParams(params),
  })
  return response.data
}

export const getAccountingVehicleUsage = async (id: number | string) => {
  const response = await http.get<VehicleUsage>(`/accounting/vehicle-usages/${id}/`)
  return response.data
}

export const createAccountingVehicleUsage = async (payload: VehicleUsagePayload) => {
  const response = await http.post<VehicleUsage>('/accounting/vehicle-usages/', payload)
  return response.data
}

export const updateAccountingVehicleUsage = async (id: number | string, payload: Partial<VehicleUsagePayload>) => {
  const response = await http.patch<VehicleUsage>(`/accounting/vehicle-usages/${id}/`, payload)
  return response.data
}

export const deleteAccountingVehicleUsage = async (id: number) => {
  await http.delete(`/accounting/vehicle-usages/${id}/`)
}
