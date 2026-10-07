import assert from 'node:assert/strict'
import { test } from 'node:test'
import { NAVIGATION, filterNavigation, isGroup, navigationPaths } from '../src/utils/navigation'

const all = () => true

test('構成：作業台・案件管理（案件一覧が先頭）・社内資料管理（会計・不動産・書類）・帳票・システム設定', () => {
  assert.deepEqual(NAVIGATION.map((g) => g.label), ['作業台', '案件管理', '社内資料管理', '帳票管理', 'システム設定'])
  const cases = NAVIGATION.find((g) => g.key === 'cases')!
  assert.equal((cases.children[0] as { path: string }).path, '/cases')
  const internal = NAVIGATION.find((g) => g.key === 'internal')!
  const labels = internal.children.map((c) => c.label)
  assert.deepEqual(labels, ['会計資料', '不動産資料', '書類管理'])
  assert.deepEqual(navigationPaths([NAVIGATION[0]]), ['/daily-plan', '/daily-reports', '/dashboard'])
})

test('同じ画面への入口は 1 つだけ。LIST 取込・今日の作業台はナビゲーションに無い', () => {
  const paths = navigationPaths(NAVIGATION)
  assert.equal(new Set(paths).size, paths.length)
  assert.ok(!paths.includes('/real-estate/import'))
  assert.ok(!paths.includes('/workbench'))
})

test('権限で絞り込み、空のグループは出さない', () => {
  const caseStaff = filterNavigation(NAVIGATION, (code) => code === 'cases.use_cases')
  assert.deepEqual(caseStaff.map((g) => g.key), ['workbench', 'cases', 'internal', 'system'])
  const internal = caseStaff.find((g) => g.key === 'internal')!
  assert.deepEqual(navigationPaths([internal]), ['/documents'])  // 会計・不動産の権限が無ければ出さない
  const accountantOnly = filterNavigation(NAVIGATION, (code) => ['accounting.use_expense', 'accounting.use_income'].includes(code))
  const accounting = accountantOnly.find((g) => g.key === 'internal')!.children.find(isGroup)!
  assert.deepEqual(navigationPaths([{ ...accounting, children: accounting.children }]).sort(),
    ['/accounting', '/accounting/expense-categories', '/accounting/expenses', '/accounting/income-sources'].sort())
  assert.ok(!navigationPaths(accountantOnly).includes('/cases'))
  // 会計の権限が無い人には、収入元だけの権限があっても会計資料は出さない（従来と同じ）
  const incomeOnly = filterNavigation(NAVIGATION, (code) => code === 'accounting.use_income')
  assert.ok(!navigationPaths(incomeOnly).includes('/accounting/income-sources'))
  assert.deepEqual(navigationPaths(filterNavigation(NAVIGATION, () => false)), ['/settings'])
  assert.equal(navigationPaths(filterNavigation(NAVIGATION, all)).length, navigationPaths(NAVIGATION).length)
})

test('P4：サービス項目・料金は管理する人だけにメニューを出す（選ぶだけの職員には出さない）', () => {
  const staff = filterNavigation(NAVIGATION, (code) => ['cases.use_cases', 'accounting.use_service_item'].includes(code))
  assert.ok(!navigationPaths(staff).includes('/vouchers/service-items'))
  const manager = filterNavigation(NAVIGATION, (code) => ['accounting.use_service_item', 'accounting.manage_service_item'].includes(code))
  assert.ok(navigationPaths(manager).includes('/vouchers/service-items'))
})
