// 請求書・領収書の明細（新規作成・編集の連続入力）。金額計算は voucherCalc（後端と同じ規則）を使う。
// 行の誤りはその行にだけ付け、他の行の入力は消さない。
import type { AccountingVoucherLineItem } from '../types/accounting'
import { lineAmounts } from './voucherCalc'

export type VoucherLine = AccountingVoucherLineItem & { key: number }

let nextKey = 1
export const newLineKey = () => nextKey++

export const createLine = (): VoucherLine => ({
  key: newLineKey(), item_name: '', quantity: 1, unit: '', unit_price: '', tax_category: 'tax_10',
  price_type: 'tax_included', note: '',
})

export const withKeys = (items: AccountingVoucherLineItem[]): VoucherLine[] =>
  items.map((item) => ({ unit: '', note: '', ...item, key: newLineKey() }))

// 指定行の直後に同じ内容の行を作る（新しい行として扱う。後端の line_key は引き継がない＝P4）
export const duplicateLine = (lines: VoucherLine[], index: number): VoucherLine[] => {
  const source = lines[index]
  if (!source) return lines
  const copy: VoucherLine = { ...source, key: newLineKey() }
  delete copy.line_key
  return [...lines.slice(0, index + 1), copy, ...lines.slice(index + 1)]
}

export const moveLine = (lines: VoucherLine[], index: number, delta: -1 | 1): VoucherLine[] => {
  const target = index + delta
  if (target < 0 || target >= lines.length) return lines
  const next = [...lines]
  ;[next[index], next[target]] = [next[target], next[index]]
  return next
}

export const removeLine = (lines: VoucherLine[], index: number): VoucherLine[] => {
  const next = lines.filter((_, i) => i !== index)
  return next.length ? next : [createLine()]
}

export const isBlankLine = (line: AccountingVoucherLineItem) =>
  !String(line.item_name ?? '').trim() && !String(line.unit_price ?? '').trim() && !String(line.note ?? '').trim()
  && !String(line.unit ?? '').trim() && (line.quantity === '' || line.quantity == null || Number(line.quantity) === 1)

const isNumber = (value: unknown) => {
  const text = String(value ?? '').trim()
  return text === '' || Number.isFinite(Number(text))
}

// 行ごとの誤り：{行の key: メッセージ}。空行は誤りにしない（保存時に除く）。
export const validateLines = (lines: VoucherLine[]): Record<number, string> => {
  const errors: Record<number, string> = {}
  lines.forEach((line) => {
    if (isBlankLine(line)) return
    const messages: string[] = []
    if (!String(line.item_name ?? '').trim()) messages.push('項目／説明を入力してください')
    if (!isNumber(line.quantity)) messages.push('数量は数字で入力してください')
    else if (Number(line.quantity) < 0) messages.push('数量は 0 以上にしてください')
    if (!isNumber(line.unit_price)) messages.push('単価は数字で入力してください')
    if (messages.length) errors[line.key] = messages.join('。')
  })
  return errors
}

// 保存用：空行を除き、key を外し、表示用の金額を付ける（保存値は後端が再計算する）
export const toPayloadLines = (lines: VoucherLine[]): AccountingVoucherLineItem[] =>
  lines.filter((line) => !isBlankLine(line)).map(({ key: _key, ...line }) => {
    const amounts = lineAmounts(line)
    return {
      ...line,
      item_name: String(line.item_name ?? '').trim(),
      quantity: Number(line.quantity || 0),
      unit_price: Number(line.unit_price || 0),
      unit: String(line.unit ?? '').trim(),
      note: String(line.note ?? '').trim(),
      line_total: amounts.total,
      tax_excluded_amount: amounts.taxExcluded,
      tax_amount: amounts.tax,
    }
  })

// 後端の行番号（1 始まり、空行を除いた保存順）から画面の行の key を求める
export const keyForSavedRow = (lines: VoucherLine[], row: number): number | null => {
  const saved = lines.filter((line) => !isBlankLine(line))
  return saved[row - 1]?.key ?? null
}

// 入力欄の順序（Enter で次へ進む）：項目／説明 → 数量 → 単位 → 単価 → 税区分 → 備考 → 次の行
export const LINE_FIELDS = ['item_name', 'quantity', 'unit', 'unit_price', 'tax_category', 'note'] as const
export type LineField = (typeof LINE_FIELDS)[number]

export const nextFocus = (field: LineField, rowIndex: number, rowCount: number):
  { rowIndex: number; field: LineField; append: boolean } => {
  const position = LINE_FIELDS.indexOf(field)
  if (position < LINE_FIELDS.length - 1) return { rowIndex, field: LINE_FIELDS[position + 1], append: false }
  return { rowIndex: rowIndex + 1, field: 'item_name', append: rowIndex + 1 >= rowCount }
}
