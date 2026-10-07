// 左側ナビゲーションの構成（P3）。表示は業務権限で絞る（表示上の制御。API 側でも必ず判定する）。
// 同じ画面への正式な入口は 1 つだけ。LIST 取込は不動産資料の画面内の操作、旧「今日の作業台」は毎日の計画に統合。
// 不動産と会計は「社内資料管理」の下に並べるが、画面・API・権限・データは別のまま（ナビゲーションだけの整理）。

export type NavIcon =
  | 'Calendar' | 'Notebook' | 'DataAnalysis' | 'Briefcase' | 'Tickets' | 'EditPen' | 'User' | 'OfficeBuilding'
  | 'FolderOpened' | 'Coin' | 'Money' | 'List' | 'Van' | 'Files' | 'Document' | 'Reading' | 'Setting'

export interface NavItem {
  path: string
  label: string
  icon: NavIcon
  /** すべて必要な権限 */
  requires?: string[]
  tag?: string
}

export interface NavGroup {
  key: string
  label: string
  icon: NavIcon
  /** グループ自体に必要な権限（どれか 1 つ） */
  requiresAny?: string[]
  children: Array<NavItem | NavGroup>
}

const CASES = 'cases.use_cases'
const EXPENSE = 'accounting.use_expense'

export const NAVIGATION: NavGroup[] = [
  {
    key: 'workbench', label: '作業台', icon: 'Calendar', children: [
      { path: '/daily-plan', label: '毎日の計画', icon: 'Calendar', requires: [CASES] },
      { path: '/daily-reports', label: '業務報告', icon: 'Notebook', requires: [CASES] },
      { path: '/dashboard', label: 'ダッシュボード', icon: 'DataAnalysis', requires: [CASES] },
    ],
  },
  {
    key: 'cases', label: '案件管理', icon: 'Briefcase', children: [
      { path: '/cases', label: '案件一覧', icon: 'Tickets', requires: [CASES] },
      { path: '/reception/new', label: '新規受付', icon: 'EditPen', requires: [CASES] },
      { path: '/customers', label: '顧客管理', icon: 'User', requires: [CASES] },
      { path: '/companies', label: '会社管理', icon: 'OfficeBuilding', requires: [CASES] },
    ],
  },
  {
    key: 'internal', label: '社内資料管理', icon: 'FolderOpened', children: [
      {
        key: 'accounting', label: '会計資料', icon: 'Coin', children: [
          { path: '/accounting', label: '会計ダッシュボード', icon: 'DataAnalysis', requires: [EXPENSE] },
          { path: '/accounting/expenses', label: '支出記録', icon: 'Money', requires: [EXPENSE] },
          { path: '/accounting/expense-categories', label: '支出カテゴリ', icon: 'List', requires: [EXPENSE] },
          { path: '/accounting/income-sources', label: '収入元', icon: 'Coin', requires: [EXPENSE, 'accounting.use_income'] },
          { path: '/accounting/vehicle-usages', label: '車両使用記録', icon: 'Van', requires: [EXPENSE, 'accounting.use_vehicle'] },
          { path: '/accounting/projects', label: 'プロジェクト収支表', icon: 'Notebook', requires: [EXPENSE, 'accounting.use_project'] },
        ],
      },
      { path: '/real-estate', label: '不動産資料', icon: 'OfficeBuilding', requires: ['real_estate.use_real_estate'] },
      { path: '/documents', label: '書類管理', icon: 'Files', requires: [CASES] },
    ],
  },
  {
    key: 'vouchers', label: '帳票管理', icon: 'Document', children: [
      { path: '/vouchers/invoices', label: '請求書・領収書', icon: 'Document', requires: ['accounting.use_voucher'] },
      { path: '/vouchers/visa-return', label: '返签 visa 表', icon: 'Files', requires: ['accounting.use_visa'] },
      { path: '/vouchers/tax-renewal', label: '税务证明更新用', icon: 'Reading', requires: ['accounting.use_tax_renewal'] },
      { path: '/vouchers/seifu-notice', label: '清風合格通知書', icon: 'Document', requires: ['accounting.use_seifu'], tag: '暂停' },
      { path: '/vouchers/estimates', label: '見積書', icon: 'Document', requires: ['accounting.use_estimate'] },
      { path: '/vouchers/contracts', label: '契約書', icon: 'Document', requires: ['accounting.use_contract'] },
      // P4：管理する人（会計管理者・システム管理者）にだけメニューを出す。選ぶだけの職員は受付・帳票の中で使う
      { path: '/vouchers/service-items', label: 'サービス項目・料金', icon: 'List', requires: ['accounting.manage_service_item'] },
      { path: '/vouchers/certificates', label: '証明書', icon: 'Document', requires: ['accounting.use_voucher'], tag: '準備中' },
      { path: '/vouchers/others', label: 'その他帳票', icon: 'Document', requires: ['accounting.use_voucher'], tag: '準備中' },
    ],
  },
  {
    key: 'system', label: 'システム設定', icon: 'Setting', children: [
      { path: '/case-checklists', label: '案件テンプレート・担当設定', icon: 'List', requires: [CASES] },
      { path: '/settings', label: 'アカウント・事務所設定', icon: 'Setting' },
    ],
  },
]

export const isGroup = (entry: NavItem | NavGroup): entry is NavGroup => 'children' in entry

// 権限で見えない項目を除き、空になったグループも除く
export const filterNavigation = (groups: NavGroup[], can: (code: string) => boolean): NavGroup[] => {
  const visible = (entry: NavItem | NavGroup): NavItem | NavGroup | null => {
    if (isGroup(entry)) {
      if (entry.requiresAny && !entry.requiresAny.some(can)) return null
      const children = entry.children.map(visible).filter((child): child is NavItem | NavGroup => child !== null)
      return children.length ? { ...entry, children } : null
    }
    return (entry.requires ?? []).every(can) ? entry : null
  }
  return groups.map(visible).filter((group): group is NavGroup => group !== null) as NavGroup[]
}

export const navigationPaths = (groups: NavGroup[]): string[] => groups.flatMap((group) => group.children.flatMap(
  (entry) => (isGroup(entry) ? navigationPaths([entry]) : [entry.path]),
))
