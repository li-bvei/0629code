import type { PaginatedResponse } from './api'

export interface AccountingListParams {
  // 関連案件で絞り込み（P2）
  case?: number | string
  customer?: number | string
  company?: number | string
  // 帳票の状態（'unset' は状態未設定の旧データ）
  status?: string
  page?: number
  page_size?: number
  search?: string
  start_date?: string | null
  end_date?: string | null
  issue_date_from?: string | null
  issue_date_to?: string | null
  voucher_type?: string
  recipient_name?: string
  title?: string
  keyword?: string
  amount_min?: number | string | null
  amount_max?: number | string | null
  payment_due_date_from?: string | null
  payment_due_date_to?: string | null
  include_inactive?: boolean | string | number
  project?: number | string
  category?: string
  payment_method?: string
  purpose?: string
  is_active?: boolean | string
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
  // 歴史互換の項目。現在の UI では表示・送信しない（報銷フローではない）
  is_reimbursed?: boolean
  is_exported: boolean
  // 所有者（後端が設定。フロントからは送らない）
  owner?: number | null
  owner_username?: string
  owner_name?: string
  // 任意の関連（P2）
  customer?: number | null
  company?: number | null
  case?: number | null
  case_number?: string
  customer_name?: string
  company_name?: string
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
  is_exported: boolean
  customer?: number | null
  company?: number | null
  case?: number | null
  /** 利用者が「この場所とカテゴリの対応を記憶する」を選んだ場合だけ true（保存項目ではない。本人用の規則になる） */
  remember_place_category?: boolean
}

export interface ExpenseSummary {
  target_count: number
  // 全体の会計権限が無い場合、収入・残高系は null（会社の残高として表示しない）
  total_income: number | string | null
  total_expense: number | string
  balance: number | string | null
  opening_balance?: number | string | null
  period_income_total?: number | string | null
  period_expense_total?: number | string | null
  filtered_expense_total?: number | string
  filtered_net?: number | string | null
  balance_visible?: boolean
  expense_scope?: 'own' | 'all'
}

export interface ExpenseTargetChartItem {
  name: string
  amount: number | string
}

export interface AccountingProjectChartItem {
  project_id: number
  project_name: string
  income: number | string
  expense: number | string
  balance: number | string
}

export interface AccountingProjectReportSummary {
  total_income: number | string
  project_count: number
  total_expense: number | string
  balance: number | string
}

export interface AccountingProjectReport {
  summary: AccountingProjectReportSummary
  project_chart: AccountingProjectChartItem[]
  expense_category_chart: ExpenseTargetChartItem[]
}

export interface IncomeSource {
  id: number
  source_date: string
  source_target: string
  amount: string | number
  note: string
  is_exported: boolean
  // 任意の関連（P2）
  customer?: number | null
  company?: number | null
  case?: number | null
  case_number?: string
  customer_name?: string
  company_name?: string
  created_at?: string
  updated_at?: string
}

