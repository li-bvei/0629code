import http from '../services/http'
import type {
  AccountingDashboard,
  AccountingListParams,
  AccountingPaginatedResponse,
  AccountingProject,
  AccountingProjectReport,
  AccountingProjectDetail,
  AccountingProjectExpense,
  AccountingProjectExpensePayload,
  AccountingProjectIncome,
  AccountingProjectIncomePayload,
  AccountingProjectPayload,
  AccountingVoucher,
  AccountingVoucherPayload,
  Expense,
  ExpenseCategory,
  ExpenseCategoryPayload,
  ExpensePayload,
  IncomeSource,
  IncomeSourcePayload,
  SeifuNoticeGeneratePayload,
  SeifuNoticePdfRecord,
  SeifuNoticeRecordPayload,
  SeifuNoticeTemplateInfo,
  TaxRenewalAgentTemplate,
  TaxRenewalAgentTemplatePayload,
  TaxRenewalPdfDiagnostic,
  TaxRenewalGeneratePdfPayload,
  TaxRenewalTemplate,
  TaxRenewalVoucherPayload,
  TaxRenewalVoucherRecord,
  VehicleUsage,
  VehicleUsagePayload,
  VisaGuarantorTemplate,
  VisaGuarantorTemplatePayload,
  VisaReturnApplication,
  VisaReturnApplicationPayload,
  VoucherItemTemplate,
  VoucherItemTemplatePayload,
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

export const downloadAccountingExpensesExcel = async (params?: AccountingListParams) => {
  const response = await http.get<Blob>('/accounting/expenses/excel/', {
    params: cleanParams(params),
    responseType: 'blob',
  })
  return {
    blob: response.data,
    contentDisposition: response.headers['content-disposition'] as string | undefined,
  }
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

export const listAccountingProjects = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<AccountingProject>>('/accounting/projects/', {
    params: cleanParams(params),
  })
  return response.data
}

export const getAccountingProjects = listAccountingProjects

export const getAccountingProjectReport = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingProjectReport>('/accounting/projects/report/', {
    params: cleanParams(params),
  })
  return response.data
}

export const getAccountingProject = async (id: number | string) => {
  const response = await http.get<AccountingProjectDetail>(`/accounting/projects/${id}/`)
  return response.data
}

export const downloadAccountingProjectExcel = async (id: number | string) => {
  const response = await http.get<Blob>(`/accounting/projects/${id}/excel/`, {
    responseType: 'blob',
  })
  return {
    blob: response.data,
    contentDisposition: response.headers['content-disposition'] as string | undefined,
  }
}

export const createAccountingProject = async (payload: AccountingProjectPayload) => {
  const response = await http.post<AccountingProject>('/accounting/projects/', payload)
  return response.data
}

export const updateAccountingProject = async (id: number | string, payload: Partial<AccountingProjectPayload>) => {
  const response = await http.patch<AccountingProject>(`/accounting/projects/${id}/`, payload)
  return response.data
}

export const deleteAccountingProject = async (id: number) => {
  await http.delete(`/accounting/projects/${id}/`)
}

export const listAccountingProjectIncomes = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<AccountingProjectIncome>>('/accounting/project-incomes/', {
    params: cleanParams(params),
  })
  return response.data
}

export const getAccountingProjectIncomes = listAccountingProjectIncomes

export const createAccountingProjectIncome = async (payload: AccountingProjectIncomePayload) => {
  const response = await http.post<AccountingProjectIncome>('/accounting/project-incomes/', payload)
  return response.data
}

export const updateAccountingProjectIncome = async (
  id: number | string,
  payload: Partial<AccountingProjectIncomePayload>,
) => {
  const response = await http.patch<AccountingProjectIncome>(`/accounting/project-incomes/${id}/`, payload)
  return response.data
}

export const deleteAccountingProjectIncome = async (id: number) => {
  await http.delete(`/accounting/project-incomes/${id}/`)
}

export const listAccountingProjectExpenses = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<AccountingProjectExpense>>('/accounting/project-expenses/', {
    params: cleanParams(params),
  })
  return response.data
}

export const getAccountingProjectExpenses = listAccountingProjectExpenses

export const createAccountingProjectExpense = async (payload: AccountingProjectExpensePayload) => {
  const response = await http.post<AccountingProjectExpense>('/accounting/project-expenses/', payload)
  return response.data
}

export const updateAccountingProjectExpense = async (
  id: number | string,
  payload: Partial<AccountingProjectExpensePayload>,
) => {
  const response = await http.patch<AccountingProjectExpense>(`/accounting/project-expenses/${id}/`, payload)
  return response.data
}

export const deleteAccountingProjectExpense = async (id: number) => {
  await http.delete(`/accounting/project-expenses/${id}/`)
}

export const copyExpensesToProject = async (projectId: number | string, expenseIds: number[]) => {
  const response = await http.post<{ created: number }>(`/accounting/projects/${projectId}/copy-expenses/`, {
    expense_ids: expenseIds,
  })
  return response.data
}

