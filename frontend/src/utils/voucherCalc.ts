// 帳票明細の金額計算（後端 voucher_calculations.py と同じ規則。画面の即時表示用で、保存値は後端が再計算する）。
export type TaxCategory = 'tax_10' | 'tax_8' | 'non_taxable'
export type PriceType = 'tax_included' | 'tax_excluded'

export interface CalcLine {
  item_name?: string
  quantity?: number | string
  unit_price?: number | string
  tax_category?: TaxCategory | string
  price_type?: PriceType | string
}

const RATES: Record<string, number> = { tax_10: 0.1, tax_8: 0.08, non_taxable: 0 }

// Python の ROUND_HALF_UP（0.5 は 0 から遠い方へ）に合わせる
export const roundHalfUp = (value: number) => Math.sign(value) * Math.round(Math.abs(value) + Number.EPSILON * 10)

const toNumber = (value: unknown) => {
  const n = Number(value ?? 0)
  return Number.isFinite(n) ? n : 0
}

export const lineAmounts = (line: CalcLine) => {
  const taxCategory = (line.tax_category && line.tax_category in RATES ? line.tax_category : 'tax_10') as TaxCategory
  const priceType = line.price_type === 'tax_excluded' ? 'tax_excluded' : 'tax_included'
  const raw = roundHalfUp(toNumber(line.quantity) * toNumber(line.unit_price))
  if (taxCategory === 'non_taxable') return { total: raw, taxExcluded: raw, tax: 0, taxCategory }
  const rate = RATES[taxCategory]
  if (priceType === 'tax_excluded') {
    const tax = roundHalfUp(raw * rate)
    return { total: raw + tax, taxExcluded: raw, tax, taxCategory }
  }
  const taxExcluded = roundHalfUp(raw / (1 + rate))
  return { total: raw, taxExcluded, tax: raw - taxExcluded, taxCategory }
}

export const summarizeLines = (lines: CalcLine[]) => {
  const summary = { subtotal: 0, tax_total: 0, total: 0, subtotal_10: 0, tax_10: 0, subtotal_8: 0, tax_8: 0, subtotal_non_taxable: 0 }
  for (const line of lines) {
    if (!(line.item_name || '').trim() && !toNumber(line.quantity) && !toNumber(line.unit_price)) continue
    const a = lineAmounts(line)
    summary.subtotal += a.taxExcluded
    summary.tax_total += a.tax
    summary.total += a.total
    if (a.taxCategory === 'tax_10') { summary.subtotal_10 += a.taxExcluded; summary.tax_10 += a.tax }
    else if (a.taxCategory === 'tax_8') { summary.subtotal_8 += a.taxExcluded; summary.tax_8 += a.tax }
    else summary.subtotal_non_taxable += a.taxExcluded
  }
  return summary
}

export const formatYen = (value?: number | string | null) => `￥${Number(value || 0).toLocaleString()}`
