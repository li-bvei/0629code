import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { ExpenseCategorySuggestions } from '../src/types/accounting'
import { canOfferRemember, pendingPlaceRecommendations } from '../src/utils/expenseCategory'

const suggestions = (rows: ExpenseCategorySuggestions['place_recommendations']): ExpenseCategorySuggestions => ({
  query: '', matches: [], normalized: null, recommendations: [], place_recommendations: rows, source_scope: 'own_history',
})
const parking = { name: '停车费', match_field: 'place' as const, pattern: '駐車場', scope: 'office' as const, reason: '場所に「駐車場」を含む', requires_confirmation: true }

test('場所からの提案：採用するまで候補として出し、採用済みなら出さない', () => {
  assert.deepEqual(pendingPlaceRecommendations(suggestions([parking]), ''), [parking])
  assert.deepEqual(pendingPlaceRecommendations(suggestions([parking]), '雑費'), [parking]) // 手入力は変えずに候補だけ示す
  assert.deepEqual(pendingPlaceRecommendations(suggestions([parking]), '停车费'), [])
  assert.deepEqual(pendingPlaceRecommendations(null, ''), [])
})

test('対応の記憶：場所とカテゴリが入力済みで、同じ対応の規則がまだ無いときだけ選べる', () => {
  assert.equal(canOfferRemember(suggestions([]), '喫茶ルノアール', '会議費'), true)
  assert.equal(canOfferRemember(suggestions([parking]), '新宿駐車場', '停车费'), false) // 既に規則がある
  assert.equal(canOfferRemember(suggestions([parking]), '新宿駐車場', '雑費'), true)
  assert.equal(canOfferRemember(suggestions([]), '', '会議費'), false)
  assert.equal(canOfferRemember(suggestions([]), '喫茶ルノアール', '  '), false)
  assert.equal(canOfferRemember(null, '喫茶ルノアール', '会議費'), true)
})
