export const toAccountingNumber = (value: number | string | null | undefined) => {
  const numberValue = Number(value ?? 0)
  if (!Number.isFinite(numberValue)) return 0
  return numberValue
}

export const formatAccountingNumber = (value: number | string | null | undefined, emptyValue = '0') => {
  if (value === null || value === undefined || value === '') return emptyValue
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return emptyValue
  const hasDecimal = Math.abs(numberValue % 1) > 0
  return numberValue.toLocaleString('ja-JP', {
    minimumFractionDigits: 0,
    maximumFractionDigits: hasDecimal ? 2 : 0,
  })
}

export const formatAccountingPercent = (value: number) => `${value.toFixed(1)}%`
