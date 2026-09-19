import { apiClient } from './client'
import type { Team, TeamDetail, TeamMember } from './types'

export async function listTeams(): Promise<Team[]> {
  const { data } = await apiClient.get<Team[]>('/teams')
  return data
}

export async function createTeam(name: string): Promise<Team> {
  const { data } = await apiClient.post<Team>('/teams', { name })
  return data
}

export async function getTeam(teamId: number): Promise<TeamDetail> {
  const { data } = await apiClient.get<TeamDetail>(`/teams/${teamId}`)
  return data
}

export async function addMember(
  teamId: number,
  payload: {
    name: string
    email: string
    password: string
    designation?: string
    phone_number?: string
  },
): Promise<TeamMember> {
  const { data } = await apiClient.post<TeamMember>(`/teams/${teamId}/members`, payload)
  return data
}
