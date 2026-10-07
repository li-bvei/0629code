import http from '../services/http'
import type { BatchChanges, BatchResponse } from '../utils/checklistBatch'
import type {
  Case,
  Document,
  TodayWorkbench,
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
  WorkflowStage,
  WorkflowTemplate,
  CaseStatusPayload,
  CaseStatusChangePayload,
  CaseStatusChangeResponse,
  ChecklistItemPreset,
  ChecklistItemPresetPayload,
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

// --- 業務フロー（P4）。変更は案件設定の権限者のみ（後端で判定・監査） ---

export const listWorkflowTemplates = async (params?: ListParams & { is_active?: boolean | string }) => {
  const response = await http.get<PaginatedResponse<WorkflowTemplate>>('/workflow-templates/', { params })
  return response.data
}

export const saveWorkflowTemplate = async (id: number | null, payload: Partial<Pick<WorkflowTemplate, 'code' | 'name' | 'family' | 'description' | 'is_active' | 'sort_order'>>) => {
  const response = id
    ? await http.patch<WorkflowTemplate>(`/workflow-templates/${id}/`, payload)
    : await http.post<WorkflowTemplate>('/workflow-templates/', payload)
  return response.data
}

export const duplicateWorkflowTemplate = async (id: number, payload: { code: string; name: string }) => {
  const response = await http.post<WorkflowTemplate>(`/workflow-templates/${id}/duplicate/`, payload)
  return response.data
}

export const saveWorkflowStage = async (id: number | null, payload: Partial<Pick<WorkflowStage, 'template' | 'code' | 'name' | 'base_status' | 'sort_order' | 'is_active'>>) => {
  const response = id
    ? await http.patch<WorkflowStage>(`/workflow-stages/${id}/`, payload)
    : await http.post<WorkflowStage>('/workflow-stages/', payload)
  return response.data
}

export const deleteWorkflowStage = async (id: number) => {
  await http.delete(`/workflow-stages/${id}/`)
}

export const changeCaseStage = async (id: number, payload: { stage: number; expected_stage?: number | null; note?: string }) => {
  const response = await http.post<Case>(`/cases/${id}/change-stage/`, payload)
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

export const listChecklistItemPresets = async (params?: ListParams & { is_active?: boolean | string, search?: string }) => {
  const response = await http.get<PaginatedResponse<ChecklistItemPreset>>('/checklist-item-presets/', { params })
  return response.data
}

export const createChecklistItemPreset = async (payload: ChecklistItemPresetPayload) => {
  const response = await http.post<ChecklistItemPreset>('/checklist-item-presets/', payload)
  return response.data
}

export const updateChecklistItemPreset = async (id: number, payload: Partial<ChecklistItemPresetPayload>) => {
  const response = await http.patch<ChecklistItemPreset>(`/checklist-item-presets/${id}/`, payload)
  return response.data
}

export const seedStandardChecklistItemPresets = async () => {
  const response = await http.post<{ success: boolean, message: string, created: number, skipped: number }>(
    '/checklist-item-presets/seed-standard/',
    {},
  )
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

// アーカイブ（理由必須。進捗が終わっていない案件は force で確認済みとして送る）と復元
export const archiveCase = async (id: number, payload: { reason: string; force?: boolean }) => {
  const response = await http.post<CaseStatusChangeResponse>(`/cases/${id}/archive/`, payload)
  return response.data
}

export const restoreCase = async (id: number, reason = '') => {
  const response = await http.post<CaseStatusChangeResponse>(`/cases/${id}/restore/`, { reason })
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

export const applyCaseChecklistTemplate = async (
  caseId: number,
  templateId: number,
  mode: 'merge' | 'replace' = 'merge',
) => {
  const response = await http.post<{ created: CaseChecklistItem[], created_count: number, mode: string }>(
    `/cases/${caseId}/apply-checklist-template/`,
    { template_id: templateId, mode },
  )
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


// --- Next Action / 待機 / 入金の記録 / 資料受領（P1）。権限は後端で判定される。 ---
export interface NextActionPayload {
  next_action: string
  next_action_due_at?: string | null
  assignee?: number | null
  blocked_reason?: string
}

export const setCaseNextAction = async (id: number, payload: NextActionPayload) => {
  const response = await http.post<Case>(`/cases/${id}/next-action/`, payload)
  return response.data
}

export const completeCaseNextAction = async (id: number, note = '') => {
  const response = await http.post<Case>(`/cases/${id}/next-action/complete/`, { note })
  return response.data
}

export const startCaseWaiting = async (
  id: number,
  payload: { waiting_reason: string; waiting_note?: string; waiting_until?: string | null },
) => {
  const response = await http.post<Case>(`/cases/${id}/waiting/start/`, payload)
  return response.data
}

export const endCaseWaiting = async (id: number, note = '') => {
  const response = await http.post<Case>(`/cases/${id}/waiting/end/`, { note })
  return response.data
}

export const recordCasePaymentNote = async (
  id: number,
  payload: { amount?: string | number | null; received_on?: string | null; reference?: string; note?: string },
) => {
  const response = await http.post<{ timeline_id: number }>(`/cases/${id}/payment-note/`, payload)
  return response.data
}

export const receiveCaseChecklistItem = async (
  id: number,
  payload: { document?: number | null; received_on?: string | null; note?: string; complete?: boolean },
) => {
  const response = await http.post<CaseChecklistItem & { progress_summary?: unknown }>(
    `/case-checklist-items/${id}/receive/`,
    payload,
  )
  return response.data
}

// 案件内の必要資料の一括更新（P2）。対象はこの案件の項目だけ。項目ごとの成功／失敗が返る。
export const batchUpdateCaseChecklist = async (
  caseId: number,
  payload: { item_ids: number[]; changes: BatchChanges; versions?: Record<string, string> },
) => {
  const response = await http.post<BatchResponse & { progress_summary?: Record<string, number | boolean> }>(
    `/cases/${caseId}/checklist-batch/`, payload,
  )
  return response.data
}

export const listCaseDocuments = async (caseId: number) => {
  const response = await http.get<PaginatedResponse<Document>>('/documents/', { params: { case: caseId, page_size: 100 } })
  return response.data
}

export const getTodayWorkbench = async (scope: 'mine' | 'all' = 'mine') => {
  const response = await http.get<TodayWorkbench>('/workbench/today/', { params: { scope } })
  return response.data
}
