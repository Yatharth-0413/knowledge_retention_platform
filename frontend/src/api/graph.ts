import { apiClient } from './client'
import type { TeamGraph } from './types'

export async function getTeamGraph(teamId: number): Promise<TeamGraph> {
  const { data } = await apiClient.get<TeamGraph>(`/teams/${teamId}/graph`)
  return data
}
