import { apiClient } from './client'
import type { TeamRecommendations } from './types'

export async function getTeamRecommendations(teamId: number): Promise<TeamRecommendations> {
  const { data } = await apiClient.get<TeamRecommendations>(`/teams/${teamId}/recommendations`)
  return data
}
