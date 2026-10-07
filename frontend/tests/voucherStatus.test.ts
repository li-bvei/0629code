import assert from 'node:assert/strict'
import { test } from 'node:test'
import { transitionNotice } from '../src/components/vouchers/voucherStatus'

test('請求書・領収書：下書きへ戻すときは再編集・再発行の説明、発行するときは編集不可の説明', () => {
  assert.match(transitionNotice('vouchers', 'issued', 'draft'), /下書きに戻すと内容を編集できます/)
  assert.match(transitionNotice('vouchers', 'voided', 'draft'), /新しい版/)
  assert.match(transitionNotice('vouchers', 'draft', 'issued'), /下書きに戻します/)
  assert.equal(transitionNotice('vouchers', 'issued', 'paid'), '')
  assert.equal(transitionNotice('vouchers', 'draft', 'cancelled'), '')
})

test('見積書・契約書は従来の説明のまま', () => {
  assert.match(transitionNotice('estimates', 'draft', 'submitted'), /編集できなくなります/)
  assert.equal(transitionNotice('estimates', 'submitted', 'accepted'), '')
})
