import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  createLine, duplicateLine, isBlankLine, keyForSavedRow, moveLine, nextFocus, removeLine, toPayloadLines, validateLines,
  type VoucherLine,
} from '../src/utils/voucherLines'
import { summarizeLines } from '../src/utils/voucherCalc'

const line = (extra: Partial<VoucherLine>): VoucherLine => ({ ...createLine(), ...extra })

test('複製は直後に同じ内容の新しい行を作り、並び替えと削除は他の行を変えない', () => {
  const a = line({ item_name: 'A', unit_price: 1000 })
  const b = line({ item_name: 'B', unit_price: 2000, unit: '件', note: 'メモ' })
  const duplicated = duplicateLine([a, b], 1)
  assert.deepEqual(duplicated.map((l) => l.item_name), ['A', 'B', 'B'])
  assert.notEqual(duplicated[1].key, duplicated[2].key)
  assert.equal(duplicated[2].note, 'メモ')
  assert.deepEqual(moveLine(duplicated, 0, 1).map((l) => l.item_name), ['B', 'A', 'B'])
  assert.equal(moveLine(duplicated, 0, -1), duplicated) // 先頭より上へは動かない
  assert.deepEqual(removeLine([a, b], 0).map((l) => l.item_name), ['B'])
  assert.equal(removeLine([a], 0).length, 1) // 最後の 1 行を消すと空行が残る
  // P4：後端の line_key は複製に引き継がない（サービス項目は新しい選択として後端が作り直す）
  const linked = line({ item_name: 'S', line_key: 'k1', service_item_id: 7 })
  const copied = duplicateLine([linked], 0)[1]
  assert.equal(copied.line_key, undefined)
  assert.equal(copied.service_item_id, 7)
  assert.equal(linked.line_key, 'k1')
})

test('行ごとの誤り：誤りのある行だけに付き、空行は誤りにしない', () => {
  const ok = line({ item_name: '申請取次', unit_price: 55000 })
  const noName = line({ item_name: '', unit_price: 1000 })
  const badQty = line({ item_name: '翻訳', quantity: 'abc', unit_price: 3000 })
  const blank = createLine()
  const errors = validateLines([ok, noName, badQty, blank])
  assert.deepEqual(Object.keys(errors).map(Number).sort(), [noName.key, badQty.key].sort())
  assert.match(errors[noName.key], /項目／説明/)
  assert.match(errors[badQty.key], /数量/)
  assert.equal(isBlankLine(blank), true)
})

test('保存用：空行を除き、単位・備考を残し、金額は後端と同じ規則で計算する', () => {
  const lines = [line({ item_name: ' 申請取次 ', unit: '件', unit_price: 55000, note: '着手金' }), createLine(),
    line({ item_name: '収入印紙', unit_price: 4000, tax_category: 'non_taxable' })]
  const payload = toPayloadLines(lines)
  assert.equal(payload.length, 2)
  assert.deepEqual([payload[0].item_name, payload[0].unit, payload[0].note, payload[0].line_total, payload[0].tax_amount],
    ['申請取次', '件', '着手金', 55000, 5000])
  assert.ok(!('key' in payload[0]))
  const summary = summarizeLines(payload)
  assert.deepEqual([summary.subtotal, summary.tax_total, summary.total], [54000, 5000, 59000])
})

test('後端の行番号（空行を除いた順）から画面の行を特定する', () => {
  const a = line({ item_name: 'A' })
  const blank = createLine()
  const c = line({ item_name: 'C', quantity: 'x' })
  assert.equal(keyForSavedRow([a, blank, c], 2), c.key)
  assert.equal(keyForSavedRow([a], 5), null)
})

test('Enter の移動順：項目→数量→単位→単価→税区分→備考→次の行（最後なら行を追加）', () => {
  assert.deepEqual(nextFocus('item_name', 0, 3), { rowIndex: 0, field: 'quantity', append: false })
  assert.deepEqual(nextFocus('tax_category', 1, 3), { rowIndex: 1, field: 'note', append: false })
  assert.deepEqual(nextFocus('note', 1, 3), { rowIndex: 2, field: 'item_name', append: false })
  assert.deepEqual(nextFocus('note', 2, 3), { rowIndex: 3, field: 'item_name', append: true })
})
