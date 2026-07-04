import type { Case } from '../types/api'

type CaseStatusSource = Pick<
  Case,
  'status' | 'accepted_at' | 'applied_at' | 'result_notified_at' | 'completed_at'
>

export const getCaseDisplayStatus = (caseItem?: CaseStatusSource | null) => {
  if (!caseItem) return '-'
  if (caseItem.status === '中止') return '中止'
  if (caseItem.completed_at) return '完了'
  if (caseItem.result_notified_at) return '結果通知済'
  if (caseItem.applied_at) return '申請中'
  if (caseItem.accepted_at) return '受任中'
  return '準備中'
}

export const getCaseDisplayStatusTagType = (status: string) => {
  if (status === '中止') return 'danger'
  if (['結果通知済', '完了'].includes(status)) return 'success'
  if (status === '申請中') return 'warning'
  return 'info'
}
