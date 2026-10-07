import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  DEFAULT_UPLOAD_POLICY, addFiles, contentLabelProblem, fileProblem, fillMissingLabels, rowsMissingLabel, isRetryable, markFailedForRetry, removeFinished, runQueue,
  summarizeQueue, uploadErrorText, type QueueItem,
} from '../src/utils/uploadQueue'

type FakeFile = { name: string; size: number }
const MB = 1024 * 1024
const policy = { ...DEFAULT_UPLOAD_POLICY, max_file_bytes: 10 * MB, batch_max_files: 3, batch_max_total_bytes: 15 * MB }

const runWith = async (queue: QueueItem<FakeFile>[], fail: (name: string) => unknown) => {
  let rows = queue
  const update = (key: string, patch: Partial<QueueItem<FakeFile>>) => {
    rows = rows.map((row) => (row.key === key ? { ...row, ...patch } : row))
  }
  await runQueue(rows, async (item, onProgress) => {
    onProgress(50)
    const problem = fail(item.name)
    if (problem) throw problem
    return { id: item.name.length }
  }, update)
  return rows
}

test('複数ファイル：全件成功で全行が成功・進捗 100・登録 ID を持つ', async () => {
  const { queue } = addFiles([], [{ name: 'a.pdf', size: 100 }, { name: 'b.png', size: 200 }], policy, 'other')
  const rows = await runWith(queue, () => null)
  assert.deepEqual(rows.map((row) => [row.status, row.progress]), [['success', 100], ['success', 100]])
  assert.ok(rows.every((row) => row.documentId))
})

test('一部失敗：失敗は理由付きで残り、他の成功は消えず、失敗分だけ再試行できる', async () => {
  const { queue } = addFiles([], [{ name: 'a.pdf', size: 100 }, { name: 'b.pdf', size: 100 }, { name: 'c.pdf', size: 100 }], policy, 'other')
  const serverError = { response: { status: 400, data: { file: ['ファイルの中身が拡張子（.pdf）と一致しません。'] } } }
  let rows = await runWith(queue, (name) => (name === 'b.pdf' ? serverError : null))
  assert.deepEqual(rows.map((row) => row.status), ['success', 'failed', 'success'])
  assert.equal(rows[1].error, 'ファイルの中身が拡張子（.pdf）と一致しません。')
  assert.ok(!rows.some((row) => row.status === 'uploading'))  // 登録中のまま残らない
  rows = markFailedForRetry(rows, policy)
  assert.deepEqual(rows.map((row) => row.status), ['success', 'waiting', 'success'])
  let uploaded: string[] = []
  await runQueue(rows, async (item) => { uploaded = [...uploaded, item.name]; return { id: 9 } }, () => undefined)
  assert.deepEqual(uploaded, ['b.pdf'])  // 成功済みは再送しない
})

test('通信エラー・権限エラーも行の失敗理由になる（例外を外へ出さない）', async () => {
  assert.match(uploadErrorText(new Error('Network Error')), /通信できませんでした/)
  assert.match(uploadErrorText({ response: { status: 403 } }), /権限/)
  assert.match(uploadErrorText({ response: { status: 413 } }), /大きすぎます/)
  const { queue } = addFiles([], [{ name: 'a.pdf', size: 1 }], policy, 'other')
  const rows = await runWith(queue, () => new Error('Network Error'))
  assert.equal(rows[0].status, 'failed')
})

test('上限：件数・1 件の大きさ・合計サイズ', () => {
  const four = [1, 2, 3, 4].map((i) => ({ name: `${i}.pdf`, size: 10 }))
  const tooMany = addFiles([], four, policy, 'other')
  assert.equal(tooMany.queue.length, 3)
  assert.match(tooMany.errors[0], /3 件まで/)
  const big = addFiles([], [{ name: 'big.pdf', size: 11 * MB }], policy, 'other')
  assert.equal(big.queue[0].status, 'failed')
  assert.match(big.queue[0].error, /大きすぎます/)
  assert.equal(isRetryable(big.queue[0], policy), false)  // ファイル自体の問題は再試行できない
  const total = addFiles([], [{ name: 'a.pdf', size: 9 * MB }, { name: 'b.pdf', size: 9 * MB }], policy, 'other')
  assert.equal(total.queue.length, 1)
  assert.match(total.errors[0], /合計サイズ/)
})

