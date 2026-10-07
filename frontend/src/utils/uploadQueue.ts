// 複数ファイル登録の待ち行列（P2）。1 ファイル＝1 回の登録（POST /documents/）で、ファイルごとに
// 進捗・成功・失敗を持つ。1 件の失敗で行列を消さず、他の成功も取り消さない。失敗分だけ再試行できる。
// ここでの上限確認は画面での事前案内で、最終的な判定は後端（upload-check・登録時の検査）が行う。
// P6：ファイルごとに「資料内容」（例：住民票）を必須で入力する。表示名「資料内容-顧客名.拡張子」は後端が作る。
// ZIP は他のファイルより小さい上限（zip_upload_max_bytes）。中身の安全性（展開爆弾・パス・入れ子）は後端が検査する。

export type UploadStatus = 'waiting' | 'uploading' | 'success' | 'failed'

export interface UploadPolicy {
  max_file_bytes: number
  batch_max_files: number
  batch_max_total_bytes: number
  zip_max_files: number
  zip_max_total_bytes: number
  allowed_extensions: string[]
  /** P6：アップロードする ZIP 1 件の上限（後端の DOCUMENT_ZIP_UPLOAD_MAX_BYTES） */
  zip_upload_max_bytes?: number
  content_label_max_length?: number
}

export interface QueueItem<F = File> {
  key: string
  file: F
  name: string
  size: number
  category: string
  contentLabel: string
  status: UploadStatus
  progress: number
  error: string
  documentId: number | null
}

const MB = 1024 * 1024

export const DEFAULT_UPLOAD_POLICY: UploadPolicy = {
  max_file_bytes: 20 * MB,
  batch_max_files: 20,
  batch_max_total_bytes: 200 * MB,
  zip_max_files: 100,
  zip_max_total_bytes: 200 * MB,
  zip_upload_max_bytes: 10 * MB,
  content_label_max_length: 60,
  allowed_extensions: ['.csv', '.doc', '.docx', '.gif', '.heic', '.jpeg', '.jpg', '.pdf', '.png', '.ppt', '.pptx',
    '.tif', '.tiff', '.txt', '.webp', '.xls', '.xlsx', '.zip'],
}

