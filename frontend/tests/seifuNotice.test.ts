import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  RECIPIENT_NAME_MAX_LENGTH, defaultSeifuTitle, deriveNoticeNumber, formatFileSize, localToday, newRequestId,
  normalizePermitNumber, seifuErrorMessage, validateSeifuForm,
} from '../src/utils/seifuNotice'

const valid = { recipient_name: '合成 太郎', permit_number: '99A0012', issue_date: '2027-01-15' }

test('許可番号を整形し、通知書番号は後端と同じ規則で派生する', () => {
  assert.equal(normalizePermitNumber(' 99a0012 '), '99A0012')
  assert.equal(normalizePermitNumber('９９ａ００１２'), '99A0012')
  assert.equal(deriveNoticeNumber('99a0012'), '99A0012 A')
  assert.equal(deriveNoticeNumber(''), '')
  assert.equal(defaultSeifuTitle('合成 太郎'), '合成 太郎 合格通知書')
})

test('固定三項目の検証：空・不正な日付・長すぎる宛名・危険な文字・不正な許可番号', () => {
  assert.equal(validateSeifuForm(valid), '')
  assert.match(validateSeifuForm({ ...valid, recipient_name: ' ' }), /宛名を入力/)
  assert.match(validateSeifuForm({ ...valid, recipient_name: 'あ'.repeat(RECIPIENT_NAME_MAX_LENGTH + 1) }), /文字以内/)
  assert.match(validateSeifuForm({ ...valid, recipient_name: '合成​太郎' }), /印字できない/)
  assert.match(validateSeifuForm({ ...valid, recipient_name: '合成‮太郎' }), /印字できない/)
  for (const permit of ['', '番号', 'ABC', '12', '99A0012!', '1234567890123', '-99A']) {
    assert.match(validateSeifuForm({ ...valid, permit_number: permit }), /許可番号/, permit)
  }
  for (const issued of ['', '2027-02-30', '2027/01/15', '1999-12-31', '2100-01-01']) {
    assert.match(validateSeifuForm({ ...valid, issue_date: issued }), /通知日/, issued)
  }
})

test('通知日の既定値は端末の日付（UTC ではない）', () => {
  assert.equal(localToday(new Date(2027, 0, 5, 0, 30)), '2027-01-05')
})

test('操作 ID は後端の形式（英数字・ハイフン・下線、64 文字以内）', () => {
  const id = newRequestId()
  assert.match(id, /^[A-Za-z0-9_-]{8,64}$/)
  assert.notEqual(id, newRequestId())
})

test('エラー表示：JSON・blob の応答から後端の文言を読む', async () => {
  const jsonError = { response: { status: 422, data: { code: 'font_missing', detail: '字体がありません' } } }
  assert.equal(await seifuErrorMessage(jsonError, 'x'), '字体がありません')
  const blobError = { response: { status: 400, data: new Blob([JSON.stringify({ code: 'invalid_permit_number', detail: '許可番号が不正' })]) } }
  assert.equal(await seifuErrorMessage(blobError, 'x'), '許可番号が不正')
  assert.equal(await seifuErrorMessage({ response: { status: 400, data: { recipient_name: ['欄に収まりません'] } } }, 'x'), '欄に収まりません')
  assert.equal(await seifuErrorMessage({ response: { status: 403, data: {} } }, 'x'), 'この操作を行う権限がありません。')
  assert.match(await seifuErrorMessage(new Error('network'), 'x'), /通信できませんでした/)
  assert.equal(formatFileSize(2048), '2 KB')
})

test('画面：任意文字・座標・字体の編集入口が無く、成功した生成記録があるときだけダウンロードを出す', () => {
  const page = readFileSync(resolve(process.cwd(), 'src/pages/SeifuNoticePdfTextPage.vue'), 'utf8')
  const template = page.slice(page.indexOf('<template>'), page.indexOf('<style'))
  const script = page.slice(0, page.indexOf('</script>')).replace(/\/\/.*$/gm, '')  // コメントは除く
  for (const forbidden of ['text_items', 'font_size', 'font_family', 'fontSize', 'drag', 'coordinate', '座標', '字体', 'x:', 'y:', 'color']) {
    assert.ok(!template.includes(forbidden), `画面に ${forbidden} がある`)
    assert.ok(!script.includes(forbidden), `画面の処理に ${forbidden} がある`)
  }
  const inputs = template.match(/<el-(input|date-picker|select)[^>]*v-model="form\.(\w+)"/g) ?? []
  assert.deepEqual(inputs.map((tag) => tag.match(/form\.(\w+)/)![1]).sort(),
    ['issue_date', 'note', 'permit_number', 'recipient_name', 'status', 'title'])
  assert.match(page, /v-if="lastGeneration"/)
  assert.match(page, /lastGeneration\.value = generation/)
  // 失敗時は入力を消さず、loading を必ず戻す
  const generate = page.slice(page.indexOf('const generateCurrent'), page.indexOf('const duplicateRecord'))
  assert.match(generate, /finally \{\s*generating\.value = false/)
  assert.ok(!/Object\.assign\(form/.test(generate))
  assert.ok(!/lastGeneration\.value = null/.test(generate.slice(generate.indexOf('catch'))))
})
