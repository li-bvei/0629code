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
