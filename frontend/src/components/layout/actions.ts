// 操作ボタンの共通定義と振り分け（ResponsiveActionBar・TableRowActions で共用）。
// 表示・非表示や権限の判定は呼び出し側で行い、ここでは並べ方だけを決める。

export type ActionButtonType = '' | 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'

export interface ActionItem {
  key: string
  label: string
  type?: ActionButtonType
  plain?: boolean
  disabled?: boolean
  loading?: boolean
  hidden?: boolean
  /** 危険な操作（メニュー内で赤字・区切り線の下に出す） */
  danger?: boolean
  /**
   * 'never'：常にボタンとして出す／'auto'（既定）：狭い画面では「その他」へ／'always'：常に「その他」の中
   */
  collapse?: 'never' | 'auto' | 'always'
  onClick: () => void
}

export interface SplitActions {
  /** 常にボタンで出すもの */
  pinned: ActionItem[]
  /** 広い画面ではボタン、狭い画面では「その他」に入るもの */
  collapsible: ActionItem[]
  /** 常に「その他」に入るもの */
  overflow: ActionItem[]
}

/** ヘッダー・詳細画面の操作列：collapse 指定で 3 つに振り分ける（順序は保つ）。 */
export function splitBarActions(actions: ActionItem[]): SplitActions {
  const result: SplitActions = { pinned: [], collapsible: [], overflow: [] }
  for (const action of actions) {
    if (action.hidden) continue
    if (action.collapse === 'never') result.pinned.push(action)
    else if (action.collapse === 'always') result.overflow.push(action)
    else result.collapsible.push(action)
  }
  return result
}

/**
 * 表の行操作：先頭 inline 個をボタンで出し、残りを「その他」に入れる。
 * 危険な操作は inline に入れず、常にメニューの最後へ回す（誤クリック防止）。
 */
export function splitRowActions(actions: ActionItem[], inline: number): { inline: ActionItem[], overflow: ActionItem[] } {
  const visible = actions.filter((action) => !action.hidden)
  const safe = visible.filter((action) => !action.danger && action.collapse !== 'always')
  const shown = safe.slice(0, Math.max(0, inline))
  const rest = visible.filter((action) => !shown.includes(action))
  rest.sort((a, b) => Number(Boolean(a.danger)) - Number(Boolean(b.danger)))
  return { inline: shown, overflow: rest }
}
