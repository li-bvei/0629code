// 支出カテゴリの入力支援（表示の判断だけ。提案の計算と保存は後端）。
import type { ExpenseCategorySuggestions, PlaceCategoryRecommendation } from '../types/accounting'

const same = (a: string | undefined | null, b: string | undefined | null) => (a ?? '').trim() === (b ?? '').trim()

// 文字規則からの提案のうち、まだ採用していないもの（採用済みのカテゴリは出さない）
export const pendingPlaceRecommendations = (
  suggestions: ExpenseCategorySuggestions | null, category: string | undefined,
): PlaceCategoryRecommendation[] =>
  (suggestions?.place_recommendations ?? []).filter((row) => !same(row.name, category))

// 「この場所とカテゴリの対応を記憶する」を出す条件：場所とカテゴリが入力済みで、
// その組み合わせを提案する規則がまだ無い（既にある対応を重ねて登録させない）。
export const canOfferRemember = (
  suggestions: ExpenseCategorySuggestions | null, place: string | undefined, category: string | undefined,
): boolean => {
  if (!(place ?? '').trim() || !(category ?? '').trim()) return false
  return !(suggestions?.place_recommendations ?? []).some((row) => row.match_field === 'place' && same(row.name, category))
}
