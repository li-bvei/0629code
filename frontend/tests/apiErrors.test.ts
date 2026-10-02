import assert from 'node:assert/strict'
import { test } from 'node:test'
import { describeApiErrors, fieldErrorMap, flattenApiErrors, labelForPath, responseOf } from '../src/utils/apiErrors'

test('flattenApiErrors: 入れ子の項目エラーをパスに展開する', () => {
  const data = { case: { responsible_employee: ['担当者を選択してください。'] }, customer: { birth_date: ['この項目は必須です。'] } }
  assert.deepEqual(flattenApiErrors(data), [
    { path: 'case.responsible_employee', messages: ['担当者を選択してください。'] },
    { path: 'customer.birth_date', messages: ['この項目は必須です。'] },
  ])
})

test('flattenApiErrors: detail・non_field_errors・配列内の辞書・文字列を扱う', () => {
  assert.deepEqual(flattenApiErrors({ detail: '権限がありません。' }), [{ path: '', messages: ['権限がありません。'] }])
  assert.deepEqual(flattenApiErrors({ case: { non_field_errors: ['両方を選択してください。'] } }),
    [{ path: 'case', messages: ['両方を選択してください。'] }])
  assert.deepEqual(flattenApiErrors({ family_members: [{}, { name: ['家族の氏名を入力してください。'] }] }),
    [{ path: 'family_members.1.name', messages: ['家族の氏名を入力してください。'] }])
  assert.deepEqual(flattenApiErrors({ family_members: '見つかりません。' }), [{ path: 'family_members', messages: ['見つかりません。'] }])
  assert.deepEqual(flattenApiErrors(undefined), [])
  assert.deepEqual(flattenApiErrors(''), [])
})

test('describeApiErrors: ラベル付きの文にする（添字は 1 始まり、未登録のパスはそのまま）', () => {
  const labels = { 'case.responsible_employee': '担当者', 'family_members.*.name': '家族 {n} の氏名' }
  assert.deepEqual(
    describeApiErrors({ case: { responsible_employee: ['担当者を選択してください。'] }, family_members: [{}, { name: ['必須です。'] }], x: ['y'] }, labels),
    ['担当者：担当者を選択してください。', '家族 2 の氏名：必須です。', 'x：y'],
  )
  assert.deepEqual(describeApiErrors({ detail: '他の担当者の案件は作成できません。' }, labels), ['他の担当者の案件は作成できません。'])
  assert.equal(labelForPath('', labels), '')
})

test('fieldErrorMap / responseOf', () => {
  assert.deepEqual(fieldErrorMap({ case: { responsible_employee: ['a', 'b'] }, detail: 'x' }), { 'case.responsible_employee': 'a b' })
  assert.deepEqual(responseOf({ response: { status: 400, data: { a: 1 } } }), { status: 400, data: { a: 1 } })
  assert.deepEqual(responseOf(new Error('network')), {})
})
