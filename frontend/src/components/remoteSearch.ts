// RemoteSelect の検索状態（候補・読み込み中・エラー・初期値）を管理する。Vue コンポーネントから
// 切り離し、単体テストできるようにしている（tests/remoteSearch.test.ts）。
import { ref } from 'vue'

export interface RemoteOption {
  value: number
  label: string
  sublabel?: string
}

export interface RemoteSearchConfig<T extends { id: number }> {
  fetcher: (search: string) => Promise<T[]>
  fetchOne?: (id: number) => Promise<T | null>
  toOption: (row: T) => RemoteOption
  getModelValue: () => number | null | undefined
  getInitialOption?: () => RemoteOption | null | undefined
}

export const remoteErrorMessage = (error: unknown) => {
  const status = (error as { response?: { status?: number } })?.response?.status
  if (status === 403) return '検索する権限がありません。'
  if (status === 401) return 'ログインし直してください。'
  return '候補を取得できませんでした。再度お試しください。'
}

export const createRemoteSearch = <T extends { id: number }>(config: RemoteSearchConfig<T>) => {
  const options = ref<RemoteOption[]>([])
  const loading = ref(false)
  const error = ref('')
  const rowCache = new Map<number, T>()
  // 連続入力で古い応答が新しい結果を上書きしないよう、最後に出したリクエストだけを反映する。
  let latestRequest = 0

  const keepSelected = (mapped: RemoteOption[]) => {
    const selectedId = config.getModelValue()
    const selected = options.value.find((option) => option.value === selectedId)
    if (selected && !mapped.some((option) => option.value === selected.value)) {
      return [selected, ...mapped]
    }
    return mapped
  }

  const runSearch = async (search: string) => {
    const requestId = ++latestRequest
    loading.value = true
    error.value = ''
    try {
      const rows = await config.fetcher(search.trim())
      if (requestId !== latestRequest) return
      rows.forEach((row) => rowCache.set(row.id, row))
      options.value = keepSelected(rows.map((row) => config.toOption(row)))
    } catch (err) {
      if (requestId !== latestRequest) return
      error.value = remoteErrorMessage(err)
      // 失敗しても選択中の値のラベルは残す。
      options.value = keepSelected([])
    } finally {
      if (requestId === latestRequest) loading.value = false
    }
  }

  const ensureInitial = async () => {
    const id = config.getModelValue()
    if (!id) return
    if (options.value.some((option) => option.value === id)) return
    const initial = config.getInitialOption?.()
    if (initial && initial.value === id) {
      options.value = [initial, ...options.value]
      return
    }
    if (!config.fetchOne) return
    try {
      const row = await config.fetchOne(id)
      if (row && !options.value.some((option) => option.value === row.id)) {
        rowCache.set(row.id, row)
        options.value = [config.toOption(row), ...options.value]
      }
    } catch (err) {
      // 権限外などで取得できない場合は id だけの表示になる。理由は error に出す。
      error.value = remoteErrorMessage(err)
    }
  }

  return { options, loading, error, rowCache, runSearch, ensureInitial }
}
