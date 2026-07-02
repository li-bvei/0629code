export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface ListParams {
  page?: number
  search?: string
  residence_status?: string
  customer?: number
  company?: number
  case?: number
}

export interface Customer {
  id: number
  name: string
  name_kana: string
  birth_date: string
  gender: string
  nationality: string
  residence_status: string
  residence_card_no: string
  residence_expiry: string | null
  passport_no: string
  passport_expiry: string | null
  email: string
  phone: string
  postal_code: string
  address: string
  my_number: string
  note: string
  cases_count: number
  created_at: string
  updated_at: string
}

export interface CreateCustomerPayload {
  name: string
  name_kana?: string
  birth_date: string
  gender?: string
  nationality?: string
  residence_status?: string
  residence_card_no?: string
  residence_expiry?: string | null
  passport_no?: string
  passport_expiry?: string | null
  email?: string
  phone?: string
  postal_code?: string
  address?: string
  my_number?: string
  note?: string
}

export type UpdateCustomerPayload = CreateCustomerPayload

export interface Company {
  id: number
  name: string
  name_kana: string
  representative_customer: number | null
  representative_customer_name: string
  representative_name: string
  representative_name_kana: string
  corporate_number: string
  corporate_registration_number: string
  email: string
  phone: string
  postal_code: string
  address: string
  fiscal_month: string
  bank_name: string
  bank_branch: string
  bank_account_type: string
  bank_account_number: string
  cases_count: number
  created_at: string
  updated_at: string
}

export interface CreateCompanyPayload {
  name: string
  name_kana?: string
  representative_customer?: number | null
  representative_name?: string
  representative_name_kana?: string
  corporate_number?: string
  corporate_registration_number?: string
  email?: string
  phone?: string
  postal_code?: string
  address?: string
  fiscal_month?: string
  bank_name?: string
  bank_branch?: string
  bank_account_type?: string
  bank_account_number?: string
}

export type UpdateCompanyPayload = CreateCompanyPayload

export interface CompanyStaff {
  id: number
  company: number
  company_name: string
  name: string
  name_kana: string
  position: string
  birth_date: string | null
  gender: string
  nationality: string
  residence_status: string
  residence_card_no: string
  residence_expiry: string | null
  passport_no: string
  passport_expiry: string | null
  phone: string
  email: string
  postal_code: string
  address: string
  my_number: string
  employment_start_date: string | null
  employment_end_date: string | null
  note: string
  created_at: string
  updated_at: string
}

export interface CompanyStaffPayload {
  company: number
  name: string
  name_kana?: string
  position?: string
  birth_date?: string | null
  gender?: string
  nationality?: string
  residence_status?: string
  residence_card_no?: string
  residence_expiry?: string | null
  passport_no?: string
  passport_expiry?: string | null
  phone?: string
  email?: string
  postal_code?: string
  address?: string
  my_number?: string
  employment_start_date?: string | null
  employment_end_date?: string | null
  note?: string
}

