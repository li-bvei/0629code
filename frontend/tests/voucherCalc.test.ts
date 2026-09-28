import assert from 'node:assert/strict'
import { test } from 'node:test'
import { lineAmounts, roundHalfUp, summarizeLines } from '../src/utils/voucherCalc'

test('税込 10% は内税で税抜・税額に分ける（後端と同じ四捨五入）', () => {
  assert.deepEqual(lineAmounts({ quantity: 1, unit_price: 55000 }), { total: 55000, taxExcluded: 50000, tax: 5000, taxCategory: 'tax_10' })
  assert.deepEqual(lineAmounts({ quantity: 1, unit_price: 105, tax_category: 'tax_10' }).taxExcluded, 95)
})

test('税抜入力は外税で加算、非課税は税額 0', () => {
  assert.deepEqual(lineAmounts({ quantity: 2, unit_price: 1000, price_type: 'tax_excluded', tax_category: 'tax_8' }),
    { total: 2160, taxExcluded: 2000, tax: 160, taxCategory: 'tax_8' })
  assert.equal(lineAmounts({ quantity: 1, unit_price: 4000, tax_category: 'non_taxable' }).tax, 0)
})

test('合計：空行は無視し、税区分ごとに集計する', () => {
  const s = summarizeLines([
    { item_name: '申請取次', quantity: 1, unit_price: 55000 },
    { item_name: '収入印紙', quantity: 1, unit_price: 4000, tax_category: 'non_taxable' },
    { item_name: '', quantity: '', unit_price: '' },
  ])
  assert.equal(s.total, 59000)
  assert.equal(s.tax_total, 5000)
  assert.equal(s.subtotal_non_taxable, 4000)
})

test('ROUND_HALF_UP：0.5 は切り上げ', () => {
  assert.equal(roundHalfUp(2.5), 3)
  assert.equal(roundHalfUp(-2.5), -3)
  assert.equal(roundHalfUp(2.4999), 2)
})
