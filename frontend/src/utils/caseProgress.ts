// 「進捗を更新」ダイアログでの申請日（入管局受理日）の扱い。
// 申請日は審査期間の計算の起点。申請より後の進捗へ直接進める場合にも入力欄を出し、未入力のまま
// 進めて一覧の「審査期間」が空になることを防ぐ。
export const POST_APPLICATION_STATUSES = [
  'applied', 'under_review', 'additional_documents', 'additional_documents_submitted', 'approved', 'rejected',
] as const

const isPostApplication = (status: string | null | undefined) =>
  (POST_APPLICATION_STATUSES as readonly string[]).includes(status ?? '')

// 申請日・受付番号の入力欄を出すか：申請以降の進捗を選んだとき、または既に申請日が入っているとき
export const shouldShowAppliedFields = (newStatus: string | null | undefined, currentAppliedAt: string | null | undefined) =>
  isPostApplication(newStatus) || Boolean(currentAppliedAt)

// ダイアログを開いたとき・進捗を選び直したときの申請日の初期値。
// 「申請済み」へ進めるときだけ今日を仮に入れる。それ以外で未登録なら空のまま（実際の日付を入力してもらう）。
export const defaultAppliedAt = (
  newStatus: string | null | undefined, currentAppliedAt: string | null | undefined, today: string,
): string | null => currentAppliedAt || (newStatus === 'applied' ? today : null)

// 申請以降の進捗なのに申請日が空：確認を出す（審査期間が計算できなくなるため）
export const isAppliedAtMissing = (newStatus: string | null | undefined, appliedAt: string | null | undefined) =>
  isPostApplication(newStatus) && !appliedAt
