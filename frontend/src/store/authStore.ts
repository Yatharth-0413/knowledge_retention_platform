import { create } from 'zustand'
import { fetchCurrentUser, login as loginRequest, registerManager as registerRequest } from '../api/auth'
import type { CurrentUser } from '../api/types'

interface AuthState {
  token: string | null
  user: CurrentUser | null
  status: 'idle' | 'loading' | 'ready'
  error: string | null
  login: (email: string, password: string) => Promise<void>
  registerManager: (payload: {
    name: string
    email: string
    password: string
    designation?: string
    phone_number?: string
  }) => Promise<void>
  logout: () => void
  hydrate: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('krp_token'),
  user: null,
  status: 'idle',
  error: null,

  async login(email, password) {
    set({ error: null })
    const { access_token } = await loginRequest({ email, password })
    localStorage.setItem('krp_token', access_token)
    set({ token: access_token })
    const user = await fetchCurrentUser()
    set({ user })
  },

  async registerManager(payload) {
    set({ error: null })
    const { access_token } = await registerRequest(payload)
    localStorage.setItem('krp_token', access_token)
    set({ token: access_token })
    const user = await fetchCurrentUser()
    set({ user })
  },

  logout() {
    localStorage.removeItem('krp_token')
    set({ token: null, user: null })
  },

  async hydrate() {
    const token = get().token
    if (!token) {
      set({ status: 'ready' })
      return
    }
    set({ status: 'loading' })
    try {
      const user = await fetchCurrentUser()
      set({ user, status: 'ready' })
    } catch {
      localStorage.removeItem('krp_token')
      set({ token: null, user: null, status: 'ready' })
    }
  },
}))
