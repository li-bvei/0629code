import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { test } from 'node:test'
import { maskMyNumber, myNumberErrorMessage } from '../src/utils/myNumber'

test('マイナンバーの伏せ字と、番号を含まないエラー文言', () => {
  assert.doesNotMatch(maskMyNumber(), /\d/)
  assert.match(myNumberErrorMessage({ response: { status: 403 } }), /権限/)
  assert.match(myNumberErrorMessage({ response: { status: 404 } }), /範囲外/)
  assert.match(myNumberErrorMessage({ response: { status: 422 } }), /読み出せません/)
  assert.match(myNumberErrorMessage(new Error('Network Error')), /通信/)
  // 後端の応答本文（仮に番号が含まれていても）を文言に使わない
  const leaked = myNumberErrorMessage({ response: { status: 400, data: { detail: '123456789012' } } })
  assert.doesNotMatch(leaked, /\d{4}/)
})

test('表示した値は部品の中だけに持ち、保存・コピー・URL に出さない', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/components/customers/MyNumberReveal.vue'), 'utf8')
  const script = source.split('</script>')[0]
  const code = source.replace(/^\s*\/\/.*$/gm, '')  // 説明コメントは除いて確認する
  for (const forbidden of [/localStorage/, /sessionStorage/, /clipboard/i, /router\./, /console\./, /useRoute/, /defineStore/]) {
    assert.doesNotMatch(code, forbidden, String(forbidden))
  }
  assert.match(script, /auth\.can\('customers\.reveal_my_number'\)/)
  assert.match(script, /onBeforeUnmount\(hide\)/)
  assert.match(script, /watch\(\(\) => \[props\.kind, props\.targetId, props\.resetKey\], hide\)/)
  // 顧客詳細のタブ（非表示でも DOM に残る）を切り替えたら消す
  const page = readFileSync(resolve(process.cwd(), 'src/pages/CustomerDetailPage.vue'), 'utf8')
  assert.equal((page.match(/<MyNumberReveal [^>]*:reset-key="activeSection"/g) ?? []).length, 2)
  assert.match(script, /token !== requestToken/)  // 遅れて届いた応答は捨てる
  const api = readFileSync(resolve(process.cwd(), 'src/api/customers.ts'), 'utf8')
  assert.match(api, /http\.post<MyNumberRevealResponse>/)  // GET（URL・キャッシュ）ではなく POST
})

test('会社職員：同じ部品・同じ権限で表示し、タブ切り替えと編集画面の開閉で消す', () => {
  const page = readFileSync(resolve(process.cwd(), 'src/pages/CompanyDetailPage.vue'), 'utf8')
  const tags = page.match(/<MyNumberReveal [^>]*>/g) ?? []
  assert.equal(tags.length, 1)
  assert.match(tags[0], /kind="company_staff"/)
  assert.match(tags[0], /:registered="Boolean\(staff\.has_my_number\)"/)
  assert.match(tags[0], /:reset-key="`\$\{activeSection\}:\$\{staffDialogVisible\}`"/)
  assert.doesNotMatch(page, /staff\.my_number\b/)  // 一覧の値（API は返さない）を表示に使わない
  const api = readFileSync(resolve(process.cwd(), 'src/api/customers.ts'), 'utf8')
  assert.match(api, /company_staff: '\/company-staff\/'/)
})
