// マイナンバー表示（P6）の画面用の関数。エラー文言にはマイナンバーを含めない（後端の文言も含まない）。

export const maskMyNumber = () => '●●●● ●●●● ●●●●'

export const myNumberErrorMessage = (error: unknown) => {
  const status = (error as { response?: { status?: number } })?.response?.status
  if (status === 403) return 'マイナンバーを表示する権限がありません。'
  if (status === 404) return '対象が見つかりません（表示できる範囲外です）。'
  if (status === 422) return 'マイナンバーを読み出せませんでした。管理者に連絡してください。'
  if (!status) return '通信できませんでした。もう一度お試しください。'
  return '表示できませんでした。もう一度お試しください。'
}
