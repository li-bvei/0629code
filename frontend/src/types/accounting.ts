import type { PaginatedResponse } from './api'

export interface AccountingListParams {
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

export type AccountingVoucherType = 'invoice' | 'receipt'

export interface AccountingVoucherLineItem {
  item_name: string
  quantity: number | string
  unit_price: number | string
  line_total?: number | string
}

export interface AccountingVoucher {
  id: number
  voucher_type: AccountingVoucherType
  voucher_type_display: string
  voucher_number: string
  issue_date: string
  recipient_name: string
  recipient_postal_code: string
  recipient_address: string
  title: string
  amount: number | string
  tax_amount: number | string
  total_amount: number | string
  details: string
  line_items: AccountingVoucherLineItem[]
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
}

export interface AccountingVoucherPayload {
  voucher_type: AccountingVoucherType
  issue_date: string
  recipient_name?: string
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
  page_count: number
  pages: SeifuNoticePageInfo[]
  font_available: boolean
  font_error?: string | null
  template_error?: string | null
}

export interface SeifuNoticeTextItem {
  id?: string | number
  page: number
  text: string
  x: number
  y: number
  font_size?: number
  font_weight?: 'normal' | 'bold'
  color?: string
  font_family?: 'adobe_heiti'
}

export interface SeifuNoticeGeneratePayload {
  items: SeifuNoticeTextItem[]
}

export type SeifuNoticeRecordStatus = 'draft' | 'completed'

export interface SeifuNoticePdfRecord {
  id: number
  title: string
  status: SeifuNoticeRecordStatus
  text_items: SeifuNoticeTextItem[]
  text_count: number
  note: string
  created_by?: number | null
  created_by_username?: string
  created_at?: string
  updated_at?: string
}

export interface SeifuNoticeRecordPayload {
  title: string
  status?: SeifuNoticeRecordStatus
  text_items: SeifuNoticeTextItem[]
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
  representative_name?: string
  representative_kana?: string
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
}

export type AccountingPaginatedResponse<T> = PaginatedResponse<T>
