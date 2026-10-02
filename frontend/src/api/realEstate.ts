import http from '../services/http'
import type { PaginatedResponse } from '../types/api'
import type { BulkPreviewRequest, BulkUpdateRequest } from '../utils/realEstateBulk'
import type {
  AuditRow, BulkSelectionPreview, BulkUpdateResult, DryRunHistoryRow, DryRunReport, LedgerCorrection, LegalLedger, ProfitDistribution, RealEstateAccountingLink,
  RealEstateFile, RealEstateTransaction, RealEstateTransactionPayload, TransactionParty,
} from '../types/realEstate'

const base = '/real-estate'
const clean = (params: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined && v !== false))

export const listTransactions = async (params: Record<string, unknown>) =>
  (await http.get<PaginatedResponse<RealEstateTransaction>>(`${base}/transactions/`, { params: clean(params) })).data
export const getTransaction = async (id: number | string) =>
  (await http.get<RealEstateTransaction>(`${base}/transactions/${id}/`)).data
export const createTransaction = async (payload: RealEstateTransactionPayload) =>
  (await http.post<RealEstateTransaction>(`${base}/transactions/`, payload)).data
export const updateTransaction = async (id: number, payload: RealEstateTransactionPayload) =>
  (await http.patch<RealEstateTransaction>(`${base}/transactions/${id}/`, payload)).data
export const archiveTransaction = async (id: number, reason: string) =>
  (await http.post<RealEstateTransaction>(`${base}/transactions/${id}/archive/`, { reason })).data
export const restoreTransaction = async (id: number) =>
  (await http.post<RealEstateTransaction>(`${base}/transactions/${id}/restore/`)).data
export const listResponsibleSuggestions = async (q = '') =>
  (await http.get<{ name: string }[]>(`${base}/transactions/responsible-suggestions/`, { params: { q } })).data
export const exportTransactions = async (params: Record<string, unknown> = {}) =>
  (await http.get<Blob>(`${base}/transactions/export/`, { params: clean(params), responseType: 'blob' })).data
// 一括変更：対象の固定（書き込みなし。絞り込み結果の全件、または一覧で選択した記録）と、1 回の原子的な変更。
// 単票 PATCH を繰り返さない。実行は固定した選択トークンでしか行えない。
export const previewBulkSelection = async (filters: Record<string, unknown>) =>
  (await http.post<BulkSelectionPreview>(`${base}/transactions/bulk-preview/`, { filters: clean(filters) })).data
export const previewBulkSelectedRows = async (payload: BulkPreviewRequest) =>
  (await http.post<BulkSelectionPreview>(`${base}/transactions/bulk-preview/`, payload)).data
export const bulkUpdateTransactions = async (payload: BulkUpdateRequest) =>
  (await http.post<BulkUpdateResult>(`${base}/transactions/bulk-update/`, payload)).data
export const getTransactionAuditLog = async (id: number) =>
  (await http.get<AuditRow[]>(`${base}/transactions/${id}/audit-log/`)).data
export const ensureLedger = async (id: number) =>
  (await http.post<LegalLedger>(`${base}/transactions/${id}/ensure-ledger/`)).data

export const listParties = async (transaction: number) =>
  (await http.get<PaginatedResponse<TransactionParty>>(`${base}/parties/`, { params: { transaction, page_size: 100 } })).data.results
export const saveParty = async (id: number | null, payload: Partial<TransactionParty>) =>
  (id ? await http.patch<TransactionParty>(`${base}/parties/${id}/`, payload) : await http.post<TransactionParty>(`${base}/parties/`, payload)).data
export const deleteParty = async (id: number) => { await http.delete(`${base}/parties/${id}/`) }

export const getLedgerForTransaction = async (transaction: number) =>
  (await http.get<PaginatedResponse<LegalLedger>>(`${base}/ledgers/`, { params: { transaction } })).data.results[0] ?? null
export const updateLedger = async (id: number, payload: Partial<LegalLedger>) =>
  (await http.patch<LegalLedger>(`${base}/ledgers/${id}/`, payload)).data
