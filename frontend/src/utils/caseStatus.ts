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
  { label: '追加資料提出済み', value: 'additional_documents_submitted', type: 'primary' },
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

// 案件詳細のステッパー用に、13種類の細かいステータスを6段階の大分類にまとめる。
// 取下げは正常フローの途中離脱なので、この並びには含めず例外表示として扱う。
export interface CaseStageDefinition {
  key: string
  label: string
  statuses: CaseStatus[]
}

export const caseStageGroups: CaseStageDefinition[] = [
  { key: 'preparation', label: '資料準備', statuses: ['consultation', 'accepted', 'collecting_documents', 'preparing_documents', 'ready_to_apply'] },
  { key: 'applied', label: '申請済み', statuses: ['applied'] },
  { key: 'under_review', label: '審査中', statuses: ['under_review', 'additional_documents', 'additional_documents_submitted'] },
  { key: 'result', label: '許可 / 不許可', statuses: ['approved', 'rejected'] },
  { key: 'completed', label: '完了', statuses: ['completed'] },
]

const statusToStageIndex = new Map<CaseStatus, number>()
caseStageGroups.forEach((group, index) => {
  group.statuses.forEach((status) => statusToStageIndex.set(status, index))
})

export type CaseStageState = 'done' | 'current' | 'pending'

export interface CaseStageDisplay extends CaseStageDefinition {
  state: CaseStageState
}

export const isCaseWithdrawn = (status?: string | null) => status === 'withdrawn'

export const getCaseStageDisplays = (status?: string | null): CaseStageDisplay[] => {
  const currentIndex = status ? statusToStageIndex.get(status as CaseStatus) ?? -1 : -1
  return caseStageGroups.map((group, index) => ({
    ...group,
    state: currentIndex === -1 ? 'pending' : index < currentIndex ? 'done' : index === currentIndex ? 'current' : 'pending',
  }))
}

// 「審査中」ステージ内の細かい状態（追加資料対応中など）を小さいバッジで補足する。
export const getCaseStageSubBadge = (status?: string | null): string | null => {
  if (status === 'additional_documents') return '追加資料対応中'
  if (status === 'additional_documents_submitted') return '追加資料提出済み'
  return null
}

// 「進捗を更新」の新しい進捗セレクトをグループ表示するための分類。
export const caseStatusOptionGroups: Array<{ label: string, values: CaseStatus[] }> = [
  { label: '資料準備', values: ['consultation', 'accepted', 'collecting_documents', 'preparing_documents', 'ready_to_apply'] },
  { label: '申請〜審査', values: ['applied', 'under_review', 'additional_documents', 'additional_documents_submitted'] },
  { label: '結果', values: ['approved', 'rejected'] },
  { label: 'その他', values: ['withdrawn', 'completed'] },
]
