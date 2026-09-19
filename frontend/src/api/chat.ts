import { apiClient } from './client'
import type { ChatResponse } from './types'

export async function askQuestion(teamId: number, question: string): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>(`/teams/${teamId}/chat`, { question })
  return data
}
