import { apiClient } from './client'
import type { DependencyTopic, TeamDashboard } from './types'

export async function getTeamDashboard(teamId: number): Promise<TeamDashboard> {
  const { data } = await apiClient.get<TeamDashboard>(`/teams/${teamId}/dashboard`)
  return data
}

export async function getTeamDependency(teamId: number): Promise<DependencyTopic[]> {
  const { data } = await apiClient.get<DependencyTopic[]>(`/teams/${teamId}/dependency`)
  return data
}
