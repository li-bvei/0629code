// 不動産（P3）。表示用の型で、権限の判定は常に後端（BusinessAccessPolicy）。
export type RealEstateType = 'rental' | 'sale'
export type RealEstateStage = 'inquiry' | 'viewing' | 'application' | 'screening' | 'contract' | 'settled' | 'cancelled'

export interface RealEstateTransaction {
  id: number
  transaction_number: string
  transaction_type: RealEstateType
  transaction_type_display: string
  stage: RealEstateStage
  stage_display: string
  party_name: string
  customer: number | null
  customer_name: string
  property_name: string
  room_number: string
  property_address: string
  property_kind: string
  area_sqm: string | null
  management_company_name: string
  management_company: number | null
  management_company_ref_name: string
  responsible_employee: number | null
  responsible_employee_name: string
  transaction_date: string | null
  rent_or_price: string | null
  brokerage_fee: string | null
  advertising_fee: string | null
  handling_fee: string | null
  source_billed_to_sunrise_amount: string | null
  source_billed_to_client_amount: string | null
  source_sunrise_invoice_amount: string | null
  payment_status: string
  payment_status_display: string
  payment_date: string | null
  transfer_status: string
  transfer_status_display: string
  note: string
  missing_items: string[]
  has_ledger: boolean
  ledger_locked: boolean
  created_at: string
  updated_at: string
}

export type RealEstateTransactionPayload = Partial<Omit<RealEstateTransaction,
  'id' | 'transaction_number' | 'missing_items' | 'has_ledger' | 'ledger_locked' | 'created_at' | 'updated_at'>>

export interface TransactionParty {
  id: number
  transaction: number
  role: string
  role_display: string
  name: string
  address: string
  license_number: string
  customer: number | null
  customer_name: string
  company: number | null
  company_name: string
  note: string
}

export interface LegalLedger {
  id: number
  transaction: number
  transaction_number: string
  transaction_form: string
  transaction_form_display: string
  transaction_type: RealEstateType
  transaction_type_display: string
  property_location: string
  property_name: string
  room_number: string
  area_sqm: string | null
  building_outline: string
  rent_or_price: string | null
  remuneration: string | null
  advertising_fee: string | null
  handling_fee: string | null
  special_terms: string
  contract_date: string | null
  fiscal_year: number | null
  fiscal_year_end_month: number | null
  fiscal_year_closed_at: string | null
  retention_years: number
  retention_until: string | null
  retention_due: boolean
  legal_hold: boolean
  legal_hold_reason: string
  is_locked: boolean
  locked_at: string | null
  version: number
  parties: TransactionParty[]
}

export interface LedgerCorrection {
  id: number
  version: number
  changes: Record<string, [unknown, unknown]>
  reason: string
  corrected_by_name: string
  corrected_at: string
}

export interface RealEstateFile {
  id: number
  transaction: number
  kind: string
  kind_display: string
  title: string
  file_name: string
  file_size: number | null
  document: number | null
  document_title: string
  uploaded_by_name: string
  created_at: string
  has_file: boolean
}

export interface RealEstateAccountingLink {
  id: number
  transaction: number
  income_source: number | null
  voucher: number | null
  note: string
  income_summary: { date: string; target: string; amount: number } | null
  voucher_summary: { number: string; type: string; total: number } | null
}

export interface ProfitDistribution {
  id: number
  transaction: number
  recipient_name: string
  recipient_employee: number | null
  method: 'fixed' | 'ratio'
  method_display: string
  base_amount: string
  ratio_percent: string | null
  fixed_amount: string | null
  amount: string
  status: 'draft' | 'settled'
  status_display: string
  settled_at: string | null
  note: string
}

export interface AuditRow {
  occurred_at: string
  user: string
  action: string
  object_type: string
  result: string
  reason: string
  changes: Record<string, unknown>
}

export interface DryRunRow {
  row_number: number
  source: { file: string; sheet: string; row: number }
  raw: Record<string, string>
  values: Record<string, string | number | null>
  errors: { column: string; raw?: string; message: string }[]
  notes: { column: string; code: string; message: string }[]
  to_complete: string[]
  duplicate_in_file_rows: number[]
  duplicate_existing: { id: number; number: string }[]
  candidates: {
    customer: { id: number; name: string }[]
    management_company: { id: number; name: string }[]
    property: { id: number; number: string; property_name: string; room_number: string }[]
    responsible: { id: number; name: string }[]
  }
}

export interface DryRunReport {
  id: number
  file_name: string
  sheet: string
  sheets_found: string[]
  headers: string[]
  unknown_columns: string[]
  missing_columns: string[]
  column_stats: Record<string, { empty: number; dash: number; zero: number; value: number }>
  summary: Record<string, number>
  results: DryRunRow[]
  previous_runs?: number[]
}

export interface DryRunHistoryRow {
  id: number
  file_name: string
  sheet: string
  summary: Record<string, number>
  created_at: string
}

export const STAGE_OPTIONS: { value: RealEstateStage; label: string }[] = [
  { value: 'inquiry', label: '問い合わせ' }, { value: 'viewing', label: '内見' }, { value: 'application', label: '申込' },
  { value: 'screening', label: '審査' }, { value: 'contract', label: '契約' }, { value: 'settled', label: '完了' },
  { value: 'cancelled', label: 'キャンセル' },
]
export const TYPE_OPTIONS = [{ value: 'rental', label: '賃貸' }, { value: 'sale', label: '売買（記録のみ）' }]
export const PAYMENT_OPTIONS = [
  { value: 'unset', label: '未設定' }, { value: 'unpaid', label: '未払い' }, { value: 'paid', label: '支払済み' },
  { value: 'offset', label: '相殺' },
]
export const TRANSFER_OPTIONS = [{ value: '', label: '未設定' }, { value: 'pending', label: '振込待ち' }, { value: 'transferred', label: '振込済み' }]
export const PARTY_ROLE_OPTIONS = [
  { value: 'lessor', label: '貸主' }, { value: 'lessee', label: '借主' }, { value: 'seller', label: '売主' },
  { value: 'buyer', label: '買主' }, { value: 'agent', label: '代理人' }, { value: 'broker', label: '媒介業者' },
  { value: 'co_broker', label: '共同の宅建業者' },
]
export const FILE_KIND_OPTIONS = [
  { value: 'brokerage_contract', label: '媒介契約書' }, { value: 'important_matters', label: '重要事項説明書' },
  { value: 'contract', label: '契約書' }, { value: 'identity', label: '本人確認書類' }, { value: 'other', label: 'その他' },
]
export const LEDGER_FORM_OPTIONS = [{ value: 'brokerage', label: '媒介' }, { value: 'agency', label: '代理' }, { value: 'own', label: '自ら当事者' }]
