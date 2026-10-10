import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import sgLogo from '../assets/societe-generale-logo.png'
import { useAuthStore } from '../store/authStore'
import { getInitials } from '../utils/initials'
import { Dropdown, DropdownItem } from './ui/Dropdown'

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  const initials = user ? getInitials(user.name) : ''

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-3">
              <img src={sgLogo} alt="Société Générale" className="h-7 w-auto shrink-0" />
              <span className="hidden h-6 w-px bg-gray-200 sm:block" />
              <span className="hidden text-sm font-semibold tracking-tight text-gray-700 sm:block">
                Knowledge Retention Platform
              </span>
            </Link>
            {user && (
              <Link to="/" className="text-sm font-medium text-gray-700 hover:text-[var(--color-brand)]">
                Teams
              </Link>
            )}
          </div>
          {user && (
            <Dropdown
              align="right"
              trigger={({ toggle }) => (
                <button
                  type="button"
                  onClick={toggle}
                  className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-3 transition-colors hover:bg-gray-50"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-brand)] text-xs font-semibold text-white">
                    {initials}
                  </span>
                  <span className="hidden text-left text-sm leading-tight sm:block">
                    <span className="block font-medium text-gray-900">{user.name}</span>
                    <span className="block text-xs capitalize text-gray-500">{user.role}</span>
                  </span>
                  <span className="hidden text-gray-400 sm:inline">▾</span>
                </button>
              )}
            >
              {(close) => (
                <div className="w-52">
                  <div className="border-b border-gray-100 px-3 py-2">
                    <p className="text-sm font-medium text-gray-900">{user.name}</p>
                    <p className="text-xs capitalize text-gray-500">{user.role}</p>
                  </div>
                  <DropdownItem
                    onClick={() => {
                      close()
                      handleLogout()
                    }}
                  >
                    Log out
                  </DropdownItem>
                </div>
              )}
            </Dropdown>
          )}
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">{children}</main>

      <footer className="border-t border-gray-200">
        <div className="mx-auto flex max-w-7xl flex-col gap-1 px-6 py-4 text-xs text-gray-500 sm:flex-row sm:items-center sm:justify-between">
          <span>© Knowledge Retention Platform · Hackathon MVP</span>
          <span>Documented knowledge evidence, not employee competence.</span>
        </div>
      </footer>
    </div>
  )
}
