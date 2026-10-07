import assert from 'node:assert/strict'
import { test } from 'node:test'
import { requiredPermissionFor } from '../src/utils/access'
import { isChunkLoadError } from '../src/utils/chunkLoad'

test('帳票・不動産の画面は各自の権限で入る', () => {
  assert.equal(requiredPermissionFor('/vouchers/estimates'), 'accounting.use_estimate')
  assert.equal(requiredPermissionFor('/vouchers/contracts'), 'accounting.use_contract')
  assert.equal(requiredPermissionFor('/vouchers/service-items'), 'accounting.use_service_item')
  assert.equal(requiredPermissionFor('/vouchers/invoices'), 'accounting.use_voucher')
  assert.equal(requiredPermissionFor('/real-estate/import'), 'real_estate.import_real_estate')
  assert.equal(requiredPermissionFor('/real-estate/12'), 'real_estate.use_real_estate')
  assert.equal(requiredPermissionFor('/workbench/today'), 'cases.use_cases')
  assert.equal(requiredPermissionFor('/settings'), null)
})

test('動的 import の失敗を判定する（ブラウザごとの文言）', () => {
  assert.ok(isChunkLoadError(new TypeError('Failed to fetch dynamically imported module: http://x/assets/A.js')))
  assert.ok(isChunkLoadError(new TypeError('Importing a module script failed.')))
  assert.ok(isChunkLoadError(new Error('error loading dynamically imported module')))
  assert.ok(!isChunkLoadError(new Error('Request failed with status code 403')))
  assert.ok(!isChunkLoadError(undefined))
})
