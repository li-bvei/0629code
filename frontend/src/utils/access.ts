// 画面遷移・メニュー表示用の業務権限マップ。安全の根拠ではない（後端が常に判定する）。
const ROUTE_PERMISSIONS: Array<[string, string]> = [
  ['/accounting/income-sources', 'accounting.use_income'],
  ['/accounting/vehicle-usages', 'accounting.use_vehicle'],
  ['/accounting/projects', 'accounting.use_project'],
  ['/accounting', 'accounting.use_expense'],
  ['/vouchers/visa-return', 'accounting.use_visa'],
  ['/vouchers/tax-renewal', 'accounting.use_tax_renewal'],
  ['/vouchers/seifu-notice', 'accounting.use_seifu'],
  ['/vouchers', 'accounting.use_voucher'],
  ['/reports', 'accounting.use_voucher'],
  ['/dashboard', 'cases.use_cases'],
  ['/reception', 'cases.use_cases'],
  ['/cases', 'cases.use_cases'],
  ['/case-checklists', 'cases.use_cases'],
  ['/customers', 'cases.use_cases'],
  ['/companies', 'cases.use_cases'],
  ['/employees', 'cases.use_cases'],
  ['/tasks', 'cases.use_cases'],
  ['/reminders', 'cases.use_cases'],
  ['/timelines', 'cases.use_cases'],
  ['/documents', 'cases.use_cases'],
]

export const requiredPermissionFor = (path: string): string | null => {
  const match = ROUTE_PERMISSIONS.find(([prefix]) => path === prefix || path.startsWith(`${prefix}/`))
  return match ? match[1] : null
}

export const landingPath = (can: (code: string) => boolean): string => {
  if (can('cases.use_cases')) return '/dashboard'
  if (can('accounting.use_expense')) return '/accounting/expenses'
  return '/settings'
}
