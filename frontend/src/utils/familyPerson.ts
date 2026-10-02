// 家族の編集：関連付いている人物（Customer）の情報のうち、利用者が実際に変更した項目だけを取り出す。
// 変更していない項目は送らない（伏せ字で表示されている証件番号などを、その表示値で上書きしないため）。
export const FAMILY_PERSON_FIELDS = [
  'name', 'name_kana', 'birth_date', 'gender', 'nationality', 'phone', 'email', 'postal_code', 'address',
  'residence_status', 'residence_card_no', 'residence_expiry', 'passport_no', 'passport_expiry',
] as const
const DATE_FIELDS = new Set<string>(['birth_date', 'residence_expiry', 'passport_expiry'])

type PersonValues = Partial<Record<(typeof FAMILY_PERSON_FIELDS)[number] | 'my_number', string | null | undefined>>

const normalize = (value: string | null | undefined) => (value ?? '').trim()

export const buildPersonChanges = (original: PersonValues, form: PersonValues): Record<string, string | null> => {
  const changes: Record<string, string | null> = {}
  for (const field of FAMILY_PERSON_FIELDS) {
    const next = normalize(form[field])
    if (next === normalize(original[field])) continue
    changes[field] = DATE_FIELDS.has(field) && !next ? null : next
  }
  // マイナンバーは入力されたときだけ送る（空欄は「変更なし」）
  const myNumber = normalize(form.my_number)
  if (myNumber) changes.my_number = myNumber
  return changes
}