export interface Case {
  id: number
  case_number: string
  case_type: string
  status: string
  customer: number
  customer_name: string
  company: number | null
  company_name: string
  responsible_employee: number | null
  responsible_employee_name: string
  accepted_at: string | null
  applied_at: string | null
  result_notified_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface CasePayload {
  case_number?: string
  case_type: string
  status: string
  customer: number | null
  company?: number | null
  responsible_employee?: number | null
  accepted_at?: string | null
  applied_at?: string | null
  result_notified_at?: string | null
  completed_at?: string | null
}

export interface GenerateRemindersResponse {
  created_count: number
  skipped_count: number
  reminders: number[]
}

export interface DashboardDeadline {
  type: string
  target_type: string
  target_name: string
  deadline_label: string
  deadline_date: string
  days_left: number
  status: 'overdue' | 'today' | 'upcoming'
  case_id: number | null
  case_number: string
  case_type: string
}

export interface Employee {
  id: number
  name: string
  email: string
  phone: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Task {
  id: number
  case: number
  case_number: string
  title: string
  description: string
  status: string
  due_date: string | null
  created_at: string
  updated_at: string
}

export interface TaskPayload {
  case: number
  title: string
  description?: string
  status: string
  due_date?: string | null
}

export interface Reminder {
  id: number
  case: number
  case_number: string
  title: string
  remind_at: string
  note: string
  is_done: boolean
  created_at: string
  updated_at: string
}

export interface ReminderPayload {
  case: number
  title: string
  remind_at: string
  note?: string
  is_done?: boolean
}

export interface Timeline {
  id: number
  case: number
  case_number: string
  occurred_at: string | null
  title: string
  content: string
  is_visible_to_client: boolean
  created_at: string
  updated_at: string
}

export interface TimelinePayload {
  case: number
  occurred_at?: string | null
  title: string
  content?: string
  is_visible_to_client?: boolean
}

export interface Document {
  id: number
  case: number
  case_number: string
  title: string
  file: string | null
  file_url: string
  file_name: string
  file_path: string
  file_size: number | null
  content_type: string
  source: string
  is_visible_to_client: boolean
  created_at: string
  updated_at: string
}

export interface DocumentPayload {
  case: number
  title: string
  file?: File | null
  source?: string
  is_visible_to_client?: boolean
}

export interface FamilyMember {
  id: number
  customer: number
  customer_name: string
  relationship: string
  relationship_display: string
  name: string
  name_kana: string
  birth_date: string | null
  gender: string
  gender_display: string
  nationality: string
  residence_status: string
  residence_card_no: string
  residence_expiry: string | null
  phone: string
  postal_code: string
  address: string
  my_number: string
  is_dependent: boolean
  note: string
  created_at: string
  updated_at: string
}

export interface FamilyMemberPayload {
  customer: number
  relationship: string
  name: string
  name_kana?: string
  birth_date?: string | null
  gender?: string
  nationality?: string
  phone?: string
  postal_code?: string
  address?: string
  my_number?: string
  residence_status?: string
  residence_card_no?: string
  residence_expiry?: string | null
  is_dependent?: boolean
  note?: string
}

export interface ReceptionCustomerPayload {
  name: string
  name_kana?: string
  birth_date: string
  gender?: string
  nationality?: string
  email?: string
  phone?: string
  postal_code?: string
  address?: string
  my_number?: string
  residence_status?: string
  residence_card_no?: string
  residence_expiry?: string | null
  passport_no?: string
  passport_expiry?: string | null
  note?: string
}

export interface ReceptionFamilyMemberPayload {
  relationship?: string
  name?: string
  name_kana?: string
  birth_date?: string | null
  gender?: string
  nationality?: string
  phone?: string
  postal_code?: string
  address?: string
  my_number?: string
  residence_status?: string
  residence_card_no?: string
  residence_expiry?: string | null
  is_dependent?: boolean
  note?: string
}

export interface ReceptionCompanyPayload {
  name?: string
  name_kana?: string
  representative_customer?: number | null
  representative_customer_is_current_customer?: boolean
  representative_name?: string
  representative_name_kana?: string
  corporate_number?: string
  corporate_registration_number?: string
  email?: string
  phone?: string
  postal_code?: string
  address?: string
  fiscal_month?: string
  bank_name?: string
  bank_branch?: string
  bank_account_type?: string
  bank_account_number?: string
}

export interface ReceptionCasePayload {
  case_type: string
  status: string
  responsible_employee?: number | null
  accepted_at?: string | null
}

export interface ReceptionPayload {
  customer: ReceptionCustomerPayload
  family_members: ReceptionFamilyMemberPayload[]
  company: ReceptionCompanyPayload
  case: ReceptionCasePayload
}

export interface ReceptionResponse {
  customer: number
  company: number | null
  case: number
  case_number: string
  family_members: number[]
}
