import { apiClient } from './client'
import type { CurrentUser } from './types'

interface TokenResponse {
  access_token: string
  token_type: string
}

export async function registerManager(payload: {
  name: string
  email: string
  password: string
  designation?: string
  phone_number?: string
}): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/register', payload)
  return data
}

export async function login(payload: { email: string; password: string }): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', payload)
  return data
}

export async function fetchCurrentUser(): Promise<CurrentUser> {
  const { data } = await apiClient.get<CurrentUser>('/auth/me')
  return data
}
