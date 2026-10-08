import { apiClient } from './client'
import type { EmailIngestResult, KnowledgeDocument } from './types'

export async function listDocuments(teamId: number): Promise<KnowledgeDocument[]> {
  const { data } = await apiClient.get<KnowledgeDocument[]>(`/teams/${teamId}/documents`)
  return data
}

export async function uploadDocument(teamId: number, file: File): Promise<KnowledgeDocument | EmailIngestResult> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post<KnowledgeDocument | EmailIngestResult>(`/teams/${teamId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
