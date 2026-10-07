// 帳票の状態変更の確認文（画面の説明だけ。可否は後端の Workflow が決める）。
const EDITABLE = new Set(['', 'draft'])
const VOID = new Set(['cancelled', 'voided', 'declined', 'terminated'])

export const transitionNotice = (endpoint: string, current: string, target: string): string => {
  if (endpoint === 'vouchers' && target === 'draft') {
    return '下書きに戻すと内容を編集できます。再発行すると新しい版として履歴に残ります（以前の発行内容も履歴から確認できます）。'
  }
  if (EDITABLE.has(current) && !EDITABLE.has(target) && !VOID.has(target)) {
    return endpoint === 'vouchers'
      ? '変更後は内容を編集できません（直すときは下書きに戻します）。発行時の内容を履歴に記録します。'
      : '変更後は宛先・金額などを編集できなくなります（発行時の内容を記録します）。'
  }
  return ''
}
