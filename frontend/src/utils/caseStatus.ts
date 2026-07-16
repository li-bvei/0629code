import type { CaseRegistrationStatus, CaseStatus } from '../types/api'

export const caseStatusOptions: Array<{ label: string, value: CaseStatus, type: 'info' | 'success' | 'warning' | 'danger' | 'primary' }> = [
  { label: '相談中', value: 'consultation', type: 'info' },
  { label: '受任済み', value: 'accepted', type: 'primary' },
  { label: '資料準備中', value: 'collecting_documents', type: 'warning' },
  { label: '書類作成中', value: 'preparing_documents', type: 'warning' },
  { label: '申請準備完了', value: 'ready_to_apply', type: 'success' },
  { label: '申請済み', value: 'applied', type: 'warning' },
  { label: '審査中', value: 'under_review', type: 'warning' },
  { label: '追加資料対応中', value: 'additional_documents', type: 'warning' },
  { label: '許可', value: 'approved', type: 'success' },
  { label: '不許可', value: 'rejected', type: 'danger' },
  { label: '取下げ', value: 'withdrawn', type: 'info' },
  { label: '完了', value: 'completed', type: 'success' },
]

export const caseRegistrationStatusOptions: Array<{ label: string, value: CaseRegistrationStatus, type: 'info' | 'success' | 'warning' }> = [
  { label: '有効', value: 'active', type: 'success' },
  { label: '無効', value: 'inactive', type: 'info' },
  { label: 'アーカイブ', value: 'archived', type: 'warning' },
]

export const getCaseDisplayStatus = (status?: string | null) => (
  caseStatusOptions.find((option) => option.value === status)?.label || status || '-'
)

export const getCaseDisplayStatusTagType = (status?: string | null) => (
  caseStatusOptions.find((option) => option.value === status)?.type || 'info'
)

export const getCaseRegistrationStatusLabel = (status?: string | null) => (
  caseRegistrationStatusOptions.find((option) => option.value === status)?.label || status || '-'
)

export const getCaseRegistrationStatusTagType = (status?: string | null) => (
  caseRegistrationStatusOptions.find((option) => option.value === status)?.type || 'info'
)
