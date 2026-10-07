// 帳票 API のエラー文言（後端の detail / 項目エラーを優先して表示する）。
export const apiErrorText = (error: unknown, fallback: string) => {
  const response = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
  if (response?.status === 403) return 'この操作の権限がありません。'
  const data = response?.data
  if (!data) return fallback
  if (typeof data.detail === 'string') return data.detail
  const first = Object.values(data)[0]
  if (typeof first === 'string') return first
  return Array.isArray(first) && typeof first[0] === 'string' ? first[0] : fallback
}

// P6：暫定価格のサービス項目を含む見積書・請求書を発行しようとしたときの応答（確認すれば発行できる）
export const provisionalPriceNotice = (error: unknown): string | null => {
  const response = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
  const data = response?.data
  if (response?.status !== 400 || !data || data.code !== 'provisional_price_confirmation_required') return null
  return typeof data.detail === 'string' ? data.detail : '暫定価格のサービス項目が含まれています。'
}

export const extractFilename = (contentDisposition?: string, fallback = 'document.pdf') => {
  if (!contentDisposition) return fallback
  const encoded = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
  if (encoded) return decodeURIComponent(encoded[1])
  const plain = contentDisposition.match(/filename="?([^";]+)"?/)
  return plain ? plain[1] : fallback
}

export const saveBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}
