// DRF の 400 応答（項目名 → メッセージの入れ子）を、画面に出せる形へ展開する。
// 例：{ case: { responsible_employee: ['担当者を選択してください。'] } }
//   → [{ path: 'case.responsible_employee', messages: ['担当者を選択してください。'] }]
export interface ApiFieldError {
  path: string
  messages: string[]
}

const GENERAL_KEYS = new Set(['non_field_errors', 'detail'])

const joinPath = (prefix: string, key: string) => {
  if (GENERAL_KEYS.has(key)) return prefix
  return prefix ? `${prefix}.${key}` : key
}

export const flattenApiErrors = (data: unknown, prefix = ''): ApiFieldError[] => {
  if (data === null || data === undefined || data === '') return []
  if (typeof data === 'string' || typeof data === 'number' || typeof data === 'boolean') {
    return [{ path: prefix, messages: [String(data)] }]
  }
  if (Array.isArray(data)) {
    const texts = data.filter((item) => typeof item === 'string') as string[]
    const nested = data.flatMap((item, index) =>
      (item !== null && typeof item === 'object' ? flattenApiErrors(item, joinPath(prefix, String(index))) : []))
    return [...(texts.length ? [{ path: prefix, messages: texts }] : []), ...nested]
  }
  if (typeof data === 'object') {
    return Object.entries(data as Record<string, unknown>).flatMap(([key, value]) => flattenApiErrors(value, joinPath(prefix, key)))
  }
  return []
}

// labels のキーは項目のパス。配列の添字は「*」で書き、ラベル中の {n} が 1 始まりの番号に置き換わる。
export const labelForPath = (path: string, labels: Record<string, string>): string => {
  if (!path) return ''
  if (labels[path]) return labels[path]
  let index = ''
  const generic = path.split('.').map((part) => {
    if (!/^\d+$/.test(part)) return part
    index = String(Number(part) + 1)
    return '*'
  }).join('.')
  const label = labels[generic]
  return label ? label.replace('{n}', index) : path
}

export const describeApiErrors = (data: unknown, labels: Record<string, string> = {}): string[] =>
  flattenApiErrors(data).map(({ path, messages }) => {
    const label = labelForPath(path, labels)
    return label ? `${label}：${messages.join(' ')}` : messages.join(' ')
  })

// el-form-item の :error に渡す用（パス → 最初のメッセージ群）
export const fieldErrorMap = (data: unknown): Record<string, string> => {
  const map: Record<string, string> = {}
  flattenApiErrors(data).forEach(({ path, messages }) => {
    if (path) map[path] = map[path] ? `${map[path]} ${messages.join(' ')}` : messages.join(' ')
  })
  return map
}

export const responseOf = (error: unknown): { status?: number; data?: unknown } =>
  (error as { response?: { status?: number; data?: unknown } })?.response ?? {}