export const lockLedger = async (id: number) => (await http.post<LegalLedger>(`${base}/ledgers/${id}/lock/`)).data
export const correctLedger = async (id: number, changes: Record<string, unknown>, reason: string) =>
  (await http.post<LegalLedger>(`${base}/ledgers/${id}/correct/`, { changes, reason })).data
export const setLegalHold = async (id: number, hold: boolean, reason: string) =>
  (await http.post<LegalLedger>(`${base}/ledgers/${id}/legal-hold/`, { hold, reason })).data
export const listCorrections = async (id: number) =>
  (await http.get<LedgerCorrection[]>(`${base}/ledgers/${id}/corrections/`)).data
export const closeFiscalYear = async (fiscalYear: number) =>
  (await http.post<{ fiscal_year: number; ledgers: number; newly_locked: number }>(`${base}/ledgers/close-year/`, { fiscal_year: fiscalYear })).data
export const exportLedgers = async (fiscalYear?: number) =>
  (await http.get<Blob>(`${base}/ledgers/export/`, { params: clean({ fiscal_year: fiscalYear }), responseType: 'blob' })).data

export const listFiles = async (transaction: number) =>
  (await http.get<PaginatedResponse<RealEstateFile>>(`${base}/files/`, { params: { transaction, page_size: 100 } })).data.results
export const uploadFile = async (transaction: number, kind: string, title: string, file: File) => {
  const form = new FormData()
  form.append('transaction', String(transaction))
  form.append('kind', kind)
  form.append('title', title)
  form.append('file', file)
  return (await http.post<RealEstateFile>(`${base}/files/`, form, { headers: { 'Content-Type': 'multipart/form-data' } })).data
}
export const downloadFile = async (id: number) => {
  const response = await http.get<Blob>(`${base}/files/${id}/download/`, { responseType: 'blob' })
  return { blob: response.data, contentDisposition: response.headers['content-disposition'] as string | undefined }
}

export const listAccountingLinks = async (transaction: number) =>
  (await http.get<PaginatedResponse<RealEstateAccountingLink>>(`${base}/accounting-links/`, { params: { transaction } })).data.results
export const createAccountingLink = async (payload: { transaction: number; income_source?: number | null; voucher?: number | null; note?: string }) =>
  (await http.post<RealEstateAccountingLink>(`${base}/accounting-links/`, payload)).data
export const deleteAccountingLink = async (id: number) => { await http.delete(`${base}/accounting-links/${id}/`) }

export const listProfits = async (transaction: number) =>
  (await http.get<PaginatedResponse<ProfitDistribution>>(`${base}/profit-distributions/`, { params: { transaction } })).data.results
export const saveProfit = async (id: number | null, payload: Partial<ProfitDistribution>) =>
  (id ? await http.patch<ProfitDistribution>(`${base}/profit-distributions/${id}/`, payload)
    : await http.post<ProfitDistribution>(`${base}/profit-distributions/`, payload)).data
export const settleProfit = async (id: number) => (await http.post<ProfitDistribution>(`${base}/profit-distributions/${id}/settle/`)).data
export const reopenProfit = async (id: number, reason: string) =>
  (await http.post<ProfitDistribution>(`${base}/profit-distributions/${id}/reopen/`, { reason })).data
export const deleteProfit = async (id: number) => { await http.delete(`${base}/profit-distributions/${id}/`) }

export const runDryRun = async (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return (await http.post<DryRunReport>(`${base}/imports/dry-run/`, form, { headers: { 'Content-Type': 'multipart/form-data' } })).data
}
export const listDryRuns = async () => (await http.get<DryRunHistoryRow[]>(`${base}/imports/`)).data
export const getDryRun = async (id: number) => (await http.get<DryRunReport>(`${base}/imports/${id}/`)).data
export const downloadDryRunReport = async (id: number) =>
  (await http.get<Blob>(`${base}/imports/${id}/error-report/`, { responseType: 'blob' })).data