export interface IncomeSourcePayload {
  source_date: string
  source_target?: string
  amount: string | number
  note?: string
  is_exported: boolean
  customer?: number | null
  company?: number | null
  case?: number | null
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
  monthly_income_source_total: number | string | null
  monthly_vehicle_km_total: number | string | null
  // 歴史互換：API は返すが UI では表示しない
  monthly_unreimbursed_total?: number | string
  total_expense_amount: number | string
  total_income_source_amount: number | string | null
  current_balance: number | string | null
  balance_visible?: boolean
  income_visible?: boolean
  vehicle_visible?: boolean
  expense_scope?: 'own' | 'all'
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
  income_total?: number | string
  expense_total?: number | string
  balance?: number | string
  income_count?: number
  expense_count?: number
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

export type AccountingVoucherType = 'invoice' | 'receipt'
export type AccountingVoucherTaxCategory = 'tax_10' | 'tax_8' | 'non_taxable'
export type AccountingVoucherPriceType = 'tax_included' | 'tax_excluded'

export interface AccountingVoucherLineItem {
  item_name: string
  quantity: number | string
  /** 単位（件・時間・通 など。任意） */
  unit?: string
  unit_price: number | string
  /** 行ごとの備考（任意） */
  note?: string
  line_total?: number | string
  tax_category?: AccountingVoucherTaxCategory
  tax_category_label?: string
  price_type?: AccountingVoucherPriceType
  tax_excluded_amount?: number | string
  tax_amount?: number | string
  /** P4：行の識別子（後端が作る。保存済みの行を送り返すときにそのまま返す） */
  line_key?: string
  /** P4：選んだサービス項目（手入力の行には無い） */
  service_item_id?: number | null
  /** P4：選んだ時点のサービス項目の内容（後端が作る。底価は含まない） */
  service?: ServiceItemLineSnapshot | null
}

export type ServiceProfessionalType = '' | 'gyousei' | 'tax_accountant' | 'judicial_scrivener' | 'labor_consultant' | 'other'

export type ServicePriceStatus = 'provisional' | 'confirmed'

export interface ServiceItemLineSnapshot {
  id: number
  category: string
  name: string
  default_price: number | null
  price_type: AccountingVoucherPriceType
  tax_category: AccountingVoucherTaxCategory
  unit: string
  professional_type: ServiceProfessionalType
  professional_type_display: string
  selected_at?: string
  /** P6：選んだ時点の価格状態（暫定価格から作った行は provisional のまま残る） */
  price_status?: ServicePriceStatus
  code?: string | null
}

/** 委託底価（社内）。底価権限者への応答にだけ含まれる */
export interface InternalLineCost {
  line_key: string
  service_item_id: number
  floor_price: number | null
  professional_type: ServiceProfessionalType
  captured_at: string
}

export interface ServiceItem {
  id: number
  category: string
  name: string
  default_price: string | null
  price_type: AccountingVoucherPriceType
  price_type_display: string
  /** 底価権限者だけに返る */
  floor_price?: string | null
  professional_type: ServiceProfessionalType
  professional_type_display: string
  tax_category: AccountingVoucherTaxCategory
  tax_category_display: string
  unit: string
  is_active: boolean
  note: string
  sort_order: number
  is_used: boolean
  /** P6：基本項目の固定コード（初期データ）。手で作った項目は null */
  code: string | null
  price_status: ServicePriceStatus
  price_status_display: string
  price_confirmed_at: string | null
  price_confirmed_by_name: string
  created_at: string
  updated_at: string
}

export interface ServiceItemPayload {
  category?: string
  name?: string
  default_price?: number | string | null
  price_type?: AccountingVoucherPriceType
  floor_price?: number | string | null
  professional_type?: ServiceProfessionalType
  tax_category?: AccountingVoucherTaxCategory
  unit?: string
  is_active?: boolean
  note?: string
  sort_order?: number
  version?: string
}

export interface InternalCostsResponse {
  current: InternalLineCost[]
  issued_versions: { version: number; document_number: string; line_costs: InternalLineCost[]; created_at: string }[]
}

export interface AccountingVoucherTaxSummary {
  subtotal_10: number | string
  tax_10: number | string
  subtotal_8: number | string
  tax_8: number | string
  subtotal_non_taxable: number | string
  subtotal: number | string
  tax_total: number | string
  total: number | string
}

export interface AccountingVoucher extends BusinessDocumentCommon {
  id: number
  voucher_type: AccountingVoucherType
  voucher_type_display: string
  voucher_number: string
  issue_date: string
  recipient_name: string
  recipient_honorific: string
  recipient_postal_code: string
  recipient_address: string
  title: string
  amount: number | string
  tax_amount: number | string
  total_amount: number | string
  details: string
  line_items: AccountingVoucherLineItem[]
  tax_summary?: AccountingVoucherTaxSummary
  note: string
  payment_due_date: string | null
  payment_method: string
  issuer_name: string
  issuer_postal_code: string
  issuer_address: string
  issuer_tel: string
  issuer_registration_number: string
  bank_info: string
  created_by?: number | null
  created_by_username?: string
  created_at?: string
  updated_at?: string
  // P2-C11：請求書・領収書は別々の状態列を持つ（自分の種別の列だけを使う。空は旧データ）
  invoice_status: InvoiceStatus
  receipt_status: ReceiptStatus
  paid_date: string | null
  source_estimate?: number | null
  source_contract?: number | null
  source_invoice?: number | null
  source_estimate_number?: string
  source_contract_number?: string
  source_invoice_number?: string
}


export type InvoiceStatus = '' | 'draft' | 'issued' | 'sent' | 'paid' | 'cancelled'
export type ReceiptStatus = '' | 'draft' | 'issued' | 'voided'
export type EstimateStatus = 'draft' | 'submitted' | 'accepted' | 'declined' | 'cancelled'
export type ContractStatus = 'draft' | 'sent' | 'signed' | 'terminated' | 'cancelled'
export type BusinessDocumentKind = 'estimate' | 'contract' | 'invoice' | 'receipt'
export type BusinessDocumentEndpoint = 'estimates' | 'contracts' | 'vouchers'

// 帳票共通の表示補助（後端が帳票ごとの Workflow から作る）
export interface BusinessDocumentCommon {
  document_kind: BusinessDocumentKind
  status_value: string
  status_display: string
  is_editable: boolean
  allowed_transitions: { value: string; label: string }[]
  status_changed_at: string | null
  issued_snapshot: Record<string, unknown>
  case: number | null
  customer: number | null
  company: number | null
  case_number: string
  customer_name: string
  company_name: string
  updated_by?: number | null
  updated_at?: string
  /** P4：底価権限者への応答にだけ含まれる */
  internal_line_costs?: InternalLineCost[]
}

interface BusinessDocumentBase extends BusinessDocumentCommon {
  id: number
  issue_date: string
  recipient_name: string
  recipient_honorific: string
  recipient_postal_code: string
  recipient_address: string
  title: string
  line_items: AccountingVoucherLineItem[]
  amount: number | string
  tax_amount: number | string
  total_amount: number | string
  tax_summary?: AccountingVoucherTaxSummary
  note: string
  issuer_name: string
  issuer_postal_code: string
  issuer_address: string
  issuer_tel: string
  issuer_registration_number: string
  created_at?: string
  updated_at?: string
}

export interface Estimate extends BusinessDocumentBase {
  estimate_number: string
  status: EstimateStatus
  valid_until: string | null
}

export interface Contract extends BusinessDocumentBase {
  contract_number: string
  status: ContractStatus
  start_date: string | null
  end_date: string | null
  payment_terms: string
  body: string
  signed_date: string | null
  source_estimate: number | null
  source_estimate_number?: string
}

export interface BusinessDocumentPayload {
  issue_date: string
  recipient_name?: string
  recipient_honorific?: string
  recipient_postal_code?: string
  recipient_address?: string
  title?: string
  line_items?: AccountingVoucherLineItem[]
  note?: string
  issuer_name?: string
  issuer_postal_code?: string
  issuer_address?: string
  issuer_tel?: string
  issuer_registration_number?: string
  case?: number | null
  customer?: number | null
  company?: number | null
  valid_until?: string | null
  start_date?: string | null
  end_date?: string | null
  payment_terms?: string
  body?: string
  /** P4：画面で見ていた版（updated_at）。他の人の保存と衝突したら 409 */
  version?: string
}

export interface VoucherLinkRow {
  id: number
  number: string
  issue_date: string
  title: string
  recipient_name: string
  status: string
  status_display: string
  total_amount: number
}

export type VoucherLinkBlock = { visible: false } | { visible: true; count: number; items: VoucherLinkRow[] }

export interface VoucherLinks {
  estimates: VoucherLinkBlock
  contracts: VoucherLinkBlock
  invoices: VoucherLinkBlock
  receipts: VoucherLinkBlock
}

export interface AccountingVoucherPayload {
  voucher_type: AccountingVoucherType
  issue_date: string
  recipient_name?: string
  recipient_honorific?: string
  recipient_postal_code?: string
  recipient_address?: string
  title?: string
  amount: number | string
  tax_amount?: number | string
  details?: string
  line_items?: AccountingVoucherLineItem[]
  note?: string
  payment_due_date?: string | null
  payment_method?: string
  issuer_name?: string
  issuer_postal_code?: string
  issuer_address?: string
  issuer_tel?: string
  issuer_registration_number?: string
  bank_info?: string
  case?: number | null
  customer?: number | null
  company?: number | null
  /** P4：画面で見ていた版（updated_at） */
  version?: string
}

export interface VoucherItemTemplate {
  id: number
  name: string
  default_unit_price?: number | string | null
  is_active: boolean
  sort_order: number
  created_at?: string
  updated_at?: string
}

export interface VoucherItemTemplatePayload {
  name: string
  default_unit_price?: number | string | null
  is_active?: boolean
  sort_order?: number
}

export type VisaReturnGender = '' | 'male' | 'female'
export type VisaReturnMaritalStatus = '' | 'single' | 'married' | 'divorced' | 'widowed'
export type VisaReturnYesNo = 'yes' | 'no'

export interface VisaReturnFormData {
  [key: string]: string
  pinyin_name1: string
  pinyin_name2: string
  chinese_name1: string
  chinese_name2: string
  used_name1: string
  used_name2: string
  othernationality: string
  birth_place: string
  chinese_id: string
  passport_address: string
  passport_a: string
  zailiu_number: string
  entry_port: string
  airline: string
  entry_time1: string
  entry_time2: string
  entry_time3: string
  registered_address: string
  current_address: string
  home_address2: string
  home_phone: string
  workplace_name: string
  workplace_address: string
  workplace_phone: string
  hotel: string
  hotel_phone: string
  hotel_address: string
  last: string
  job_title2: string
  guarantor_name_en: string
  guarantor_address_en: string
  guarantor_birth_date: string
  guarantor_nationality: string
  guarantor_visa_status: string
  gender2: VisaReturnGender
  same: string
  x1: VisaReturnYesNo
  x2: VisaReturnYesNo
  x3: VisaReturnYesNo
  x4: VisaReturnYesNo
  x5: VisaReturnYesNo
  x6: VisaReturnYesNo
}

export interface VisaGuarantorTemplate {
  id: number
  name: string
  guarantor_name: string
  guarantor_name_en: string
  guarantor_phone: string
  guarantor_address: string
  guarantor_address_en: string
  guarantor_birth_date: string | null
  guarantor_nationality: string
  guarantor_visa_status: string
  guarantor_occupation: string
  guarantor_relationship: string
  guarantor_company_name: string
  note: string
  is_active: boolean
  sort_order: number
  created_at?: string
  updated_at?: string
}

export type VisaGuarantorTemplatePayload = Omit<VisaGuarantorTemplate, 'id' | 'created_at' | 'updated_at'>

export interface SeifuNoticePageInfo {
  page: number
  width: number
  height: number
}

export interface SeifuNoticeTemplateInfo {
  template_key: string
  template_name: string
  course_years: string
  enrollment_period: string
  notice_number_suffix?: string
  recipient_name_max_length?: number
  template_version?: string
  font_version?: string
  page_count: number
  pages: SeifuNoticePageInfo[]
  font_available: boolean
  font_error?: string | null
  template_error?: string | null
}

export type SeifuNoticeRecordStatus = 'draft' | 'completed'

/** P5：PDF の生成記録（成功のみ）。ダウンロードは download/ から */
export interface SeifuNoticeGeneration {
  id: number
  record: number | null
  status: 'success'
  recipient_name: string
  permit_number: string
  notice_number: string
  issue_date: string
  template_key: string
  template_version: string
  font_version: string
  method: string
  file_sha256: string
  file_size: number
  created_by: number | null
  created_by_username: string
  created_at: string
  /** 同じ操作の再送で、既存の生成結果を返したとき */
  replayed?: boolean
}

export interface SeifuNoticePdfRecord {
  id: number
  title: string
  status: SeifuNoticeRecordStatus
  recipient_name: string | null
  permit_number: string | null
  notice_number: string
  issue_date: string | null
  template_key: string | null
  template_name: string
  /** P5 以前の任意文字の記録（読み取り専用。新しい生成には使わない） */
  text_items: unknown[]
  text_count: number
  is_legacy: boolean
  latest_generation: SeifuNoticeGeneration | null
  generation_count: number
  note: string
  created_by?: number | null
  created_by_username?: string
  created_at?: string
  updated_at?: string
}

export interface SeifuNoticeRecordPayload {
  title: string
  status?: SeifuNoticeRecordStatus
  recipient_name: string
  permit_number: string
  issue_date: string
  note?: string
}

export type TaxRenewalCategory = 'renewal' | 'pension'
export type TaxRenewalStatus = 'draft' | 'completed'
export type TaxRenewalCondition = 'none' | 'has_employees' | 'has_dependents'

export interface TaxRenewalTemplate {
  key: string
  name: string
  category: TaxRenewalCategory
  filename: string
  file_path?: string
  file_exists: boolean
  condition: TaxRenewalCondition
  order: number
  required_fields?: string[]
}

export interface TaxRenewalPdfFieldRect {
  x0: number
  y0: number
  x1: number
  y1: number
  width: number
  height: number
}

export interface TaxRenewalPdfField {
  index: number
  field_name: string
  field_type: string
  page: number
  rect: TaxRenewalPdfFieldRect | null
  options: string[]
}

export interface TaxRenewalPdfPageInfo {
  page: number
  width: number
  height: number
}

export interface TaxRenewalPdfDiagnostic {
  template_key: string
  template_name: string
  filename: string
  file_exists: boolean
  page_count: number
  pages: TaxRenewalPdfPageInfo[]
  has_acroform: boolean
  field_count: number
  fields: TaxRenewalPdfField[]
}

export interface TaxRenewalDependent {
  name?: string
  kana?: string
  birth_date?: string | null
  relationship?: string
  my_number?: string
  address?: string
}

export interface TaxRenewalFormData {
  company_name?: string
  company_number?: string
  company_address?: string
  company_phone?: string
  pension_number?: string
  representative_name?: string
  representative_kana?: string
  representative_postal_code?: string
  representative_address?: string
  representative_birth_date?: string | null
  applicant_name?: string
  applicant_kana?: string
  applicant_address?: string
  applicant_phone?: string
  applicant_birth_date?: string | null
  agent_name?: string
  agent_kana?: string
  agent_address?: string
  agent_phone?: string
  agent_company_name?: string
  agent_position?: string
  agent_template_id?: number | null
  agent_snapshot?: Partial<TaxRenewalAgentTemplate> | null
  tax_office_name?: string
  osaka_city_ward?: string
  osaka_prefecture_office?: string
  fiscal_year?: string
  fiscal_period_start?: string | null
  fiscal_period_end?: string | null
  fiscal_start_year?: number | string | null
  fiscal_start_month?: number | string | null
  fiscal_start_day?: number | string | null
  fiscal_end_year?: number | string | null
  fiscal_end_month?: number | string | null
  fiscal_end_day?: number | string | null
  fiscal_start_year_jp?: string
  fiscal_end_year_jp?: string
  certificate_type?: string
  quantity?: string | number
  employee_name?: string
  employee_kana?: string
  employee_birth_date?: string | null
  employee_address?: string
  employee_phone?: string
  employee_my_number?: string
  employment_start_date?: string | null
  salary_amount?: string | number
  establishment_symbol?: string
  establishment_number?: string
  social_insurance_symbol?: string
  social_insurance_office_number?: string
  application_reason?: string
  representative_position?: string
  agent_relationship?: string
  dependents?: TaxRenewalDependent[]
  submit_date?: string | null
  note?: string
}

export interface TaxRenewalVoucherRecord {
  id: number
  title: string
  category: TaxRenewalCategory
  category_display?: string
  case?: number | null
  case_number?: string
  company?: number | null
  company_name?: string
  customer?: number | null
  customer_name?: string
  employee?: number | null
  employee_name?: string
  status: TaxRenewalStatus
  status_display?: string
  has_employees: boolean
  has_dependents: boolean
  selected_templates: string[]
  selected_template_count: number
  form_data: TaxRenewalFormData
  generated_files: string[]
  note: string
  created_by?: number | null
  created_by_username?: string
  created_at?: string
  updated_at?: string
}

export interface TaxRenewalVoucherPayload {
  title: string
  category: TaxRenewalCategory
  case?: number | null
  company?: number | null
  customer?: number | null
  employee?: number | null
  status?: TaxRenewalStatus
  has_employees: boolean
  has_dependents: boolean
  selected_templates: string[]
  form_data: TaxRenewalFormData
  generated_files?: string[]
  note?: string
}

export interface TaxRenewalGeneratePdfPayload {
  template_key?: string
}

export interface TaxRenewalAgentTemplate {
  id: number
  name: string
  agent_name: string
  agent_kana: string
  agent_address: string
  agent_phone: string
  agent_company_name: string
  agent_position: string
  note: string
  is_active: boolean
  sort_order: number
  created_at?: string
  updated_at?: string
}

export interface TaxRenewalAgentTemplatePayload {
  name: string
  agent_name: string
  agent_kana?: string
  agent_address?: string
  agent_phone?: string
  agent_company_name?: string
  agent_position?: string
  note?: string
  is_active?: boolean
  sort_order?: number
}

export interface VisaReturnApplication {
  id: number
  applicant_name: string
  nationality: string
  birth_date: string | null
  gender: VisaReturnGender
  marital_status: VisaReturnMaritalStatus
  passport_number: string
  passport_issue_date: string | null
  passport_expiry_date: string | null
  residence_status: string
  address: string
  phone: string
  email: string
  occupation: string
  guarantor_name: string
  guarantor_phone: string
  guarantor_address: string
  guarantor_relationship: string
  guarantor_occupation: string
  guarantor_snapshot: Record<string, unknown>
  /** 主流程で選んだ在日担保人テンプレート（スナップショットは後端が作る） */
  guarantor_template?: number | null
  guarantor_template_name?: string
  form_data: Partial<VisaReturnFormData> & Record<string, unknown>
  note: string
  created_by?: number | null
  created_at?: string
  updated_at?: string
}

export interface VisaReturnApplicationPayload {
  applicant_name?: string
  nationality?: string
  birth_date?: string | null
  gender?: VisaReturnGender
  marital_status?: VisaReturnMaritalStatus
  passport_number?: string
  passport_issue_date?: string | null
  passport_expiry_date?: string | null
  residence_status?: string
  address?: string
  phone?: string
  email?: string
  occupation?: string
  guarantor_name?: string
  guarantor_phone?: string
  guarantor_address?: string
  guarantor_relationship?: string
  guarantor_occupation?: string
  guarantor_snapshot?: Record<string, unknown>
  form_data?: Partial<VisaReturnFormData> & Record<string, unknown>
  note?: string
  guarantor_template?: number | null
}

export type AccountingPaginatedResponse<T> = PaginatedResponse<T>

// --- P2：カテゴリ入力支援・案件の会計要約 ---
export interface ExpenseCategorySuggestions {
  query: string
  matches: Array<{ name: string; source: 'master' | 'history'; count: number }>
  normalized: { input: string; suggestion: string; reason: string } | null
  recommendations: Array<{ name: string; reason: string; score: number }>
  // 文字規則（場所などに含まれる文字 → カテゴリ）からの提案。採用するまで入力値は変わらない。
  place_recommendations: PlaceCategoryRecommendation[]
  source_scope: 'own_history'
}

export interface PlaceCategoryRecommendation {
  name: string
  match_field: 'place' | 'expense_target' | 'note'
  pattern: string
  /** office＝事務所共通の規則、personal＝自分が記憶した規則 */
  scope: 'office' | 'personal'
  reason: string
  requires_confirmation: boolean
}

export interface ExpenseCategoryRule {
  id: number
  pattern: string
  match_field: 'place' | 'expense_target' | 'note'
  match_field_display: string
  expense_category: number
  expense_category_name: string
  priority: number
  is_active: boolean
  source: 'seed' | 'manual' | 'user_confirmed'
  source_display: string
  /** personal＝記憶した本人だけに効く。事務所共通への変更は promote だけ */
  scope: 'office' | 'personal'
  owner_name: string
  created_at: string
  updated_at: string
}

export type ExpenseCategoryRulePayload = Pick<ExpenseCategoryRule, 'pattern' | 'match_field' | 'expense_category' | 'priority' | 'is_active'>

export interface CaseAccountingSummary {
  case_id: number
  expense: { visible: boolean; scope?: 'own' | 'all'; count?: number; total?: number
    recent?: Array<{ id: number; expense_date: string; category: string; amount: number; is_own: boolean }> }
  income: { visible: boolean; count?: number; total?: number
    recent?: Array<{ id: number; source_date: string; source_target: string; amount: number }> }
  tax_renewal: { visible: boolean; count?: number; recent?: Array<{ id: number; title: string; status: string }> }
}

// --- 2026-10 P1：請求書・領収書の状態履歴、返签 visa 表の生成記録 ---
export interface VoucherStatusHistoryRow {
  id: number
  document_kind: 'invoice' | 'receipt'
  voucher_number: string
  from_status: string
  from_status_display: string
  to_status: string
  to_status_display: string
  version: number
  reason: string
  snapshot: Record<string, unknown> & { total_amount?: number; line_items?: AccountingVoucherLineItem[] }
  changed_by_name: string
  changed_at: string
}

export interface VisaCheckField {
  key: string
  label: string
  value: string
  source: 'applicant' | 'template' | 'manual' | ''
}

export interface VisaCheckResult {
  ready: boolean
  missing: { field: string; label: string }[]
  fields: VisaCheckField[]
  pdf_template: { method: string; available: boolean }
  guarantor_template: { id: number | null; name: string; version: string; is_active: boolean; updated_since_selected: boolean }
}

export interface VisaPdfGeneration {
  id: number
  application: number
  status: 'success' | 'failed'
  status_display: string
  method: string
  method_display: string
  template_name: string
  template_version: string
  guarantor_template: number | null
  guarantor_template_name: string
  guarantor_template_version: string
  file_sha256: string
  file_size: number | null
  error_code: string
  error_message: string
  created_by_name: string
  created_at: string
  /** 成功しファイルが実在するときだけ値がある */
  download_url: string | null
}
