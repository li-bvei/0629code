// 動的 import の失敗（ChunkLoadError 相当）かどうか。ブラウザごとに文言が違う。
const CHUNK_ERROR_PATTERNS = [
  /Failed to fetch dynamically imported module/i,
  /Importing a module script failed/i,
  /error loading dynamically imported module/i,
  /Loading chunk [\w-]+ failed/i,
  /Unable to preload CSS/i,
]

export const isChunkLoadError = (error: unknown) => {
  const message = error instanceof Error ? error.message : String(error ?? '')
  return CHUNK_ERROR_PATTERNS.some((pattern) => pattern.test(message))
}
