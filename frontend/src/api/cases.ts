import http from '../services/http'
import type {
  Case,
  AcquisitionPlacePreset,
  AcquisitionPlacePresetPayload,
  CaseApplicationCategory,
  CaseApplicationCategoryPayload,
  CaseChecklistItem,
  CaseChecklistItemOptionsResponse,
  CaseChecklistItemPayload,
  CaseChecklistDemoSeedResult,
  CaseChecklistDeletionHistoryResponse,
  CaseChecklistTemplate,
  CaseChecklistTemplateItem,
  CaseChecklistTemplateItemPayload,
  CaseChecklistTemplateItemMoveResult,
  CaseChecklistTemplatePayload,
  CasePayload,
  CaseStatusSetting,
  CaseStatusSettingPayload,
  CaseTypeMaster,
  CaseTypeMasterPayload,
  CaseStatusPayload,
  CaseStatusChangePayload,
  CaseStatusChangeResponse,
  GenerateRemindersResponse,
  ItemNameSuggestion,
  ListParams,
  PaginatedResponse,
  ResponsiblePartyPreset,
  ResponsiblePartyPresetPayload,
} from '../types/api'

type ChecklistTemplateListParams = ListParams & {
  is_active?: boolean | string
}

type ChecklistTemplateItemListParams = ListParams & {
  template?: number
  is_active?: boolean | string
  category?: string
  search?: string
  ordering?: string
}

export const listCases = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Case>>('/cases/', { params })
  return response.data
}

export const getCase = async (id: number) => {
  const response = await http.get<Case>(`/cases/${id}/`)
  return response.data
}

export const createCase = async (payload: CasePayload) => {
  const response = await http.post<Case>('/cases/', payload)
  return response.data
}

export const updateCase = async (id: number, payload: Partial<CasePayload>) => {
  const response = await http.patch<Case>(`/cases/${id}/`, payload)
  return response.data
}

export const deleteCase = async (id: number) => {
  await http.delete(`/cases/${id}/`)
}

export const previewRegenerateCaseNumber = async (id: number) => {
  const response = await http.get<{ current_case_number: string; new_case_number: string }>(
    `/cases/${id}/preview-regenerate-case-number/`,
  )
  return response.data
}

export const regenerateCaseNumber = async (id: number) => {
  const response = await http.post<Case>(`/cases/${id}/regenerate-case-number/`, {})
  return response.data
}

export const listCaseTypeMasters = async (params?: ListParams & { is_active?: boolean | string }) => {
  const response = await http.get<PaginatedResponse<CaseTypeMaster>>('/case-type-masters/', { params })
  return response.data
}

export const createCaseTypeMaster = async (payload: CaseTypeMasterPayload) => {
  const response = await http.post<CaseTypeMaster>('/case-type-masters/', payload)
  return response.data
}

export const updateCaseTypeMaster = async (id: number, payload: Partial<CaseTypeMasterPayload>) => {
  const response = await http.patch<CaseTypeMaster>(`/case-type-masters/${id}/`, payload)
  return response.data
}

export const listCaseApplicationCategories = async (params?: ListParams & { is_active?: boolean | string }) => {
  const response = await http.get<PaginatedResponse<CaseApplicationCategory>>('/case-application-categories/', { params })
  return response.data
}

export const createCaseApplicationCategory = async (payload: CaseApplicationCategoryPayload) => {
  const response = await http.post<CaseApplicationCategory>('/case-application-categories/', payload)
  return response.data
}

export const updateCaseApplicationCategory = async (id: number, payload: Partial<CaseApplicationCategoryPayload>) => {
  const response = await http.patch<CaseApplicationCategory>(`/case-application-categories/${id}/`, payload)
  return response.data
}

export const listCaseStatusSettings = async (params?: ListParams & { is_visible?: boolean | string }) => {
  const response = await http.get<PaginatedResponse<CaseStatusSetting>>('/case-status-settings/', { params })
  return response.data
}

export const updateCaseStatusSetting = async (id: number, payload: CaseStatusSettingPayload) => {
  const response = await http.patch<CaseStatusSetting>(`/case-status-settings/${id}/`, payload)
  return response.data
}

export const listAcquisitionPlacePresets = async (params?: ListParams & { is_active?: boolean | string }) => {
  const response = await http.get<PaginatedResponse<AcquisitionPlacePreset>>('/case-acquisition-place-presets/', { params })
  return response.data
}

export const createAcquisitionPlacePreset = async (payload: AcquisitionPlacePresetPayload) => {
  const response = await http.post<AcquisitionPlacePreset>('/case-acquisition-place-presets/', payload)
  return response.data
}

export const updateAcquisitionPlacePreset = async (id: number, payload: Partial<AcquisitionPlacePresetPayload>) => {
  const response = await http.patch<AcquisitionPlacePreset>(`/case-acquisition-place-presets/${id}/`, payload)
  return response.data
}

export const listResponsiblePartyPresets = async (params?: ListParams & { is_active?: boolean | string }) => {
  const response = await http.get<PaginatedResponse<ResponsiblePartyPreset>>('/case-responsible-party-presets/', { params })
  return response.data
}

export const createResponsiblePartyPreset = async (payload: ResponsiblePartyPresetPayload) => {
  const response = await http.post<ResponsiblePartyPreset>('/case-responsible-party-presets/', payload)
  return response.data
}

export const updateResponsiblePartyPreset = async (id: number, payload: Partial<ResponsiblePartyPresetPayload>) => {
  const response = await http.patch<ResponsiblePartyPreset>(`/case-responsible-party-presets/${id}/`, payload)
  return response.data
}

export const cancelCase = async (id: number, reason: string) => {
  const response = await http.post<Case>(`/cases/${id}/cancel/`, { reason })
  return response.data
}

