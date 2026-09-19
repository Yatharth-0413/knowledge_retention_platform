import { apiClient } from './client'
import type { TopicDetail, TopicSummary, UserTopicEvidence } from './types'

export async function listTeamTopics(teamId: number): Promise<TopicSummary[]> {
  const { data } = await apiClient.get<TopicSummary[]>(`/teams/${teamId}/topics`)
  return data
}

export async function getTopic(teamId: number, topicId: number): Promise<TopicDetail> {
  const { data } = await apiClient.get<TopicDetail>(`/teams/${teamId}/topics/${topicId}`)
  return data
}

export async function getUserKnowledge(userId: number): Promise<UserTopicEvidence[]> {
  const { data } = await apiClient.get<UserTopicEvidence[]>(`/users/${userId}/knowledge`)
  return data
}
