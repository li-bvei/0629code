// 返签 visa 表の主流程（2026-10 P1）：申請人 → 担保人テンプレート → 必要項目 → プレビュー → PDF 生成。
// 担保人テンプレートの値を入力欄へ入れ、どの欄がテンプレート由来か・手入力で変えたかを示す。
// 生成可否の最終判断は後端（check / generate-pdf）。ここは画面の案内だけ。
import type { VisaGuarantorTemplate } from '../types/accounting'

export interface VisaFlowForm {
  applicant_name?: string
  birth_date?: string | null
  nationality?: string
  passport_number?: string
  passport_expiry_date?: string | null
  guarantor_name?: string
  guarantor_phone?: string
  guarantor_address?: string
  guarantor_occupation?: string
  guarantor_relationship?: string
  form_data: Record<string, unknown>
}

// 担保人の入力欄 → テンプレートの項目
export const GUARANTOR_FIELD_MAP: { key: string; label: string; templateKey: keyof VisaGuarantorTemplate; inFormData: boolean }[] = [
  { key: 'guarantor_name', label: '担保人氏名', templateKey: 'guarantor_name', inFormData: false },
  { key: 'guarantor_name_en', label: '担保人氏名（英字）', templateKey: 'guarantor_name_en', inFormData: true },
  { key: 'guarantor_phone', label: '電話番号', templateKey: 'guarantor_phone', inFormData: false },
  { key: 'guarantor_address', label: '住所', templateKey: 'guarantor_address', inFormData: false },
  { key: 'guarantor_address_en', label: '住所（英字）', templateKey: 'guarantor_address_en', inFormData: true },
  { key: 'guarantor_birth_date', label: '生年月日', templateKey: 'guarantor_birth_date', inFormData: true },
  { key: 'guarantor_nationality', label: '国籍', templateKey: 'guarantor_nationality', inFormData: true },
  { key: 'guarantor_visa_status', label: '在留資格', templateKey: 'guarantor_visa_status', inFormData: true },
  { key: 'guarantor_occupation', label: '職業', templateKey: 'guarantor_occupation', inFormData: false },
  { key: 'guarantor_relationship', label: '申請人との関係', templateKey: 'guarantor_relationship', inFormData: false },
]

const text = (value: unknown) => (value === null || value === undefined ? '' : String(value)).trim()

const readField = (form: VisaFlowForm, key: string, inFormData: boolean) =>
  text(inFormData ? form.form_data[key] : (form as unknown as Record<string, unknown>)[key])

// テンプレートを選んだとき：担保人の欄をテンプレートの値で埋める（申請人の欄は変えない）
export const applyGuarantorTemplateToForm = <T extends VisaFlowForm>(form: T, template: VisaGuarantorTemplate): T => {
  const next = { ...form, form_data: { ...form.form_data } } as T
  for (const field of GUARANTOR_FIELD_MAP) {
    const value = text(template[field.templateKey])
    if (field.inFormData) next.form_data[field.key] = value
    else (next as unknown as Record<string, unknown>)[field.key] = value
  }
  return next
}

export type FieldSource = 'template' | 'manual' | ''

// 各欄の出所：テンプレートと同じ値なら template、違えば manual、空なら ''
export const guarantorSources = (form: VisaFlowForm, template: VisaGuarantorTemplate | null): Record<string, FieldSource> => {
  const sources: Record<string, FieldSource> = {}
  for (const field of GUARANTOR_FIELD_MAP) {
    const value = readField(form, field.key, field.inFormData)
    if (!value) sources[field.key] = ''
    else if (template && value === text(template[field.templateKey])) sources[field.key] = 'template'
    else sources[field.key] = 'manual'
  }
  return sources
}

// 段階ごとの入力確認（画面で先に知らせる。後端も同じ項目を確認する）
export const stepProblems = (step: number, form: VisaFlowForm, useTemplate: boolean, templateId: number | null): string[] => {
  const problems: string[] = []
  if (step === 0) {
    if (!text(form.applicant_name) && !text(form.form_data.pinyin_name1)) problems.push('申請人氏名')
    // 様式の氏名欄に入るのは英文姓・中文姓（申請人氏名は印字されない）
    if (!text(form.form_data.pinyin_name1) && !text(form.form_data.chinese_name1)) problems.push('英文姓（または中文姓）')
    if (!text(form.birth_date)) problems.push('生年月日')
    if (!text(form.nationality)) problems.push('国籍')
    if (!text(form.passport_number)) problems.push('旅券番号')
    if (!text(form.passport_expiry_date)) problems.push('旅券の有効期限')
  }
  if (step === 1) {
    if (useTemplate && !templateId) problems.push('担保人テンプレート')
    if (!text(form.guarantor_name)) problems.push('担保人氏名')
    if (!text(form.guarantor_address)) problems.push('担保人住所')
    if (!text(form.guarantor_phone)) problems.push('担保人電話番号')
  }
  return problems
}

const ERROR_TITLES: Record<string, string> = {
  missing_fields: '必須項目が足りません',
  template_field_mismatch: 'PDF テンプレートと項目対応表が一致しません',
  template_broken: 'PDF テンプレートを読み込めません',
  template_missing: 'PDF テンプレートがありません',
  font_missing: 'PDF 用のフォントがありません',
  field_write_failed: 'PDF の項目に書き込めませんでした',
  flatten_failed: 'PDF の確定処理に失敗しました',
  output_invalid: '生成した PDF が正しくありません',
  font_subset_failed: 'PDF のサイズ最適化（フォントの軽量化）に失敗しました',
  output_missing: '生成した PDF を保存できませんでした',
  storage_failed: '生成した PDF を保存できませんでした',
  generation_failed: 'PDF の作成中にエラーが発生しました',
  file_missing: 'PDF ファイルが見つかりません',
}

// 生成失敗の表示：題名・詳細・該当項目（入力内容は消さない）
export const visaErrorView = (error: unknown): { title: string; detail: string; fields: string[] } => {
  const response = (error as { response?: { status?: number; data?: Record<string, unknown> } })?.response
  if (response?.status === 403) return { title: '権限がありません', detail: '返签 visa 表を扱う権限がありません。', fields: [] }
  const data = response?.data ?? {}
  const code = String(data.code ?? '')
  const rawFields = Array.isArray(data.fields) ? data.fields : []
  const fields = rawFields.map((item) => (typeof item === 'string' ? item : String((item as { label?: string }).label ?? '')))
    .filter(Boolean)
  return {
    title: ERROR_TITLES[code] ?? 'PDF を作成できませんでした',
    detail: typeof data.detail === 'string' ? data.detail : '通信状況を確認して、もう一度お試しください。',
    fields,
  }
}
