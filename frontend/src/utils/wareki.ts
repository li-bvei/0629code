// 生年月日などの表示に和暦（日本の元号）を添える（P6）。保存・API・入力欄は西暦の ISO 日付のまま。
// 表示だけを変え、年齢・並び順・検索には使わない。元年は「元年」と表示する。
// 改元日：明治 1868-01-25（太陽暦換算の改元日。1873 年以前は旧暦期間だが日付はそのまま扱う）、
// 大正 1912-07-30、昭和 1926-12-25、平成 1989-01-08、令和 2019-05-01。明治より前は元号を付けない。

interface Era { name: string; start: [number, number, number] }

const ERAS: Era[] = [
  { name: '令和', start: [2019, 5, 1] },
  { name: '平成', start: [1989, 1, 8] },
  { name: '昭和', start: [1926, 12, 25] },
  { name: '大正', start: [1912, 7, 30] },
  { name: '明治', start: [1868, 1, 25] },
]

const parseIso = (value: string | null | undefined): [number, number, number] | null => {
  if (!value) return null
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!match) return null
  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const date = new Date(Date.UTC(y, m - 1, d))
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m - 1 || date.getUTCDate() !== d) return null
  return [y, m, d]
}

const compare = (a: [number, number, number], b: [number, number, number]) =>
  a[0] - b[0] || a[1] - b[1] || a[2] - b[2]

/** 和暦の部分だけ（例：平成2年5月1日、令和元年5月1日）。明治より前・不正な日付は空文字 */
export const toWareki = (value: string | null | undefined) => {
  const parts = parseIso(value)
  if (!parts) return ''
  const era = ERAS.find((candidate) => compare(parts, candidate.start) >= 0)
  if (!era) return ''
  const year = parts[0] - era.start[0] + 1
  return `${era.name}${year === 1 ? '元' : year}年${parts[1]}月${parts[2]}日`
}

/** 西暦の日付（例：1990年5月1日）。不正な日付は元の文字列、空は「-」 */
export const formatSeireki = (value: string | null | undefined) => {
  const parts = parseIso(value)
  if (!parts) return value ? String(value) : '-'
  return `${parts[0]}年${parts[1]}月${parts[2]}日`
}

/** 生年月日の表示：1990年5月1日（平成2年5月1日）。空は「-」、不正な値はそのまま */
export const formatBirthDateWithEra = (value: string | null | undefined) => {
  if (!value) return '-'
  const wareki = toWareki(value)
  const seireki = formatSeireki(value)
  return wareki ? `${seireki}（${wareki}）` : seireki
}
