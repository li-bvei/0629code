import assert from 'node:assert/strict'
import { test } from 'node:test'
import { defaultAppliedAt, isAppliedAtMissing, shouldShowAppliedFields } from '../src/utils/caseProgress'

test('申請日の入力欄：申請以降の進捗へ直接進める場合にも出す', () => {
  for (const status of ['applied', 'under_review', 'additional_documents', 'additional_documents_submitted', 'approved', 'rejected']) {
    assert.equal(shouldShowAppliedFields(status, null), true, status)
  }
  for (const status of ['consultation', 'accepted', 'collecting_documents', 'preparing_documents', 'ready_to_apply', 'withdrawn', 'completed']) {
    assert.equal(shouldShowAppliedFields(status, null), false, status)
  }
  assert.equal(shouldShowAppliedFields('completed', '2026-09-01'), true) // 登録済みなら修正できるよう常に出す
})

test('申請日の初期値：登録済みの値を優先し、今日を仮に入れるのは「申請済み」へ進めるときだけ', () => {
  assert.equal(defaultAppliedAt('under_review', '2026-09-01', '2026-10-03'), '2026-09-01')
  assert.equal(defaultAppliedAt('applied', null, '2026-10-03'), '2026-10-03')
  assert.equal(defaultAppliedAt('under_review', null, '2026-10-03'), null) // 推測で今日を入れない
  assert.equal(defaultAppliedAt('approved', '', '2026-10-03'), null)
})

test('申請以降の進捗で申請日が空なら確認対象', () => {
  assert.equal(isAppliedAtMissing('under_review', null), true)
  assert.equal(isAppliedAtMissing('approved', ''), true)
  assert.equal(isAppliedAtMissing('under_review', '2026-09-01'), false)
  assert.equal(isAppliedAtMissing('collecting_documents', null), false)
  assert.equal(isAppliedAtMissing('completed', null), false)
})