export const listAccountingVouchers = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<AccountingVoucher>>('/accounting/vouchers/', {
    params: cleanParams(params),
  })
  return response.data
}

export const createAccountingVoucher = async (payload: AccountingVoucherPayload) => {
  const response = await http.post<AccountingVoucher>('/accounting/vouchers/', payload)
  return response.data
}

export const updateAccountingVoucher = async (
  id: number | string,
  payload: Partial<AccountingVoucherPayload>,
) => {
  const response = await http.patch<AccountingVoucher>(`/accounting/vouchers/${id}/`, payload)
  return response.data
}

export const deleteAccountingVoucher = async (id: number) => {
  await http.delete(`/accounting/vouchers/${id}/`)
}

export const downloadAccountingVoucherPdf = async (id: number, withSeal = false) => {
  const response = await http.get<Blob>(`/accounting/vouchers/${id}/pdf/`, {
    params: withSeal ? { with_seal: 1 } : undefined,
    responseType: 'blob',
  })
  return {
    blob: response.data,
    contentDisposition: response.headers['content-disposition'] as string | undefined,
  }
}

export const listVoucherItemTemplates = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<VoucherItemTemplate>>(
    '/accounting/voucher-item-templates/',
    { params: cleanParams(params) },
  )
  return response.data
}

export const createVoucherItemTemplate = async (payload: VoucherItemTemplatePayload) => {
  const response = await http.post<VoucherItemTemplate>('/accounting/voucher-item-templates/', payload)
  return response.data
}

export const updateVoucherItemTemplate = async (
  id: number | string,
  payload: Partial<VoucherItemTemplatePayload>,
) => {
  const response = await http.patch<VoucherItemTemplate>(`/accounting/voucher-item-templates/${id}/`, payload)
  return response.data
}

export const deleteVoucherItemTemplate = async (id: number) => {
  await http.delete(`/accounting/voucher-item-templates/${id}/`)
}

export const listVisaReturnApplications = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<VisaReturnApplication>>(
    '/accounting/visa-return-applications/',
    { params: cleanParams(params) },
  )
  return response.data
}

export const getVisaReturnApplication = async (id: number | string) => {
  const response = await http.get<VisaReturnApplication>(`/accounting/visa-return-applications/${id}/`)
  return response.data
}

export const createVisaReturnApplication = async (payload: VisaReturnApplicationPayload) => {
  const response = await http.post<VisaReturnApplication>('/accounting/visa-return-applications/', payload)
  return response.data
}

export const updateVisaReturnApplication = async (
  id: number | string,
  payload: Partial<VisaReturnApplicationPayload>,
) => {
  const response = await http.patch<VisaReturnApplication>(`/accounting/visa-return-applications/${id}/`, payload)
  return response.data
}

export const deleteVisaReturnApplication = async (id: number | string) => {
  await http.delete(`/accounting/visa-return-applications/${id}/`)
}

export const listVisaGuarantorTemplates = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<VisaGuarantorTemplate>>(
    '/accounting/visa-guarantor-templates/',
    { params: cleanParams(params) },
  )
  return response.data
}

export const createVisaGuarantorTemplate = async (payload: VisaGuarantorTemplatePayload) => {
  const response = await http.post<VisaGuarantorTemplate>('/accounting/visa-guarantor-templates/', payload)
  return response.data
}

export const updateVisaGuarantorTemplate = async (
  id: number | string,
  payload: Partial<VisaGuarantorTemplatePayload>,
) => {
  const response = await http.patch<VisaGuarantorTemplate>(`/accounting/visa-guarantor-templates/${id}/`, payload)
  return response.data
}

export const deleteVisaGuarantorTemplate = async (id: number | string) => {
  await http.delete(`/accounting/visa-guarantor-templates/${id}/`)
}

export const downloadVisaReturnApplicationPdf = async (id: number | string) => {
  const response = await http.get<Blob>(`/accounting/visa-return-applications/${id}/pdf/`, {
    responseType: 'blob',
  })
  return {
    blob: response.data,
    contentDisposition: response.headers['content-disposition'] as string | undefined,
  }
}

export const getSeifuNoticeTemplateInfo = async () => {
  const response = await http.get<SeifuNoticeTemplateInfo>('/accounting/seifu-notice-pdf/template/')
  return response.data
}

export const getSeifuNoticePreview = async (page: number) => {
  const response = await http.get<Blob>('/accounting/seifu-notice-pdf/preview/', {
    params: { page },
    responseType: 'blob',
  })
  return response.data
}

export const generateSeifuNoticePdf = async (payload: SeifuNoticeGeneratePayload) => {
  const response = await http.post<Blob>('/accounting/seifu-notice-pdf/generate/', payload, {
    responseType: 'blob',
  })
  return {
    blob: response.data,
    contentDisposition: response.headers['content-disposition'] as string | undefined,
  }
}

export const listSeifuNoticeRecords = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<SeifuNoticePdfRecord>>(
    '/accounting/seifu-notice-records/',
    { params: cleanParams(params) },
  )
  return response.data
}

