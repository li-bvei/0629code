import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildPersonChanges } from '../src/utils/familyPerson'

const original = {
  name: '配偶者', name_kana: '', birth_date: '1991-03-03', gender: 'female', nationality: '中国',
  phone: '', email: '', postal_code: '', address: '', residence_status: '家族滞在',
  residence_card_no: 'SP********AA', residence_expiry: '2026-12-01', passport_no: '', passport_expiry: null,
}

test('変更した項目だけを送る（伏せ字のままの証件番号は送らない）', () => {
  const form = { ...original, birth_date: '1991-03-04', residence_expiry: '2027-12-01', my_number: '' }
  assert.deepEqual(buildPersonChanges(original, form), { birth_date: '1991-03-04', residence_expiry: '2027-12-01' })
})

test('何も変えていなければ空（関係だけの編集）', () => {
  assert.deepEqual(buildPersonChanges(original, { ...original, my_number: '' }), {})
  assert.deepEqual(buildPersonChanges(original, { ...original, name_kana: '  ', passport_expiry: '' }), {})
})

test('日付を消したときは null、文字を消したときは空文字、マイナンバーは入力時だけ', () => {
  const form = { ...original, residence_expiry: null, nationality: '', my_number: ' 123412341234 ' }
  assert.deepEqual(buildPersonChanges(original, form), { nationality: '', residence_expiry: null, my_number: '123412341234' })
})
