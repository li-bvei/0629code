import http from '../services/http'
import type { Document, DocumentPayload, ListParams, PaginatedResponse } from '../types/api'

export const listDocuments = async (params?: ListParams) => {
  const response = await http.get<PaginatedResponse<Document>>('/documents/', { params })
  return response.data
}

const buildDocumentFormData = (payload: DocumentPayload) => {
  const formData = new FormData()
  formData.append('case', String(payload.case))
  formData.append('title', payload.title)
  formData.append('source', payload.source || 'internal')
  formData.append('is_visible_to_client', String(Boolean(payload.is_visible_to_client)))
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
