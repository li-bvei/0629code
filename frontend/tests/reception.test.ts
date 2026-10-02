import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { ReceptionPayload } from '../src/types/api'
import { buildReceptionPayload, receptionErrorView } from '../src/utils/reception'

const form = (): ReceptionPayload => ({
  customer: { name: ' 新規 太郎 ', birth_date: '1995-06-06', postal_code: '160-0022', address: '東京都新宿区' },
  family_members: [
    { name: '', relationship: '', birth_date: null, is_dependent: false },
    { name: '新規 花子', relationship: 'spouse', birth_date: '1996-01-01', is_dependent: true },
  ],
  company: { name: '入力途中の会社', representative_customer_is_current_customer: true },
  case: { case_type_master: 3, application_category: 5, responsible_employee: undefined, accepted_at: '' },
})

test('直接入力：新規顧客をそのまま送り、既存顧客の照合 ID は送らない', () => {
  const payload = buildReceptionPayload(form(), { requestId: 'req-1', companyMode: 'none', existingCompanyId: null })
  assert.equal(payload.request_id, 'req-1')
  assert.equal(payload.customer?.name, '新規 太郎')
  assert.equal(payload.customer?.birth_date, '1995-06-06')
  assert.ok(!('existing_customer_id' in payload))
  assert.ok(!('existing_company_id' in payload))
  assert.equal(payload.company.name, '')
  assert.deepEqual(payload.case, { case_type_master: 3, application_category: 5, responsible_employee: null, accepted_at: null })
})

test('家族：空行は送らず、住所は顧客の値で補う', () => {
  const payload = buildReceptionPayload(form(), { requestId: 'req-1', companyMode: 'none', existingCompanyId: null })
  assert.equal(payload.family_members.length, 1)
  assert.equal(payload.family_members[0].name, '新規 花子')
  assert.equal(payload.family_members[0].address, '東京都新宿区')
})

test('会社：既存を選んだ場合だけ existing_company_id、新規の場合は入力した会社名', () => {
  const existing = buildReceptionPayload(form(), { requestId: 'r', companyMode: 'existing', existingCompanyId: 9 })
  assert.equal(existing.existing_company_id, 9)
  assert.equal(existing.company.name, '')
  const created = buildReceptionPayload(form(), { requestId: 'r', companyMode: 'new', existingCompanyId: null })
  assert.equal(created.company.name, '入力途中の会社')
  assert.ok(!('existing_company_id' in created))
})

test('400 の表示：担当者・生年月日などを項目名付きで示す（汎用の失敗文言にしない）', () => {
  const view = receptionErrorView({
    case: { responsible_employee: ['担当者を選択してください。'] },
    customer: { birth_date: ['この項目は必須です。'] },
    family_members: [{ birth_date: ['新規に顧客として登録する場合は生年月日を入力してください。'] }],
  })
  assert.deepEqual(view.lines, [
    '担当者：担当者を選択してください。',
    '生年月日：この項目は必須です。',
    '家族 1 の生年月日：新規に顧客として登録する場合は生年月日を入力してください。',
  ])
  assert.equal(view.fields['case.responsible_employee'], '担当者を選択してください。')
  assert.equal(view.fields['customer.birth_date'], 'この項目は必須です。')
  assert.deepEqual(receptionErrorView({ detail: '他の担当者の案件は作成できません。' }).lines, ['他の担当者の案件は作成できません。'])
})
