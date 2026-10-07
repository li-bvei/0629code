// 毎日の計画・業務報告（P3）の画面ロジック（日付・並び・結転の既定日・エラー文言）。単体テストあり。
import type { Task } from '../types/api'

const pad = (value: number) => String(value).padStart(2, '0')

export const toIsoDate = (value: Date) => `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`

export const parseIsoDate = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, (m || 1) - 1, d || 1)
}

export const todayIso = (now: Date = new Date()) => toIsoDate(now)

export const addDays = (iso: string, days: number) => {
  const date = parseIsoDate(iso)
  date.setDate(date.getDate() + days)
  return toIsoDate(date)
}

// 結転先の既定（P6）：後端の暦（/tasks/calendar/）が返す次の営業日（土日・祝日・振替休日・国民の休日を除く）。
// 暦を読めないときだけ、この関数で次の月〜金を仮の既定にする（祝日は考慮しない）。どちらも画面で変更できる
export const nextWeekday = (iso: string) => {
  let candidate = addDays(iso, 1)
  while ([0, 6].includes(parseIsoDate(candidate).getDay())) candidate = addDays(candidate, 1)
  return candidate
}

// 結転先に選んだ日が休日・対応範囲外なら注意を出す（選ぶこと自体は止めない）
export const carryDateHint = (info: { is_business_day: boolean; supported: boolean; notice: string } | null) => {
  if (!info) return ''
  if (!info.supported) return info.notice
  return info.is_business_day ? '' : `${info.notice}休日でも結転できます。`
}

export const OPEN_STATUSES = ['pending', 'in_progress', 'paused']
export const isOpen = (item: Pick<Task, 'status'>) => OPEN_STATUSES.includes(item.status)
export const isDone = (item: Pick<Task, 'status'>) => item.status === 'completed'

export const sortPlan = <T extends Pick<Task, 'sort_order' | 'id'>>(items: T[]) => (
  [...items].sort((a, b) => (a.sort_order - b.sort_order) || (a.id - b.id))
)

export const planSummary = (items: Array<Pick<Task, 'status'>>) => ({
  total: items.length,
  done: items.filter(isDone).length,
  open: items.filter(isOpen).length,
  carried: items.filter((item) => item.status === 'carried_over').length,
})

// 1 つ上／下へ動かした並びを返す（端では変わらない）
export const moveItem = <T extends { id: number }>(items: T[], id: number, direction: -1 | 1) => {
  const index = items.findIndex((item) => item.id === id)
  const target = index + direction
  if (index < 0 || target < 0 || target >= items.length) return items
  const next = [...items]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

export const versionPayload = (items: Array<Pick<Task, 'id' | 'updated_at'>>) => (
  items.map((item) => ({ id: item.id, version: item.updated_at }))
)

// 他の人の計画（全件閲覧権限で見ているとき）は読むだけ。結転済みの項目は結転先で操作する
export const canEditItem = (item: Pick<Task, 'status'>, readOnly: boolean) => !readOnly && item.status !== 'carried_over'

export const PRIORITY_OPTIONS = [
  { value: 'high', label: '高', tag: 'danger' },
  { value: 'normal', label: '中', tag: 'info' },
  { value: 'low', label: '低', tag: 'success' },
] as const

// 失敗の文言（409 は「画面を更新」、JSON 以外の応答は使わない）
export const planErrorText = (error: unknown, fallback = '保存できませんでした。もう一度お試しください。') => {
  const response = (error as { response?: { status?: number; data?: unknown } })?.response
  if (!response) return '通信できませんでした。接続を確認して再試行してください。'
  const data = response.data
  const record = data && typeof data === 'object' && !Array.isArray(data) ? data as Record<string, unknown> : null
  if (response.status === 409) {
    return typeof record?.detail === 'string' ? record.detail : '他の操作で内容が変わっています。画面を更新してからもう一度操作してください。'
  }
  if (response.status === 403) return typeof record?.detail === 'string' ? record.detail : 'この操作の権限がありません。'
  if (response.status === 404) return '対象が見つかりません。画面を更新してください。'
  if (record) {
    if (typeof record.detail === 'string') return record.detail
    for (const value of Object.values(record)) {
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
    }
  }
  return fallback
}

export const isConflict = (error: unknown) => (error as { response?: { status?: number } })?.response?.status === 409
export const errorCode = (error: unknown) => {
  const data = (error as { response?: { data?: unknown } })?.response?.data
  return data && typeof data === 'object' && 'code' in data ? String((data as { code: unknown }).code) : ''
}

export const carryBatchSummary = (result: { succeeded: number; failed: number }) => (
  result.failed ? `${result.succeeded} 件を結転しました。${result.failed} 件は結転できませんでした。` : `${result.succeeded} 件を結転しました。`
)
