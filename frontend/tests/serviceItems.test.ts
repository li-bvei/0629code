import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { AccountingVoucherLineItem, ServiceItem } from '../src/types/accounting'
import {
  changedServiceFieldLabels, changedServiceFields, copyLineForDuplicate, floorForLine, isProvisionalService, lineFromServiceItem,
  serviceOptionSublabel, serviceSummary, unlinkServiceItem,
} from '../src/utils/serviceItems'
import {
  caseProgressLabel, currentStepIndex, isWithdrawnStage, needsApplicationCategory, stageChoices, stageSteps,
} from '../src/utils/caseWorkflow'

const item: ServiceItem = {
  id: 7, category: '合成', name: '合成サービス', default_price: '55000', price_type: 'tax_excluded', price_type_display: '税抜',
  professional_type: 'gyousei', professional_type_display: '行政書士', tax_category: 'tax_10', tax_category_display: '10％',
  unit: '件', is_active: true, note: '', sort_order: 1, is_used: false, created_at: '', updated_at: '',
  code: null, price_status: 'confirmed', price_status_display: '確定', price_confirmed_at: null, price_confirmed_by_name: '',
}

test('サービス項目から行を作ると名称・標準価格・税区分・単位を写す（底価は持たない）', () => {
  const line = lineFromServiceItem(item)
  assert.equal(line.item_name, '合成サービス')
  assert.equal(line.unit_price, 55000)
  assert.equal(line.price_type, 'tax_excluded')
  assert.equal(line.unit, '件')
  assert.equal(line.service_item_id, 7)
  assert.equal(JSON.stringify(line).includes('floor'), false)
  assert.equal(lineFromServiceItem({ ...item, default_price: null }).unit_price, '')
  assert.equal(lineFromServiceItem({ ...item, tax_category: 'non_taxable' }).price_type, 'tax_included')
})

test('選んだ後に変えた項目を示し、外す・複製で後端管理のキーを渡さない', () => {
  const line: AccountingVoucherLineItem = { ...lineFromServiceItem(item), line_key: 'k1' }
  assert.deepEqual(changedServiceFields(line), [])
  const edited = { ...line, item_name: '名称を変更', unit_price: 60000, quantity: 3 }
  assert.deepEqual(changedServiceFieldLabels(edited), ['名称', '単価'])
  assert.deepEqual(changedServiceFields({ ...line, tax_category: 'tax_8', unit: '時間' }), ['unit', 'tax_category'])
  const manual = unlinkServiceItem(line)
  assert.equal(manual.service_item_id, undefined)
  assert.equal(manual.service, undefined)
  assert.equal(manual.line_key, 'k1')
  assert.equal(copyLineForDuplicate(line).line_key, undefined)
  assert.equal(copyLineForDuplicate(line).service_item_id, 7)
  assert.equal(serviceSummary(line.service), '標準 ¥55,000（税抜）／件')
  assert.equal(serviceSummary(null), '標準価格なし')
})

test('底価は line_key と項目が一致する記録だけを表示する', () => {
  const line: AccountingVoucherLineItem = { ...lineFromServiceItem(item), line_key: 'k1' }
  const costs = [
    { line_key: 'k1', service_item_id: 8, floor_price: 1, professional_type: '' as const, captured_at: '' },
    { line_key: 'k1', service_item_id: 7, floor_price: 33333, professional_type: 'gyousei' as const, captured_at: '' },
  ]
  assert.equal(floorForLine(line, costs), 33333)
  assert.equal(floorForLine(line, undefined), null)
  assert.equal(floorForLine({ ...line, line_key: undefined }, costs), null)
})

test('業務フローの段階：表示名・ステッパー・変更候補（取下げと復帰を含む）', () => {
  const stages = [
    { id: 1, name: '受付', code: 'reception', base_status: 'accepted' as const, is_withdrawn: false, is_active: true },
    { id: 2, name: '対応中', code: 'in_progress', base_status: 'preparing_documents' as const, is_withdrawn: false, is_active: true },
    { id: 3, name: '旧段階', code: 'old', base_status: 'preparing_documents' as const, is_withdrawn: false, is_active: false },
    { id: 4, name: '取下げ', code: 'withdrawn', base_status: 'withdrawn' as const, is_withdrawn: true, is_active: true },
  ]
  const flowCase = { status: 'accepted' as const, workflow_template: 9, workflow_stage: 1, workflow_stage_name: '受付', workflow_stages: stages }
  assert.equal(caseProgressLabel(flowCase), '受付')
  assert.equal(caseProgressLabel({ status: 'applied' }), '申請済み')
  assert.deepEqual(stageSteps(flowCase).map((s) => s.id), [1, 2, 3])
  assert.equal(currentStepIndex(flowCase), 0)
  assert.deepEqual(stageChoices(flowCase).map((s) => s.id), [2, 4])
  const withdrawn = { ...flowCase, workflow_stage: 4, status: 'withdrawn' as const }
  assert.equal(isWithdrawnStage(withdrawn), true)
  assert.deepEqual(stageChoices(withdrawn).map((s) => s.id), [1, 2])
  assert.equal(needsApplicationCategory({ requires_application_category: false }), false)
  assert.equal(needsApplicationCategory(null), true)
  assert.equal(needsApplicationCategory({}), true)
})

test('P6：暫定価格の項目から作った行は provisional を持ち、候補・明細に「暫定価格」と示す', () => {
  const provisional = { ...item, code: 'translation', price_status: 'provisional' as const, price_status_display: '暫定価格' }
  const line = lineFromServiceItem(provisional)
  assert.equal(line.service?.price_status, 'provisional')
  assert.equal(isProvisionalService(line.service), true)
  assert.equal(isProvisionalService(lineFromServiceItem(item).service), false)
  assert.equal(isProvisionalService(null), false)
  assert.match(serviceOptionSublabel(provisional), /暫定価格$/)
  assert.doesNotMatch(serviceOptionSublabel(item), /暫定価格/)
  assert.equal(JSON.stringify(line).includes('floor'), false)
})

test('P6：発行時の暫定価格確認・価格確定の画面（確認してから再送・二段階確認・409）', async () => {
  const { readFileSync } = await import('node:fs')
  const { resolve } = await import('node:path')
  const { provisionalPriceNotice } = await import('../src/components/vouchers/voucherErrors')
  const error = { response: { status: 400, data: { code: 'provisional_price_confirmation_required', detail: '暫定価格（1 行目）' } } }
  assert.equal(provisionalPriceNotice(error), '暫定価格（1 行目）')
  assert.equal(provisionalPriceNotice({ response: { status: 400, data: { status: 'x' } } }), null)
  assert.equal(provisionalPriceNotice({ response: { status: 409, data: { code: 'provisional_price_confirmation_required' } } }), null)
  const actions = readFileSync(resolve(process.cwd(), 'src/components/vouchers/VoucherStatusActions.vue'), 'utf8')
  assert.match(actions, /provisionalPriceNotice\(error\)/)
  assert.match(actions, /send\(true\)/)
  assert.match(actions, /busy\.value = false/)
  const page = readFileSync(resolve(process.cwd(), 'src/pages/vouchers/ServiceItemsPage.vue'), 'utf8')
  assert.match(page, /canManage\.value && canSeeFloor\.value/)
  assert.match(page, /価格の確定（1\/2）[\s\S]*価格の確定（2\/2）/)
  assert.match(page, /status === 409/)
  assert.match(page, /confirmServiceItemPrice\(row\.id, row\.updated_at\)/)
})
