import http from '../services/http'

export interface OfficeSettings {
  fiscal_year_end_month: number
  source: 'database' | 'fallback'
  updated_at: string | null
  updated_by: string
}

export const getOfficeSettings = async () => (await http.get<OfficeSettings>('/office-settings/')).data
export const updateFiscalYearEndMonth = async (month: number) =>
  (await http.patch<OfficeSettings>('/office-settings/', { fiscal_year_end_month: month })).data
