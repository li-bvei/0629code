import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  addDays, canEditItem, carryBatchSummary, carryDateHint, errorCode, isConflict, moveItem, nextWeekday, planErrorText, planSummary,
  sortPlan, toIsoDate, versionPayload,
} from '../src/utils/dailyPlan'

test('結転先の既定は次の月〜金（金・土・日 → 月）', () => {
  assert.equal(nextWeekday('2026-10-02'), '2026-10-05')  // 金
  assert.equal(nextWeekday('2026-10-03'), '2026-10-05')  // 土
  assert.equal(nextWeekday('2026-10-04'), '2026-10-05')  // 日
  assert.equal(nextWeekday('2026-10-05'), '2026-10-06')  // 月
  assert.equal(addDays('2026-12-31', 1), '2027-01-01')
  assert.equal(toIsoDate(new Date(2026, 0, 5)), '2026-01-05')
})

test('並び：sort_order→ID、上下移動（端では変わらない）と版の送信', () => {
  const rows = [{ id: 3, sort_order: 20, updated_at: 'v3' }, { id: 1, sort_order: 10, updated_at: 'v1' }, { id: 2, sort_order: 20, updated_at: 'v2' }]
  const sorted = sortPlan(rows)
  assert.deepEqual(sorted.map((r) => r.id), [1, 2, 3])
  assert.deepEqual(moveItem(sorted, 3, -1).map((r) => r.id), [1, 3, 2])
  assert.equal(moveItem(sorted, 1, -1), sorted)
  assert.deepEqual(versionPayload(sorted), [{ id: 1, version: 'v1' }, { id: 2, version: 'v2' }, { id: 3, version: 'v3' }])
})

test('集計と編集可否（他人の計画・結転済みは編集しない）', () => {
  const summary = planSummary([{ status: 'completed' }, { status: 'pending' }, { status: 'paused' }, { status: 'carried_over' }, { status: 'cancelled' }])
  assert.deepEqual(summary, { total: 5, done: 1, open: 2, carried: 1 })
  assert.equal(canEditItem({ status: 'pending' }, false), true)
  assert.equal(canEditItem({ status: 'pending' }, true), false)
  assert.equal(canEditItem({ status: 'carried_over' }, false), false)
})

test('失敗の文言：409・403・404・項目エラー・通信エラー・JSON 以外', () => {
  const conflict = { response: { status: 409, data: { detail: '他の操作で内容が変わっています。', code: 'conflict' } } }
  assert.equal(planErrorText(conflict), '他の操作で内容が変わっています。')
  assert.equal(isConflict(conflict), true)
  assert.equal(errorCode({ response: { status: 409, data: { code: 'edited_exists' } } }), 'edited_exists')
  assert.equal(planErrorText({ response: { status: 403, data: { detail: '他の人の計画は変更できません。' } } }), '他の人の計画は変更できません。')
  assert.match(planErrorText({ response: { status: 404 } }), /見つかりません/)
  assert.equal(planErrorText({ response: { status: 400, data: { title: ['内容を入力してください。'] } } }), '内容を入力してください。')
  assert.match(planErrorText(new Error('Network Error')), /通信できませんでした/)
  assert.equal(planErrorText({ response: { status: 500, data: '<html>' } }, '保存できませんでした。'), '保存できませんでした。')
  assert.equal(carryBatchSummary({ succeeded: 2, failed: 1 }), '2 件を結転しました。1 件は結転できませんでした。')
})

test('P6：結転先が休日・対応範囲外なら注意を出す（止めはしない）', () => {
  assert.equal(carryDateHint(null), '')
  assert.equal(carryDateHint({ is_business_day: true, supported: true, notice: '' }), '')
  assert.equal(carryDateHint({ is_business_day: false, supported: true, notice: '11月3日は祝日（文化の日）です。' }),
    '11月3日は祝日（文化の日）です。休日でも結転できます。')
  assert.match(carryDateHint({ is_business_day: true, supported: false, notice: '2000～2050 年以外は祝日を判定できません' }), /判定できません/)
})

test('P6：結転の既定日は後端の暦の次の営業日（読めないときだけ月〜金）', async () => {
  const { readFileSync } = await import('node:fs')
  const { resolve } = await import('node:path')
  const page = readFileSync(resolve(process.cwd(), 'src/pages/DailyPlanPage.vue'), 'utf8')
  assert.match(page, /getCalendarDay\(workDate\.value\)/)
  assert.match(page, /info\.next_business_day/)
  assert.match(page, /carryDate\.value === provisional/)  // 利用者が変えた日付は上書きしない
})
