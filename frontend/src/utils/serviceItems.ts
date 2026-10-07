// サービス項目（P4）を帳票の明細・受付で使うための小さな関数。
// 実際の値（名称・数量・単位・単価・税区分）は選んだ後も編集できる。選んだ時点のマスタの内容（line.service）は
// 後端が作って保存し、画面ではそれとの違いを「変更あり」として示すだけ。
import type {
  AccountingVoucherLineItem,
  InternalLineCost,
  ServiceItem,
  ServiceItemLineSnapshot,
} from '../types/accounting'

const toNumberOrEmpty = (value: string | number | null | undefined): number | '' => {
  if (value === null || value === undefined || value === '') return ''
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : ''
}

/** 画面で選んだ直後の行（保存すると後端が line_key と service を作り直す）。 */
export const lineFromServiceItem = (item: ServiceItem): AccountingVoucherLineItem => ({
  item_name: item.name,
  quantity: 1,
  unit: item.unit,
  unit_price: toNumberOrEmpty(item.default_price),
  tax_category: item.tax_category,
  price_type: item.tax_category === 'non_taxable' ? 'tax_included' : item.price_type,
  note: '',
  service_item_id: item.id,
  // 保存前の表示用（後端はこの値を使わずマスタから作る）
  service: {
    id: item.id,
    category: item.category,
    name: item.name,
    default_price: item.default_price === null ? null : Number(item.default_price),
    price_type: item.price_type,
    tax_category: item.tax_category,
    unit: item.unit,
    professional_type: item.professional_type,
    professional_type_display: item.professional_type_display,
    price_status: item.price_status,
    code: item.code,
  },
})

/** P6：選んだ時点で暫定価格だったか（行・受付の記録は後から確定しても provisional のまま） */
export const isProvisionalService = (service: { price_status?: string } | null | undefined) =>
  service?.price_status === 'provisional'

/** 一覧の候補に添える表示（暫定価格なら明記する） */
export const serviceOptionSublabel = (item: Pick<ServiceItem, 'category' | 'default_price' | 'price_type' | 'unit' | 'price_status'>) =>
  [item.category, serviceSummary({ default_price: item.default_price === null ? null : Number(item.default_price), price_type: item.price_type, unit: item.unit }),
    item.price_status === 'provisional' ? '暫定価格' : '']
    .filter(Boolean).join('・')

export type ServiceLineField = 'item_name' | 'unit' | 'unit_price' | 'tax_category'

const FIELD_LABELS: Record<ServiceLineField, string> = {
  item_name: '名称',
  unit: '単位',
  unit_price: '単価',
  tax_category: '税区分',
}

const same = (a: unknown, b: unknown) => String(a ?? '') === String(b ?? '')

/** 選んだ時点の内容から変えた項目（表示用）。数量は案件ごとに変わる前提なので対象外。 */
export const changedServiceFields = (line: AccountingVoucherLineItem): ServiceLineField[] => {
  const service = line.service
  if (!service || !line.service_item_id) return []
  const changed: ServiceLineField[] = []
  if (!same(line.item_name, service.name)) changed.push('item_name')
  if (!same(line.unit, service.unit)) changed.push('unit')
  if (service.default_price !== null && Number(line.unit_price) !== Number(service.default_price)) changed.push('unit_price')
  if (!same(line.tax_category ?? 'tax_10', service.tax_category)) changed.push('tax_category')
  return changed
}

export const changedServiceFieldLabels = (line: AccountingVoucherLineItem) => changedServiceFields(line).map((field) => FIELD_LABELS[field])

/** 行をサービス項目から外す（手入力の行として扱う）。保存すると後端がスナップショットと底価を消す。 */
export const unlinkServiceItem = (line: AccountingVoucherLineItem): AccountingVoucherLineItem => {
  const copy = { ...line }
  delete copy.service_item_id
  delete copy.service
  return copy
}

/** 行を複製するとき：line_key は引き継がない（後端が新しい行として扱い、選択時点の内容を作り直す）。 */
export const copyLineForDuplicate = (line: AccountingVoucherLineItem): AccountingVoucherLineItem => {
  const copy = { ...line }
  delete copy.line_key
  return copy
}

export const floorForLine = (line: AccountingVoucherLineItem, costs: InternalLineCost[] | undefined) => {
  if (!costs || !line.line_key || !line.service_item_id) return null
  const cost = costs.find((row) => row.line_key === line.line_key && row.service_item_id === line.service_item_id)
  return cost ? cost.floor_price : null
}

export const priceTypeLabel = (value: string | undefined) => (value === 'tax_excluded' ? '税抜' : '税込')

export const serviceSummary = (service: Pick<ServiceItemLineSnapshot, 'default_price' | 'price_type' | 'unit'> | null | undefined) => {
  if (!service || service.default_price === null || service.default_price === undefined) return '標準価格なし'
  const unit = service.unit ? `／${service.unit}` : ''
  return `標準 ¥${Number(service.default_price).toLocaleString('ja-JP')}（${priceTypeLabel(service.price_type)}）${unit}`
}
