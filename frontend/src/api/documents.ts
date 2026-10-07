import http from '../services/http'
import type { Document, DocumentPayload, DocumentReplacement, ListParams, PaginatedResponse } from '../types/api'
import type { UploadPolicy } from '../utils/uploadQueue'

export const listDocuments = async (params?: ListParams & { case?: number; category?: string; archived?: string }) => {
  const response = await http.get<PaginatedResponse<Document>>('/documents/', { params })
  return response.data
}

const buildDocumentFormData = (payload: DocumentPayload) => {
  const formData = new FormData()
  formData.append('case', String(payload.case))
  formData.append('title', payload.title)
  formData.append('source', payload.source || 'internal')
  formData.append('is_visible_to_client', String(Boolean(payload.is_visible_to_client)))
  if (payload.category) formData.append('category', payload.category)
  if (payload.checklist_item) formData.append('checklist_item', String(payload.checklist_item))
  if (payload.replace_reason) formData.append('replace_reason', payload.replace_reason)
  if (payload.content_label !== undefined) formData.append('content_label', payload.content_label)
  if (payload.file) {
    formData.append('file', payload.file)
  }
  return formData
}

export const createDocument = async (payload: DocumentPayload, onProgress?: (percent: number) => void) => {
  const response = await http.post<Document>('/documents/', buildDocumentFormData(payload), {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress
      ? (event) => { if (event.total) onProgress((event.loaded / event.total) * 100) }
      : undefined,
  })
  return response.data
}

// --- 複数ファイル登録・ZIP（P2） ---
export const getUploadPolicy = async () => (await http.get<UploadPolicy>('/documents/upload-policy/')).data

export interface UploadCheckResult {
  ok: boolean
  errors: string[]
  files: Array<{ index: number; name: string; size: number; problem: string | null }>
  total_bytes: number
}

// 登録前の一括確認（件数・合計・1 件ごとの問題）。一覧全体の問題は 400 で errors を返す。
export const checkUploadBatch = async (caseId: number, files: Array<{ name: string; size: number }>) => {
  try {
    return (await http.post<UploadCheckResult>('/documents/upload-check/', { case: caseId, files })).data
  } catch (error) {
    const response = (error as { response?: { status?: number; data?: UploadCheckResult } })?.response
    if (response?.status === 400 && Array.isArray(response.data?.errors)) return response.data
    throw error
  }
}

export interface ZipRefusal {
  code: string
  detail: string
  skipped: Array<{ id: number; reason: string; label: string }>
}

export interface ZipDownload {
  blob: Blob
  filename: string
  included: number
  skipped: number
}

// ZIP を受け取る。拒否（400 JSON）は blob で返るので読み直して ZipRefusal として投げる。
export const downloadDocumentsZip = async (caseId: number, body: { ids?: number[]; all?: boolean }): Promise<ZipDownload> => {
  try {
    const response = await http.post<Blob>('/documents/download-zip/', { case: caseId, ...body }, { responseType: 'blob' })
    const header = String(response.headers['content-disposition'] || '')
    const encoded = header.match(/filename\*=UTF-8''([^;]+)/)
    return {
      blob: response.data,
      filename: encoded ? decodeURIComponent(encoded[1]) : 'files.zip',
      included: Number(response.headers['x-zip-included'] || 0),
      skipped: Number(response.headers['x-zip-skipped'] || 0),
    }
  } catch (error) {
    const response = (error as { response?: { status?: number; data?: unknown } })?.response
    if (response?.data instanceof Blob) {
      try {
        const parsed = JSON.parse(await response.data.text())
        throw Object.assign(new Error(parsed.detail || 'ZIP を作成できませんでした。'), { refusal: parsed as ZipRefusal, status: response.status })
      } catch (parseError) {
        if ((parseError as { refusal?: unknown }).refusal) throw parseError
      }
    }
    throw error
  }
}

export const updateDocument = async (id: number, payload: DocumentPayload) => {
  const response = await http.patch<Document>(`/documents/${id}/`, buildDocumentFormData(payload), {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const deleteDocument = async (id: number) => {
  await http.delete(`/documents/${id}/`)
}

export const archiveDocument = async (id: number, reason = '') => {
  const response = await http.post<Document>(`/documents/${id}/archive/`, { reason })
  return response.data
}

export const restoreDocument = async (id: number) => {
  const response = await http.post<Document>(`/documents/${id}/restore/`)
  return response.data
}

export const getDocumentHistory = async (id: number) => {
  const response = await http.get<DocumentReplacement[]>(`/documents/${id}/history/`)
  return response.data
}
