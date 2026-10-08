import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2.5">
              <span className="h-6 w-6 rounded-sm bg-[var(--color-brand)]" />
              <span className="text-base font-bold tracking-tight text-gray-900">Knowledge Retention Platform</span>
            </Link>
            {user && (
              <Link to="/" className="text-sm font-medium text-gray-700 hover:text-gray-900">
                Teams
              </Link>
            )}
          </div>
          {user && (
            <div className="flex items-center gap-4">
              <div className="text-right text-sm leading-tight">
                <p className="font-medium text-gray-900">{user.name}</p>
                <p className="text-xs capitalize text-gray-500">{user.role}</p>
              </div>
              <button onClick={handleLogout} className="knp-btn-secondary py-1.5 text-xs">
                Log out
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">{children}</main>

      <footer className="border-t border-gray-200">
        <div className="mx-auto flex max-w-5xl flex-col gap-1 px-6 py-4 text-xs text-gray-500 sm:flex-row sm:items-center sm:justify-between">
          <span>© Knowledge Retention Platform · Hackathon MVP</span>
          <span>Documented knowledge evidence, not employee competence.</span>
        </div>
      </footer>
    </div>
  )
}