export const formatBytes = (size: number | null | undefined) => {
  if (!size) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < MB) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / MB).toFixed(1)} MB`
}

const RESERVED = new Set(['con', 'prn', 'aux', 'nul', ...Array.from({ length: 9 }, (_, i) => `com${i + 1}`),
  ...Array.from({ length: 9 }, (_, i) => `lpt${i + 1}`)])

const extensionOf = (name: string) => {
  const index = name.lastIndexOf('.')
  return index > 0 ? name.slice(index).toLowerCase() : ''
}

// 後端の filename_problem・validate_upload と同じ観点（事前案内用）
export const fileProblem = (name: string, size: number, policy: UploadPolicy): string => {
  if (!name.trim()) return 'ファイル名がありません。'
  if (/[\\/]/.test(name)) return 'ファイル名にフォルダの区切り文字は使えません。'
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f]/.test(name)) return 'ファイル名に制御文字が含まれています。'
  if (name.length > 200) return 'ファイル名が長すぎます（200 文字まで）。'
  const stem = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : name
  if (!stem.replace(/[ .]/g, '')) return 'ファイル名が正しくありません。'
  if (RESERVED.has(stem.split('.')[0].trim().toLowerCase())) return 'この名前のファイルは登録できません（予約された名前）。'
  const ext = extensionOf(name)
  if (!policy.allowed_extensions.includes(ext)) return `この種類のファイル（${ext || '拡張子なし'}）は登録できません。`
  if (size <= 0) return '空のファイルは登録できません。'
  if (size > policy.max_file_bytes) return `ファイルが大きすぎます（${Math.floor(policy.max_file_bytes / MB)}MB まで）。`
  const zipLimit = policy.zip_upload_max_bytes
  if (ext === '.zip' && zipLimit && size > zipLimit) return `ZIP ファイルが大きすぎます（ZIP は ${formatBytes(zipLimit)} まで）。`
  return ''
}

export const CONTENT_LABEL_SUGGESTIONS = ['住民票', '在留カード', 'パスポート', '課税証明書', '納税証明書', '戸籍謄本', '登記簿謄本',
  '雇用契約書', '写真', '申請書']

// 後端の normalize_content_label と同じ観点（事前案内用。最終判定は後端）
export const contentLabelProblem = (value: string, policy: UploadPolicy = DEFAULT_UPLOAD_POLICY): string => {
  const label = (value || '').normalize('NFC').trim().replace(/\s+/g, ' ')
  if (!label) return '資料内容（例：住民票・在留カード）を入力してください。'
  const max = policy.content_label_max_length ?? 60
  if (label.length > max) return `資料内容は ${max} 文字以内で入力してください。`
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]/.test(label)) return '資料内容に制御文字・書式文字は使えません。'
  if (/[\\/:*?"<>|]/.test(label)) return '資料内容に \\ / : * ? " < > | は使えません。'
  if (label.includes('..') || label.startsWith('.') || label.endsWith('.')) return '資料内容の先頭・末尾に「.」は使えません（「..」も不可）。'
  if (RESERVED.has(label.split('.')[0].trim().toLowerCase())) return 'この名前は資料内容に使えません（予約された名前）。'
  return ''
}

/** 登録前に資料内容が足りない行（行列は消さない。入力すれば登録できる） */
export const rowsMissingLabel = <F>(queue: QueueItem<F>[], policy: UploadPolicy = DEFAULT_UPLOAD_POLICY) => (
  queue.filter((item) => item.status === 'waiting' && contentLabelProblem(item.contentLabel, policy))
)

/** まとめて入力：資料内容が空の行（未登録のもの）にだけ同じ値を入れる */
export const fillMissingLabels = <F>(queue: QueueItem<F>[], label: string) => queue.map((item) => (
  item.status !== 'success' && item.status !== 'uploading' && !item.contentLabel.trim() ? { ...item, contentLabel: label } : item
))

let keySeed = 0
const nextKey = () => {
  keySeed += 1
  return `upload-${Date.now().toString(36)}-${keySeed}`
}

export interface AddResult<F> {
  queue: QueueItem<F>[]
  errors: string[]
}

// 選んだファイルを行列に加える。行列全体の上限（件数・合計）を超える分は加えず理由を返す。
// 1 件ごとの問題（種類・大きさ・名前）は「失敗」として理由付きで並べる（何が駄目かを見せる）。
export const addFiles = <F extends { name: string; size: number }>(
  queue: QueueItem<F>[], files: F[], policy: UploadPolicy, category: string,
): AddResult<F> => {
  const errors: string[] = []
  const active = queue.filter((item) => item.status !== 'success')
  const room = Math.max(policy.batch_max_files - active.length, 0)
  const accepted = files.slice(0, room)
  if (files.length > room) {
    errors.push(`一度に登録できるのは ${policy.batch_max_files} 件までです。${files.length - room} 件は追加しませんでした。`)
  }
  const added: QueueItem<F>[] = []
  let total = active.reduce((sum, item) => sum + item.size, 0)
  for (const file of accepted) {
    const problem = fileProblem(file.name, file.size, policy)
    if (!problem && total + file.size > policy.batch_max_total_bytes) {
      errors.push(`合計サイズが上限（${Math.floor(policy.batch_max_total_bytes / MB)}MB）を超えるため「${file.name}」以降は追加しませんでした。`)
      break
    }
    if (!problem) total += file.size
    added.push({
      key: nextKey(), file, name: file.name, size: file.size, category, contentLabel: '',
      status: problem ? 'failed' : 'waiting', progress: 0, error: problem, documentId: null,
    })
  }
  return { queue: [...queue, ...added], errors }
}

// 再試行できるのは、後端・通信で失敗したもの（ファイル自体の問題は選び直しが必要）
export const isRetryable = (item: QueueItem<unknown>, policy: UploadPolicy) => (
  item.status === 'failed' && !fileProblem(item.name, item.size, policy)
)

export const markFailedForRetry = <F>(queue: QueueItem<F>[], policy: UploadPolicy) => queue.map((item) => (
  isRetryable(item as QueueItem<unknown>, policy) ? { ...item, status: 'waiting' as const, progress: 0, error: '' } : item
))

export const removeFinished = <F>(queue: QueueItem<F>[]) => queue.filter((item) => item.status !== 'success')

export const summarizeQueue = (queue: QueueItem<unknown>[]) => ({
  total: queue.length,
  waiting: queue.filter((item) => item.status === 'waiting').length,
  uploading: queue.filter((item) => item.status === 'uploading').length,
  success: queue.filter((item) => item.status === 'success').length,
  failed: queue.filter((item) => item.status === 'failed').length,
  totalBytes: queue.reduce((sum, item) => sum + item.size, 0),
})

// 後端の 400（{file: [...]}・{detail}）・403・通信エラーを 1 行の理由にする
export const uploadErrorText = (error: unknown): string => {
  const response = (error as { response?: { status?: number; data?: unknown } })?.response
  if (!response) return '通信できませんでした。接続を確認して再試行してください。'
  if (response.status === 403) return 'この案件にファイルを登録する権限がありません。'
  if (response.status === 404) return '案件が見つかりません。'
  if (response.status === 413) return 'ファイルが大きすぎます（サーバーの上限）。'
  const data = response.data as Record<string, unknown> | undefined
  if (data && typeof data === 'object') {
    for (const key of ['content_label', 'file', 'title', 'category', 'case', 'non_field_errors']) {
      const value = data[key]
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    }
    if (typeof data.detail === 'string') return data.detail
  }
  return `登録できませんでした（${response.status ?? '不明'}）。`
}

// 待ち行列を同時 concurrency 件ずつ登録する。update は行が変わるたびに呼ばれる（画面の再描画用）。
// 1 件の失敗は理由を残して次へ進む（例外を外へ出さない）。
export const runQueue = async <F>(
  queue: QueueItem<F>[],
  upload: (item: QueueItem<F>, onProgress: (percent: number) => void) => Promise<{ id: number }>,
  update: (key: string, patch: Partial<QueueItem<F>>) => void,
  concurrency = 2,
) => {
  const pending = queue.filter((item) => item.status === 'waiting')
  let cursor = 0
  const worker = async () => {
    while (cursor < pending.length) {
      const item = pending[cursor]
      cursor += 1
      update(item.key, { status: 'uploading', progress: 0, error: '' })
      try {
        const created = await upload(item, (percent) => update(item.key, { progress: Math.min(99, Math.round(percent)) }))
        update(item.key, { status: 'success', progress: 100, documentId: created.id })
      } catch (error) {
        update(item.key, { status: 'failed', progress: 0, error: uploadErrorText(error) })
      }
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, Math.min(concurrency, pending.length)) }, worker))
}