test('危険・不正なファイル名と種類を事前に知らせる', () => {
  for (const name of ['CON.pdf', 'a/b.pdf', 'tab\tname.pdf', '.pdf', 'tool.exe', 'noext', 'x'.repeat(201) + '.pdf']) {
    assert.ok(fileProblem(name, 10, policy), name)
  }
  assert.equal(fileProblem('在留カード（表）.pdf', 10, policy), '')
  assert.match(fileProblem('empty.pdf', 0, policy), /空のファイル/)
})

test('成功分を消す・集計', () => {
  const { queue } = addFiles([], [{ name: 'a.pdf', size: 5 }, { name: 'b.exe', size: 5 }], policy, 'identity')
  const rows = queue.map((row, index) => (index === 0 ? { ...row, status: 'success' as const } : row))
  assert.deepEqual(summarizeQueue(rows), { total: 2, waiting: 0, uploading: 0, success: 1, failed: 1, totalBytes: 10 })
  assert.deepEqual(removeFinished(rows).map((row) => row.name), ['b.exe'])
  assert.equal(queue[0].category, 'identity')
})

test('P6：資料内容は必須で、危険な文字・パス・予約名を事前に案内する', () => {
  assert.equal(contentLabelProblem('住民票'), '')
  assert.equal(contentLabelProblem('  在留 カード  '), '')
  for (const label of ['', '   ', '../住民票', 'a/b', 'a\\b', '住民票.', '.hidden', 'CON', 'a'.repeat(61), '住民\u0007票', '住民\u202e票', 'a:b', 'a|b']) {
    assert.notEqual(contentLabelProblem(label), '', label)
  }
})

test('P6：資料内容が未入力の行があっても行列は消さず、まとめて入力は空の行だけに入れる', () => {
  const { queue } = addFiles([], [{ name: 'a.pdf', size: 10 }, { name: 'b.pdf', size: 10 }, { name: 'c.exe', size: 10 }], DEFAULT_UPLOAD_POLICY, 'other')
  assert.equal(queue.every((item) => item.contentLabel === ''), true)
  assert.deepEqual(rowsMissingLabel(queue).map((item) => item.name), ['a.pdf', 'b.pdf'])  // 失敗済み（c.exe）は対象外
  const typed = queue.map((item) => (item.name === 'a.pdf' ? { ...item, contentLabel: 'パスポート' } : item))
  const filled = fillMissingLabels(typed, '住民票')
  assert.deepEqual(filled.map((item) => item.contentLabel), ['パスポート', '住民票', '住民票'])
  assert.equal(rowsMissingLabel(filled).length, 0)
  assert.equal(filled.length, 3)
})

test('P6：ZIP は他のファイルより小さい上限で事前に止める', () => {
  const policy = { ...DEFAULT_UPLOAD_POLICY, max_file_bytes: 20 * 1024 * 1024, zip_upload_max_bytes: 1000 }
  assert.match(fileProblem('a.zip', 2000, policy), /ZIP/)
  assert.equal(fileProblem('a.pdf', 2000, policy), '')
  assert.equal(fileProblem('a.zip', 900, policy), '')
  assert.equal(uploadErrorText({ response: { status: 400, data: { content_label: ['資料内容を入力してください。'] } } }), '資料内容を入力してください。')
})

test('P6：一覧・案件のファイル名はダウンロード名（旧ファイルは元の名前）を表示する', async () => {
  const { readFileSync } = await import('node:fs')
  const { resolve } = await import('node:path')
  for (const file of ['src/pages/DocumentsPage.vue', 'src/components/case/CaseActionBar.vue']) {
    assert.match(readFileSync(resolve(process.cwd(), file), 'utf8'), /row\.download_name \|\| row\.file_name/, file)
  }
  const component = readFileSync(resolve(process.cwd(), 'src/components/documents/DocumentUploadQueue.vue'), 'utf8')
  assert.match(component, /content_label: item\.contentLabel\.trim\(\)/)
  assert.match(component, /rowsMissingLabel\(queue\.value/)
})