export const changeCaseStatus = async (id: number, payload: CaseStatusChangePayload) => {
  const response = await http.post<CaseStatusChangeResponse>(`/cases/${id}/change-status/`, payload)
  return response.data
}

export const changeCaseRegistrationStatus = async (id: number, payload: CaseStatusChangePayload) => {
  const response = await http.post<CaseStatusChangeResponse>(`/cases/${id}/change-registration-status/`, payload)
  return response.data
}

export const updateCaseProgressInfo = async (
  id: number,
  payload: CaseStatusPayload & { note?: string },
) => {
  const response = await http.post<Case>(`/cases/${id}/progress-info/`, payload)
  return response.data
}

export const generateCaseReminders = async (id: number) => {
  const response = await http.post<GenerateRemindersResponse>(`/cases/${id}/generate-reminders/`, {})
  return response.data
}

export const listCaseChecklistTemplates = async (params?: ChecklistTemplateListParams) => {
  const response = await http.get<PaginatedResponse<CaseChecklistTemplate>>('/case-checklist-templates/', { params })
  return response.data
}

export const createCaseChecklistTemplate = async (payload: CaseChecklistTemplatePayload) => {
  const response = await http.post<CaseChecklistTemplate>('/case-checklist-templates/', payload)
  return response.data
}

export const updateCaseChecklistTemplate = async (id: number, payload: Partial<CaseChecklistTemplatePayload>) => {
  const response = await http.patch<CaseChecklistTemplate>(`/case-checklist-templates/${id}/`, payload)
  return response.data
}

export const deleteCaseChecklistTemplate = async (id: number) => {
  await http.delete(`/case-checklist-templates/${id}/`)
}

export const softDeleteCaseChecklistTemplate = async (id: number) => {
  await http.post(`/case-checklist-templates/${id}/delete/`, {})
}

export const restoreCaseChecklistTemplate = async (id: number) => {
  const response = await http.post<CaseChecklistTemplate>(`/case-checklist-templates/${id}/restore/`, {})
  return response.data
}

export const listCaseChecklistTemplateItems = async (params?: ChecklistTemplateItemListParams) => {
  const response = await http.get<PaginatedResponse<CaseChecklistTemplateItem>>('/case-checklist-template-items/', { params })
  return response.data
}

export const listCaseChecklistItemOptions = async (params?: { category?: string }) => {
  const response = await http.get<CaseChecklistItemOptionsResponse>('/case-checklist-template-items/options/', { params })
  return response.data
}

export const listCaseChecklistItemNameSuggestions = async (params?: { q?: string }) => {
  const response = await http.get<ItemNameSuggestion[]>('/case-checklist-template-items/name-suggestions/', { params })
  return response.data
}

export const createCaseChecklistTemplateItem = async (payload: CaseChecklistTemplateItemPayload) => {
  const response = await http.post<CaseChecklistTemplateItem>('/case-checklist-template-items/', payload)
  return response.data
}

export const updateCaseChecklistTemplateItem = async (id: number, payload: Partial<CaseChecklistTemplateItemPayload>) => {
  const response = await http.patch<CaseChecklistTemplateItem>(`/case-checklist-template-items/${id}/`, payload)
  return response.data
}

export const deleteCaseChecklistTemplateItem = async (id: number) => {
  await http.delete(`/case-checklist-template-items/${id}/`)
}

export const softDeleteCaseChecklistTemplateItem = async (id: number) => {
  await http.post(`/case-checklist-template-items/${id}/delete/`, {})
}

export const restoreCaseChecklistTemplateItem = async (id: number) => {
  const response = await http.post<CaseChecklistTemplateItem>(`/case-checklist-template-items/${id}/restore/`, {})
  return response.data
}

export const moveCaseChecklistTemplateItemUp = async (id: number) => {
  const response = await http.post<CaseChecklistTemplateItemMoveResult>(`/case-checklist-template-items/${id}/move-up/`, {})
  return response.data
}

export const moveCaseChecklistTemplateItemDown = async (id: number) => {
  const response = await http.post<CaseChecklistTemplateItemMoveResult>(`/case-checklist-template-items/${id}/move-down/`, {})
  return response.data
}

export const listCaseChecklistItems = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<CaseChecklistItem>>('/case-checklist-items/', { params })
  return response.data
}

export const createCaseChecklistItem = async (payload: CaseChecklistItemPayload) => {
  const response = await http.post<CaseChecklistItem>('/case-checklist-items/', payload)
  return response.data
}

export const updateCaseChecklistItem = async (id: number, payload: Partial<CaseChecklistItemPayload>) => {
  const response = await http.patch<CaseChecklistItem>(`/case-checklist-items/${id}/`, payload)
  return response.data
}

export const deleteCaseChecklistItem = async (id: number) => {
  await http.delete(`/case-checklist-items/${id}/`)
}

export const applyCaseChecklistTemplate = async (caseId: number, templateId: number) => {
  const response = await http.post<CaseChecklistItem[]>(`/cases/${caseId}/apply-checklist-template/`, {
    template_id: templateId,
  })
  return response.data
}

export const seedCaseChecklistDemo = async () => {
  const response = await http.post<CaseChecklistDemoSeedResult>('/case-checklist-demo/seed/', {})
  return response.data
}

export const seedStandardCaseChecklistTemplates = async () => {
  const response = await http.post<CaseChecklistDemoSeedResult>('/case-checklist-templates/seed-standard/', {})
  return response.data
}

export const listCaseChecklistDeletionHistory = async (params?: ListParams) => {
  const response = await http.get<CaseChecklistDeletionHistoryResponse>('/case-checklist-deletion-history/', { params })
  return response.data
}