export const getSeifuNoticeRecord = async (id: number | string) => {
  const response = await http.get<SeifuNoticePdfRecord>(`/accounting/seifu-notice-records/${id}/`)
  return response.data
}

export const createSeifuNoticeRecord = async (payload: SeifuNoticeRecordPayload) => {
  const response = await http.post<SeifuNoticePdfRecord>('/accounting/seifu-notice-records/', payload)
  return response.data
}

export const updateSeifuNoticeRecord = async (
  id: number | string,
  payload: Partial<SeifuNoticeRecordPayload>,
) => {
  const response = await http.patch<SeifuNoticePdfRecord>(`/accounting/seifu-notice-records/${id}/`, payload)
  return response.data
}

export const deleteSeifuNoticeRecord = async (id: number | string) => {
  await http.delete(`/accounting/seifu-notice-records/${id}/`)
}

export const downloadSeifuNoticeRecordPdf = async (id: number | string) => {
  const response = await http.post<Blob>(`/accounting/seifu-notice-records/${id}/generate_pdf/`, undefined, {
    responseType: 'blob',
  })
  return {
    blob: response.data,
    contentDisposition: response.headers['content-disposition'] as string | undefined,
  }
}

export const listTaxRenewalTemplates = async () => {
  const response = await http.get<TaxRenewalTemplate[]>('/accounting/tax-renewal-templates/')
  return response.data
}

export const listTaxRenewalRecords = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<TaxRenewalVoucherRecord>>(
    '/accounting/tax-renewal-records/',
    { params: cleanParams(params) },
  )
  return response.data
}

export const getTaxRenewalRecord = async (id: number | string) => {
  const response = await http.get<TaxRenewalVoucherRecord>(`/accounting/tax-renewal-records/${id}/`)
  return response.data
}

export const createTaxRenewalRecord = async (payload: TaxRenewalVoucherPayload) => {
  const response = await http.post<TaxRenewalVoucherRecord>('/accounting/tax-renewal-records/', payload)
  return response.data
}

export const updateTaxRenewalRecord = async (
  id: number | string,
  payload: Partial<TaxRenewalVoucherPayload>,
) => {
  const response = await http.patch<TaxRenewalVoucherRecord>(`/accounting/tax-renewal-records/${id}/`, payload)
  return response.data
}

export const deleteTaxRenewalRecord = async (id: number | string) => {
  await http.delete(`/accounting/tax-renewal-records/${id}/`)
}

export const generateTaxRenewalRecordPdf = async (
  id: number | string,
  payload?: TaxRenewalGeneratePdfPayload,
) => {
  const response = await http.post<Blob>(`/accounting/tax-renewal-records/${id}/generate_pdf/`, payload || {}, {
    responseType: 'blob',
  })
  return {
    blob: response.data,
    contentDisposition: response.headers['content-disposition'] as string | undefined,
    mappingFieldCount: response.headers['x-mapping-field-count'] as string | undefined,
    writtenFieldCount: response.headers['x-written-field-count'] as string | undefined,
    skippedEmptyFieldCount: response.headers['x-skipped-empty-field-count'] as string | undefined,
    warningFields: response.headers['x-warning-fields'] as string | undefined,
  }
}

export const listTaxRenewalAgentTemplates = async (params?: AccountingListParams) => {
  const response = await http.get<AccountingPaginatedResponse<TaxRenewalAgentTemplate>>(
    '/accounting/tax-renewal-agent-templates/',
    { params: cleanParams(params) },
  )
  return response.data
}

export const createTaxRenewalAgentTemplate = async (payload: TaxRenewalAgentTemplatePayload) => {
  const response = await http.post<TaxRenewalAgentTemplate>('/accounting/tax-renewal-agent-templates/', payload)
  return response.data
}

export const updateTaxRenewalAgentTemplate = async (
  id: number | string,
  payload: Partial<TaxRenewalAgentTemplatePayload>,
) => {
  const response = await http.patch<TaxRenewalAgentTemplate>(`/accounting/tax-renewal-agent-templates/${id}/`, payload)
  return response.data
}

export const deleteTaxRenewalAgentTemplate = async (id: number | string) => {
  await http.delete(`/accounting/tax-renewal-agent-templates/${id}/`)
}

export const listTaxRenewalPdfDiagnostics = async () => {
  const response = await http.get<TaxRenewalPdfDiagnostic[]>('/accounting/tax-renewal-pdf-diagnostics/')
  return response.data
}

export const downloadTaxRenewalNumberedSample = async (templateKey: string) => {
  const response = await http.post<Blob>(
    '/accounting/tax-renewal-pdf-diagnostics/numbered_sample/',
    { template_key: templateKey },
    { responseType: 'blob' },
  )
  return {
    blob: response.data,
    contentDisposition: response.headers['content-disposition'] as string | undefined,
    fieldIndex: response.headers['x-field-index'] as string | undefined,
  }
}
