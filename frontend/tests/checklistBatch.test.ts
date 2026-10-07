import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  batchErrorText, buildChanges, confirmMessage, emptyBatchForm, groupState, hasChanges, notApplicableCount, pruneSelection,
  resultSummary, selectionAfterResult, toggleGroup, toggleSelection, type BatchResponse,
} from '../src/utils/checklistBatch'

test('選択：単独の選択・解除、分組の全選択・解除、一部選択の表示', () => {
  let selected = toggleSelection([], 1)
  assert.deepEqual(selected, [1])
  selected = toggleSelection(selected, 1)
  assert.deepEqual(selected, [])
  const group = [1, 2, 3]
  selected = toggleGroup([2], group)
  assert.deepEqual(selected.sort(), [1, 2, 3])
  assert.equal(groupState(selected, group), 'all')
  selected = toggleGroup(selected, group)
  assert.deepEqual(selected, [])
  assert.equal(groupState([2], group), 'some')
  assert.equal(groupState([9], group), 'none')
  assert.deepEqual(toggleGroup([9], group).sort(), [1, 2, 3, 9])  // 他の分組の選択は残す
  assert.deepEqual(pruneSelection([1, 2, 5], [1, 2]), [1, 2])     // 消えた項目は選択から外す
})

test('変更内容：チェックした項目だけを送る・確認文に件数と変更内容を出す', () => {
  const form = { ...emptyBatchForm(), setStatus: true, isCompleted: true, setReceivedAt: true, receivedAt: '2026-10-04',
    setResponsibleParty: true, responsibleParty: 'customer', setNote: true, note: ' 原本確認 ', noteMode: 'append' as const }
  const changes = buildChanges(form)
  assert.deepEqual(changes, { is_completed: true, received_at: '2026-10-04', responsible_party: 'customer', note: '原本確認', note_mode: 'append' })
  const message = confirmMessage(3, changes, (value) => (value === 'customer' ? '顧客本人' : value))
  assert.match(message, /選択した 3 件/)
  assert.match(message, /状態 → 完了/)
  assert.match(message, /受領日 → 2026-10-04/)
  assert.match(message, /準備者 → 顧客本人/)
  assert.match(message, /備考に追記 → 原本確認/)
  assert.equal(hasChanges(buildChanges(emptyBatchForm())), false)
  assert.equal(hasChanges({ note_mode: 'append' }), false)
  assert.deepEqual(buildChanges({ ...emptyBatchForm(), setReceivedAt: true }), { received_at: null })  // 空欄＝消去
})

test('受領日を設定できない（書類でない）項目の数を事前に知らせる', () => {
  const items = [{ id: 1, item_type: 'document' }, { id: 2, item_type: 'task' }, { id: 3, item_type: 'confirmation' }]
  assert.equal(notApplicableCount({ received_at: '2026-10-04' }, items, [1, 2, 3]), 2)
  assert.equal(notApplicableCount({ is_completed: true }, items, [1, 2, 3]), 0)
})

test('結果：成功・失敗の件数、失敗した項目だけを選択に残す', () => {
  const response: BatchResponse = {
    batch_id: 'x', requested: 3, succeeded: 2, failed: 1,
    results: [
      { id: 1, status: 'success' }, { id: 2, status: 'failed', code: 'conflict', detail: '他の操作で内容が変わっています。' },
      { id: 3, status: 'success' },
    ],
  }
  assert.equal(resultSummary(response), '2 件を更新しました。1 件は更新できませんでした。')
  assert.deepEqual(selectionAfterResult(response), [2])
  assert.equal(resultSummary({ ...response, succeeded: 3, failed: 0, results: [] }), '3 件を更新しました。')
})

test('一括更新そのものの失敗：JSON の理由を出し、HTML などの応答は使わない', () => {
  assert.equal(batchErrorText({ response: { status: 400, data: { item_ids: ['この案件の必要資料ではない項目が含まれています。'] } } }),
    'この案件の必要資料ではない項目が含まれています。')
  assert.match(batchErrorText({ response: { status: 404, data: '<!doctype html>' } }), /見つかりません/)
  assert.match(batchErrorText({ response: { status: 500, data: '<html>' } }), /一括更新できませんでした（500）/)
  assert.match(batchErrorText({ response: { status: 403 } }), /権限/)
  assert.match(batchErrorText(new Error('Network Error')), /通信状況/)
})
