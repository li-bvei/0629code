import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { VisaGuarantorTemplate } from '../src/types/accounting'
import { applyGuarantorTemplateToForm, guarantorSources, stepProblems, visaErrorView, type VisaFlowForm } from '../src/utils/visaFlow'

const template = {
  id: 3, name: '公文', guarantor_name: '公文 慎吾', guarantor_name_en: 'KUMON SHINGO', guarantor_phone: '06-1111-2222',
  guarantor_address: '大阪府', guarantor_address_en: 'Osaka', guarantor_birth_date: '1980-01-02', guarantor_nationality: '日本',
  guarantor_visa_status: '日本人', guarantor_occupation: '会社役員', guarantor_relationship: '雇用主', guarantor_company_name: '',
  note: '', is_active: true, sort_order: 0,
} as unknown as VisaGuarantorTemplate

const empty = (): VisaFlowForm => ({ applicant_name: '王', form_data: { pinyin_name1: 'WANG' } })

test('テンプレートを選ぶと担保人の欄だけが埋まり、全欄がテンプレート由来になる', () => {
  const form = applyGuarantorTemplateToForm(empty(), template)
  assert.equal(form.guarantor_name, '公文 慎吾')
  assert.equal(form.form_data.guarantor_name_en, 'KUMON SHINGO')
  assert.equal(form.form_data.pinyin_name1, 'WANG') // 申請人の欄は変えない
  assert.equal(form.applicant_name, '王')
  const sources = guarantorSources(form, template)
  assert.equal(sources.guarantor_name, 'template')
  assert.equal(sources.guarantor_birth_date, 'template')
})

test('手入力で変えた欄は manual、空欄は空、テンプレート無しはすべて manual', () => {
  const form = applyGuarantorTemplateToForm(empty(), template)
  form.guarantor_phone = '080-0000-0000'
  form.form_data.guarantor_visa_status = ''
  const sources = guarantorSources(form, template)
  assert.equal(sources.guarantor_phone, 'manual')
  assert.equal(sources.guarantor_visa_status, '')
  assert.equal(guarantorSources(form, null).guarantor_name, 'manual')
})

test('段階ごとの必須確認', () => {
  assert.deepEqual(stepProblems(0, empty(), true, null), ['生年月日', '国籍', '旅券番号', '旅券の有効期限'])
  // 申請人氏名だけでは様式の氏名欄が空になるため、英文姓か中文姓を求める
  assert.ok(stepProblems(0, { applicant_name: '王', form_data: {} }, true, null).includes('英文姓（または中文姓）'))
  assert.ok(!stepProblems(0, { applicant_name: '王', form_data: { chinese_name1: '王' } }, true, null).includes('英文姓（または中文姓）'))
  assert.deepEqual(stepProblems(1, empty(), true, null), ['担保人テンプレート', '担保人氏名', '担保人住所', '担保人電話番号'])
  const filled = applyGuarantorTemplateToForm(empty(), template)
  assert.deepEqual(stepProblems(1, filled, true, 3), [])
  assert.deepEqual(stepProblems(1, { ...filled, guarantor_name: '' }, false, null), ['担保人氏名'])
})

test('生成失敗の表示：種別ごとの題名・詳細・項目', () => {
  const mismatch = visaErrorView({ response: { status: 422, data: { code: 'template_field_mismatch', detail: '一致しません', fields: ['a→b'] } } })
  assert.deepEqual(mismatch, { title: 'PDF テンプレートと項目対応表が一致しません', detail: '一致しません', fields: ['a→b'] })
  const missing = visaErrorView({ response: { status: 400, data: { code: 'missing_fields', detail: '不足', fields: [{ field: 'x', label: '旅券番号' }] } } })
  assert.deepEqual(missing.fields, ['旅券番号'])
  assert.equal(visaErrorView({ response: { status: 403 } }).title, '権限がありません')
  assert.equal(visaErrorView(new Error('network')).title, 'PDF を作成できませんでした')
})
