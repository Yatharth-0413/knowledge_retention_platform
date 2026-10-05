import { apiClient } from './client'
import type { UserProfile } from './types'

export async function getUserProfile(userId: number): Promise<UserProfile> {
  const { data } = await apiClient.get<UserProfile>(`/users/${userId}`)
  return data
}
