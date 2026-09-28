import http from '../services/http'
import type { Document, DocumentPayload, DocumentReplacement, ListParams, PaginatedResponse } from '../types/api'

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
  if (payload.file) {
    formData.append('file', payload.file)
  }
  return formData
}

export const createDocument = async (payload: DocumentPayload) => {
  const response = await http.post<Document>('/documents/', buildDocumentFormData(payload), {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
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
