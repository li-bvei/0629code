// 不動産の一括変更：画面の入力から、後端へ 1 回だけ送るリクエストを組み立てる（判定は常に後端）。
export type BulkField = 'stage' | 'responsible_name' | 'transaction_date'
export type ClearableBulkField = 'responsible_name' | 'transaction_date'

export const BULK_FIELD_LABELS: Record<BulkField, string> = { stage: '段階', responsible_name: '担当者', transaction_date: '取引日' }

export interface BulkForm {
  enabled: Record<BulkField, boolean>
  clear: Record<ClearableBulkField, boolean>
  stage: string
  responsible_name: string
  transaction_date: string | null
}

// 後端（bulk-preview）が固定した対象。ID・件数・各記録の版は署名付きトークンの中にあり、画面からは変えられない。
export interface BulkTarget {
  mode: 'ids' | 'filter'
  selection_token: string
  count: number
  filter_summary: string[]
}

export interface BulkUpdateRequest {
  selection_token: string
  changes: Partial<Record<BulkField, string>>
  clear_fields: ClearableBulkField[]
  expected_count: number
}

// 一覧で選択した記録を固定するための入力：ID と「一覧に表示された時点の updated_at」。
// 表示後に他の人が変更していれば、後端がこの時点で 409 を返す（古い画面のまま一括変更させない）。
export interface BulkPreviewRequest {
  selection: { mode: 'ids'; items: { id: number; updated_at: string }[] }
}

export const buildPreviewRequest = (rows: { id: number; updated_at: string }[]): BulkPreviewRequest => ({
  selection: { mode: 'ids', items: rows.map((row) => ({ id: row.id, updated_at: row.updated_at })) },
})

export const emptyBulkForm = (): BulkForm => ({
  enabled: { stage: false, responsible_name: false, transaction_date: false },
  clear: { responsible_name: false, transaction_date: false },
  stage: '', responsible_name: '', transaction_date: null,
})


const FIELDS: BulkField[] = ['stage', 'responsible_name', 'transaction_date']

export const buildBulkRequest = (target: BulkTarget | null, form: BulkForm):
  { request: BulkUpdateRequest; error?: undefined } | { error: string; request?: undefined } => {
  if (!target || !target.selection_token || target.count < 1) return { error: '対象の記録を選択してください。' }
  const changes: Partial<Record<BulkField, string>> = {}
  const clearFields: ClearableBulkField[] = []
  for (const field of FIELDS) {
    if (!form.enabled[field]) continue // チェックしていない項目は送らない（＝変更しない）
    if (field !== 'stage' && form.clear[field]) {
      clearFields.push(field)
      continue
    }
    const value = String(form[field] ?? '').trim()
    if (!value) return { error: `${BULK_FIELD_LABELS[field]}の変更後の値を入力してください。` }
    changes[field] = value
  }
  if (!Object.keys(changes).length && !clearFields.length) return { error: '変更する項目にチェックを入れてください。' }
  return {
    request: {
      selection_token: target.selection_token,
      changes,
      clear_fields: clearFields,
      expected_count: target.count,
    },
  }
}

// 最終確認に出す「何をどう変えるか」の一覧
export const describeBulkChanges = (request: BulkUpdateRequest, stageLabel: (value: string) => string): string[] => [
  ...Object.entries(request.changes).map(([field, value]) =>
    `${BULK_FIELD_LABELS[field as BulkField]} →「${field === 'stage' ? stageLabel(value as string) : value}」`),
  ...request.clear_fields.map((field) => `${BULK_FIELD_LABELS[field]} → 空欄にする`),
]
