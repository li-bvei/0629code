// 清風合格通知書（P5・固定テンプレート）の画面用の関数。
// 画面の確認は入力の手助けだけで、正式な検証・通知書番号の派生・版面の確認は後端が行う（同じ規則にそろえている）。
import type { SeifuNoticeRecordPayload } from '../types/accounting'

export const RECIPIENT_NAME_MAX_LENGTH = 40
const PERMIT_PATTERN = /^[0-9A-Z]+(?:-[0-9A-Z]+)*$/
// 制御文字・書式文字（ゼロ幅・双方向制御など）・改行
const FORBIDDEN_NAME_CHARS = new RegExp(
  '[\\u0000-\\u001f\\u007f-\\u009f\\u00ad\\u061c\\u180e\\u200b-\\u200f\\u202a-\\u202e'
  + '\\u2028\\u2029\\u2060-\\u2064\\u2066-\\u206f\\ufeff\\ufff9-\\ufffb]',
)

export const normalizePermitNumber = (value: string) =>
  value.normalize('NFKC').trim().toUpperCase().replace(/[ー−]/g, '-')

// 通知書番号の規則（後端の derive_notice_number と同じ）。表示用で、保存・PDF は後端の値を使う
export const deriveNoticeNumber = (permitNumber: string, suffix = 'A') => {
  const permit = normalizePermitNumber(permitNumber)
  return permit ? `${permit} ${suffix}` : ''
}

export const defaultSeifuTitle = (recipientName: string) => {
  const name = recipientName.trim()
  return name ? `${name} 合格通知書` : '清風合格通知書'
}

// 端末の日付（UTC ではなく現地の日付）
export const localToday = (now = new Date()) => {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

const isRealDate = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [y, m, d] = value.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1, d))
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d
}

export const validateSeifuForm = (value: Pick<SeifuNoticeRecordPayload, 'recipient_name' | 'permit_number' | 'issue_date'>) => {
  const name = value.recipient_name.trim()
  if (!name) return '宛名を入力してください。'
  if ([...name].length > RECIPIENT_NAME_MAX_LENGTH) return `宛名は ${RECIPIENT_NAME_MAX_LENGTH} 文字以内で入力してください。`
  if (FORBIDDEN_NAME_CHARS.test(name)) return '宛名に印字できない文字（制御文字・書式文字など）が含まれています。'
  const permit = normalizePermitNumber(value.permit_number)
  if (!permit) return '許可番号を入力してください。'
  if (!PERMIT_PATTERN.test(permit) || permit.length < 3 || permit.length > 12 || !/\d/.test(permit)) {
    return '許可番号は半角英数字（数字を含む 3～12 文字、区切りのハイフン可）で入力してください。'
  }
  if (!value.issue_date) return '通知日を入力してください。'
  if (!isRealDate(value.issue_date)) return '通知日の形式が正しくありません。'
  const year = Number(value.issue_date.slice(0, 4))
  if (year < 2000 || year > 2099) return '通知日は 2000 年～2099 年の日付を入力してください。'
  return ''
}

// 1 回の「PDF作成」操作の識別子（二重クリック・再送でも同じ生成結果を返してもらう）
export const newRequestId = () => {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID().replace(/-/g, '')
    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`
  return `seifu-${random}`.slice(0, 64)
}

// 後端のエラー本文から表示文言を取り出す（PDF 用の blob 応答でも JSON の誤りを読む）
export const seifuErrorMessage = async (error: unknown, fallback: string) => {
  const response = (error as { response?: { status?: number; data?: unknown } })?.response
  let data = response?.data
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    try {
      data = JSON.parse(await data.text())
    } catch {
      data = undefined
    }
  }
  if (data && typeof data === 'object') {
    const record = data as Record<string, unknown>
    if (typeof record.detail === 'string' && record.detail) return record.detail
    const first = Object.values(record).flat().find((value) => typeof value === 'string' && value)
    if (typeof first === 'string') return first
  }
  if (response?.status === 403) return 'この操作を行う権限がありません。'
  if (!response) return '通信できませんでした。接続を確認して、もう一度お試しください。'
  return fallback
}

export const formatFileSize = (bytes: number | null | undefined) => {
  if (!bytes) return '-'
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}
