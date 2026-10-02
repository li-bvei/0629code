import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildBulkRequest, buildPreviewRequest, describeBulkChanges, emptyBulkForm, type BulkTarget } from '../src/utils/realEstateBulk'

const ids: BulkTarget = { mode: 'ids', selection_token: 'ids-token', count: 2, filter_summary: ['一覧で選択した記録'] }
const filtered: BulkTarget = { mode: 'filter', selection_token: 'signed-token', count: 36, filter_summary: ['保存状態：利用中', '段階：契約'] }

test('チェックした項目だけを送る（未チェックの入力値は送らない）', () => {
  const form = emptyBulkForm()
  form.enabled.stage = true
  form.stage = 'settled'
  form.responsible_name = '入力したがチェックなし'
  const built = buildBulkRequest(ids, form)
  assert.deepEqual(built.request, {
    selection_token: 'ids-token', changes: { stage: 'settled' }, clear_fields: [], expected_count: 2,
  })
  // ID を直接送る経路は無い（版の確認を迂回しない）
  assert.ok(!('selection' in (built.request ?? {})) && !('ids' in (built.request ?? {})))
})

test('絞り込み結果の全件：ID や件数を自分で作らず、後端が固定したトークンと件数を送る', () => {
  const form = emptyBulkForm()
  form.enabled.responsible_name = true
  form.responsible_name = ' 田中 '
  form.enabled.transaction_date = true
  form.transaction_date = '2026-10-31'
  const built = buildBulkRequest(filtered, form)
  assert.deepEqual(built.request, {
    selection_token: 'signed-token',
    changes: { responsible_name: '田中', transaction_date: '2026-10-31' }, clear_fields: [], expected_count: 36,
  })
})

test('空欄にするのは明示したときだけ（空文字のまま送らない）', () => {
  const form = emptyBulkForm()
  form.enabled.responsible_name = true
  assert.equal(buildBulkRequest(ids, form).error, '担当者の変更後の値を入力してください。')
  form.clear.responsible_name = true
  form.enabled.transaction_date = true
  form.clear.transaction_date = true
  const built = buildBulkRequest(ids, form)
  assert.deepEqual(built.request?.changes, {})
  assert.deepEqual(built.request?.clear_fields, ['responsible_name', 'transaction_date'])
})

test('対象なし・変更なしは送信しない', () => {
  const form = emptyBulkForm()
  assert.equal(buildBulkRequest(ids, form).error, '変更する項目にチェックを入れてください。')
  form.enabled.stage = true
  form.stage = 'settled'
  assert.equal(buildBulkRequest(null, form).error, '対象の記録を選択してください。')
  assert.equal(buildBulkRequest({ ...ids, count: 0 }, form).error, '対象の記録を選択してください。')
  assert.equal(buildBulkRequest({ ...ids, selection_token: '' }, form).error, '対象の記録を選択してください。')
  form.clear.responsible_name = true // 段階は空欄にできない・未チェックの空欄化は無視
  assert.deepEqual(buildBulkRequest(ids, form).request?.clear_fields, [])
})

test('手動選択：ページをまたいだ記録も、一覧に表示された時点の updated_at を付けて後端で固定する', () => {
  const rows = [
    { id: 101, updated_at: '2026-10-02T10:00:00.123456+09:00', party_name: '表示用の他の項目' },
    { id: 245, updated_at: '2026-10-01T18:30:00.000001+09:00', party_name: '別ページの記録' },
  ]
  assert.deepEqual(buildPreviewRequest(rows), {
    selection: { mode: 'ids', items: [
      { id: 101, updated_at: '2026-10-02T10:00:00.123456+09:00' },
      { id: 245, updated_at: '2026-10-01T18:30:00.000001+09:00' },
    ] },
  })
})

test('確認文', () => {
  const lines = describeBulkChanges({
    selection_token: 't', changes: { stage: 'settled', responsible_name: '田中' },
    clear_fields: ['transaction_date'], expected_count: 1,
  }, (value) => (value === 'settled' ? '完了' : value))
  assert.deepEqual(lines, ['段階 →「完了」', '担当者 →「田中」', '取引日 → 空欄にする'])
})
