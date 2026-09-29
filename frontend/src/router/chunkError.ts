import { ElMessageBox } from 'element-plus'
import { isChunkLoadError } from '../utils/chunkLoad'

let prompting = false

export const handleChunkLoadError = (error: unknown, targetPath?: string) => {
  if (!isChunkLoadError(error)) return
  if (prompting) return
  prompting = true
  ElMessageBox.confirm(
    '画面の読み込みに失敗しました。通信状態を確認するか、システムが更新された可能性があるため再読み込みしてください。',
    '画面を読み込めませんでした',
    { confirmButtonText: '再読み込み', cancelButtonText: '閉じる', type: 'error' },
  )
    .then(() => {
      // 行き先の画面を開き直す（ログイン状態は Cookie のまま保持される）
      window.location.assign(targetPath || window.location.href)
    })
    .catch(() => undefined)
    .finally(() => {
      prompting = false
    })
}
