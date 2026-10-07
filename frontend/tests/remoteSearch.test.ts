import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createRemoteSearch, remoteErrorMessage } from '../src/components/remoteSearch'

interface Row { id: number; name: string }

const deferred = <T>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

const setup = (overrides: Partial<Parameters<typeof createRemoteSearch<Row>>[0]> = {}) => {
  let modelValue: number | null = null
  const search = createRemoteSearch<Row>({
    fetcher: async () => [],
    toOption: (row) => ({ value: row.id, label: row.name }),
    getModelValue: () => modelValue,
    ...overrides,
  })
  return { search, setModel: (value: number | null) => { modelValue = value } }
}

test('連続検索では最後のリクエストの結果だけを反映する（古い応答で上書きしない）', async () => {
  const first = deferred<Row[]>()
  const second = deferred<Row[]>()
  const pending = [first, second]
  const { search } = setup({ fetcher: () => pending.shift()!.promise })
  const p1 = search.runSearch('た')
  const p2 = search.runSearch('田中')
  second.resolve([{ id: 2, name: '田中二郎' }])
  await p2
  first.resolve([{ id: 1, name: '高橋一郎' }])
  await p1
  assert.deepEqual(search.options.value.map((o) => o.value), [2])
  assert.equal(search.loading.value, false)
})

test('古いリクエストの失敗は新しい成功結果を消さない', async () => {
  const first = deferred<Row[]>()
  const second = deferred<Row[]>()
  const pending = [first, second]
  const { search } = setup({ fetcher: () => pending.shift()!.promise })
  const p1 = search.runSearch('a')
  const p2 = search.runSearch('ab')
  second.resolve([{ id: 3, name: 'AB' }])
  await p2
  first.reject({ response: { status: 500 } })
  await p1
  assert.equal(search.error.value, '')
  assert.deepEqual(search.options.value.map((o) => o.value), [3])
})

test('検索エラーは表示用メッセージにし、選択中の値のラベルは残す', async () => {
  let fail = false
  const { search, setModel } = setup({
    fetcher: async () => {
      if (fail) throw { response: { status: 403 } }
      return [{ id: 7, name: '山田' }]
    },
  })
  await search.runSearch('')
  setModel(7)
  fail = true
  await search.runSearch('zzz')
  assert.equal(search.error.value, '検索する権限がありません。')
  assert.deepEqual(search.options.value, [{ value: 7, label: '山田' }])
  assert.equal(search.loading.value, false)
  fail = false
  await search.runSearch('')
  assert.equal(search.error.value, '')
})

test('初期値：候補に無い選択値は fetchOne で補い、initialOption があれば取得しない', async () => {
  let fetchOneCalls = 0
  const { search, setModel } = setup({
    fetchOne: async (id) => { fetchOneCalls += 1; return { id, name: `顧客${id}` } },
  })
  setModel(21)
  await search.ensureInitial()
  assert.deepEqual(search.options.value, [{ value: 21, label: '顧客21' }])
  await search.ensureInitial()
  assert.equal(fetchOneCalls, 1)

  const withInitial = setup({
    fetchOne: async () => { throw new Error('呼ばれてはならない') },
    getInitialOption: () => ({ value: 5, label: '既知の顧客' }),
  })
  withInitial.setModel(5)
  await withInitial.search.ensureInitial()
  assert.deepEqual(withInitial.search.options.value, [{ value: 5, label: '既知の顧客' }])
})

test('初期値の取得が権限外（404/403）でも例外にせずエラーメッセージを出す', async () => {
  const { search, setModel } = setup({ fetchOne: async () => { throw { response: { status: 403 } } } })
  setModel(99)
  await search.ensureInitial()
  assert.deepEqual(search.options.value, [])
  assert.equal(search.error.value, '検索する権限がありません。')
})

test('エラーメッセージの対応', () => {
  assert.equal(remoteErrorMessage({ response: { status: 401 } }), 'ログインし直してください。')
  assert.equal(remoteErrorMessage(new Error('network')), '候補を取得できませんでした。再度お試しください。')
})

// --- 会社の従業員・代表者の選択（既存顧客）：1 ページを超える候補・件数の案内・回顕 -----------------
const people = Array.from({ length: 25 }, (_, i) => ({ id: i + 1, name: `候補者${String(i + 1).padStart(2, '0')}` }))
// 一覧 API と同じく、後端で検索して 20 件まで返し、全件数 count を付ける
const pagedFetcher = async (search: string) => {
  const matched = people.filter((row) => row.name.includes(search))
  return { results: matched.slice(0, 20), count: matched.length }
}

test('候補が 1 ページを超えても、検索で後ろの人を探せる。出ていない件数を案内する', async () => {
  const { search } = setup({ fetcher: pagedFetcher })
  await search.runSearch('')
  assert.equal(search.options.value.length, 20)
  assert.equal(search.total.value, 25)
  assert.equal(search.hiddenCount(), 5)  // 「ほかに 5 件あります。絞り込んでください」
  await search.runSearch('候補者25')
  assert.deepEqual(search.options.value.map((o) => o.label), ['候補者25'])
  assert.equal(search.hiddenCount(), 0)
})

test('該当なし：候補は空、案内も出ない', async () => {
  const { search } = setup({ fetcher: pagedFetcher })
  await search.runSearch('該当しない')
  assert.deepEqual(search.options.value, [])
  assert.equal(search.hiddenCount(), 0)
  assert.equal(search.error.value, '')
})

test('選択中の値は、検索結果のページに無くても表示し続ける（編集時の既存関連）', async () => {
  const { search, setModel } = setup({ fetcher: pagedFetcher, getInitialOption: () => ({ value: 25, label: '候補者25' }) })
  setModel(25)
  await search.ensureInitial()
  await search.runSearch('')  // 1 ページ目（1〜20）に 25 は無い
  assert.equal(search.options.value[0].label, '候補者25')
  assert.ok(search.options.value.some((o) => o.value === 1))
  assert.equal(search.hiddenCount(), 5)  // 補った選択値は「出ている件数」に数えない
})

test('配列を返す従来の fetcher も動く（件数が分からないので案内しない）', async () => {
  const { search } = setup({ fetcher: async () => [{ id: 1, name: 'A' }] })
  await search.runSearch('')
  assert.equal(search.total.value, null)
  assert.equal(search.hiddenCount(), 0)
})
