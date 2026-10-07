// 案件内の必要資料の一括操作（P2）：選択・分組の全選択・変更内容の組み立てと確認文・結果の要約。
// 対象は表示中の 1 案件の項目だけ（後端も URL の案件以外の項目を含む依頼を拒否する）。

export interface BatchForm {
  setStatus: boolean
  isCompleted: boolean
  setReceivedAt: boolean
  receivedAt: string | null
  setResponsibleParty: boolean
  responsibleParty: string
  setAcquisitionPlace: boolean
  acquisitionPlace: string
  setNote: boolean
  note: string
  noteMode: 'replace' | 'append'
}

export interface BatchChanges {
  is_completed?: boolean
  received_at?: string | null
  responsible_party?: string
  acquisition_place?: string
  note?: string
  note_mode?: 'replace' | 'append'
}

export interface BatchResultRow {
  id: number
  name?: string
  status: 'success' | 'failed'
  code?: string
  detail?: string
  changed?: string[]
}

export interface BatchResponse {
  batch_id: string
  requested: number
  succeeded: number
  failed: number
  results: BatchResultRow[]
}

export const emptyBatchForm = (): BatchForm => ({
  setStatus: false, isCompleted: true,
  setReceivedAt: false, receivedAt: null,
  setResponsibleParty: false, responsibleParty: '',
  setAcquisitionPlace: false, acquisitionPlace: '',
  setNote: false, note: '', noteMode: 'append',
})

// --- 選択 ----------------------------------------------------------------------
export const toggleSelection = (selected: number[], id: number) => (
  selected.includes(id) ? selected.filter((value) => value !== id) : [...selected, id]
)

// 分組の全選択／解除：分組の全項目が選ばれていれば外し、そうでなければ全部選ぶ
export const toggleGroup = (selected: number[], groupIds: number[]) => {
  const allSelected = groupIds.length > 0 && groupIds.every((id) => selected.includes(id))
  if (allSelected) return selected.filter((id) => !groupIds.includes(id))
  return [...selected, ...groupIds.filter((id) => !selected.includes(id))]
}

export const groupState = (selected: number[], groupIds: number[]): 'all' | 'some' | 'none' => {
  const count = groupIds.filter((id) => selected.includes(id)).length
  if (!count) return 'none'
  return count === groupIds.length ? 'all' : 'some'
}

// 表示中の項目に無い ID（削除・再読込で消えたもの）を選択から外す
export const pruneSelection = (selected: number[], visibleIds: number[]) => selected.filter((id) => visibleIds.includes(id))

// --- 変更内容 -------------------------------------------------------------------
export const buildChanges = (form: BatchForm): BatchChanges => {
  const changes: BatchChanges = {}
  if (form.setStatus) changes.is_completed = form.isCompleted
  if (form.setReceivedAt) changes.received_at = form.receivedAt || null
  if (form.setResponsibleParty) changes.responsible_party = form.responsibleParty
  if (form.setAcquisitionPlace) changes.acquisition_place = form.acquisitionPlace.trim()
  if (form.setNote) {
    changes.note = form.note.trim()
    changes.note_mode = form.noteMode
  }
  return changes
}

export const completeOnlyChanges = (): BatchChanges => ({ is_completed: true })

export const hasChanges = (changes: BatchChanges) => Object.keys(changes).some((key) => key !== 'note_mode')

// 実行前の確認に出す「変更する項目」の一覧
export const describeChanges = (changes: BatchChanges, partyLabel: (value: string) => string = (v) => v) => {
  const lines: string[] = []
  if ('is_completed' in changes) lines.push(`状態 → ${changes.is_completed ? '完了' : '未完了'}`)
  if ('received_at' in changes) lines.push(`受領日 → ${changes.received_at || '（消去）'}`)
  if ('responsible_party' in changes) lines.push(`準備者 → ${changes.responsible_party ? partyLabel(changes.responsible_party) : '（消去）'}`)
  if ('acquisition_place' in changes) lines.push(`取得先・手続先 → ${changes.acquisition_place || '（消去）'}`)
  if ('note' in changes) {
    lines.push(changes.note_mode === 'append' ? `備考に追記 → ${changes.note || '（なし）'}` : `備考を置き換え → ${changes.note || '（消去）'}`)
  }
  return lines
}

export const confirmMessage = (count: number, changes: BatchChanges, partyLabel?: (value: string) => string) => (
  [`選択した ${count} 件の必要資料を次のとおり変更します。`, ...describeChanges(changes, partyLabel).map((line) => `・${line}`)].join('\n')
)

// 受領日は書類（必要資料）の項目にだけ設定できる（後端と同じ規則）
export const notApplicableCount = (
  changes: BatchChanges, items: Array<{ id: number; item_type: string }>, selected: number[],
) => (changes.received_at ? items.filter((item) => selected.includes(item.id) && item.item_type !== 'document').length : 0)

// 一括更新そのものが失敗したとき（拒否・権限・通信）の文言。JSON 以外の応答（HTML など）は使わない。
export const batchErrorText = (error: unknown) => {
  const response = (error as { response?: { status?: number; data?: unknown } })?.response
  if (!response) return '一括更新できませんでした。通信状況を確認して再試行してください。'
  if (response.status === 403) return 'この案件の必要資料を変更する権限がありません。'
  if (response.status === 404) return '案件が見つかりません。画面を更新してください。'
  const data = response.data
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const record = data as Record<string, unknown>
    if (typeof record.detail === 'string') return record.detail
    for (const value of Object.values(record)) {
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    }
  }
  return `一括更新できませんでした（${response.status ?? '不明'}）。もう一度お試しください。`
}

// --- 結果 ----------------------------------------------------------------------
export const failedRows = (response: BatchResponse) => response.results.filter((row) => row.status === 'failed')

// 失敗した項目だけを選択に残す（直して再実行しやすくする）
export const selectionAfterResult = (response: BatchResponse) => failedRows(response).map((row) => row.id)

export const resultSummary = (response: BatchResponse) => (
  response.failed
    ? `${response.succeeded} 件を更新しました。${response.failed} 件は更新できませんでした。`
    : `${response.succeeded} 件を更新しました。`
)
