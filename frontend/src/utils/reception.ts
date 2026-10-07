// 新規受付（照合なしの直接入力）：送信内容の組み立てと、後端の項目エラーの表示名。
import type { ReceptionCreatePayload, ReceptionPayload } from '../types/api'
import { describeApiErrors, fieldErrorMap } from './apiErrors'

export type ReceptionCompanyMode = 'none' | 'existing' | 'new'

const hasAnyValue = (data: Record<string, unknown>) =>
  Object.values(data).some((v) => v !== '' && v !== null && v !== undefined && v !== false)

// この画面は常に「新規顧客＋業務情報」を送る。既存顧客の照合・再利用（existing_customer_id）は送らない。
export interface ReceptionServiceSelection {
  service_item: number
  quantity: number | string
}

export const buildReceptionPayload = (
  form: ReceptionPayload,
  options: {
    requestId: string
    companyMode: ReceptionCompanyMode
    existingCompanyId: number | null
    /** P4：案件種別が申請区分を必要としない場合は送らない（false のときだけ） */
    requiresCategory?: boolean
    /** P4：サービス項目（参考。任意・複数可）。価格はマスタから後端が写す */
    serviceItems?: ReceptionServiceSelection[]
  },
): ReceptionCreatePayload => {
  const payload: ReceptionCreatePayload = {
    request_id: options.requestId,
    customer: { ...form.customer, name: form.customer.name.trim() },
    family_members: form.family_members
      .filter((member) => hasAnyValue(member as Record<string, unknown>))
      .map((member) => ({
        ...member,
        postal_code: member.postal_code || form.customer.postal_code || '',
        address: member.address || form.customer.address || '',
      })),
    company: { ...form.company },
    case: {
      case_type_master: form.case.case_type_master,
      application_category: options.requiresCategory === false ? (form.case.application_category || null) : form.case.application_category,
      responsible_employee: form.case.responsible_employee || null,
      accepted_at: form.case.accepted_at || null,
      parent_case: form.case.parent_case || null,
      service_items: (options.serviceItems ?? [])
        .filter((row) => Number(row.quantity) > 0)
        .map((row) => ({ service_item: row.service_item, quantity: Number(row.quantity) })),
    },
  }
  if (options.companyMode === 'existing') {
    payload.existing_company_id = options.existingCompanyId
    payload.company = { ...payload.company, name: '' }
  } else if (options.companyMode === 'none') {
    payload.company = { ...payload.company, name: '' }
  }
  return payload
}

export const RECEPTION_ERROR_LABELS: Record<string, string> = {
  customer: '顧客情報',
  'customer.name': '氏名',
  'customer.name_kana': 'フリガナ',
  'customer.birth_date': '生年月日',
  'customer.gender': '性別',
  'customer.email': 'メール',
  'customer.phone': '電話番号',
  'customer.residence_expiry': '在留期限',
  'customer.passport_expiry': 'パスポート期限',
  case: '案件情報',
  'case.case_type_master': '案件種別',
  'case.application_category': '申請区分',
  'case.responsible_employee': '担当者',
  'case.accepted_at': '受任日',
  'case.parent_case': '関連元の案件',
  'case.service_items': 'サービス項目（参考）',
  company: '関連会社',
  'company.name': '会社名',
  'company.email': '会社のメール',
  existing_company_id: '既存の会社',
  existing_customer_id: '顧客',
  family_members: '家族情報',
  'family_members.*.name': '家族 {n} の氏名',
  'family_members.*.birth_date': '家族 {n} の生年月日',
  'family_members.*.customer': '家族 {n}',
  request_id: '受付番号',
}

// 400 応答 → 画面上部の要約（項目名：理由）と、各入力欄の下に出すメッセージ
export const receptionErrorView = (data: unknown): { lines: string[]; fields: Record<string, string> } => ({
  lines: describeApiErrors(data, RECEPTION_ERROR_LABELS),
  fields: fieldErrorMap(data),
})
