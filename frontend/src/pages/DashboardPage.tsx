import { type FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { createTeam, listTeams } from '../api/teams'
import type { Team } from '../api/types'
import { useAuthStore } from '../store/authStore'

export function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const [teams, setTeams] = useState<Team[]>([])
  const [loading, setLoading] = useState(true)
  const [newTeamName, setNewTeamName] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    setLoading(true)
    try {
      setTeams(await listTeams())
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleCreateTeam(e: FormEvent) {
    e.preventDefault()
    if (!newTeamName.trim()) return
    setCreating(true)
    setError(null)
    try {
      await createTeam(newTeamName.trim())
      setNewTeamName('')
      await refresh()
    } catch {
      setError('Could not create team.')
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Loading…</p>

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="knp-page-title">{user?.role === 'manager' ? 'Your teams' : 'Your team'}</h1>
          <p className="knp-page-subtitle">
            {user?.role === 'manager'
              ? 'Create teams and add members to start collecting documented knowledge.'
              : 'Documents, topics and knowledge evidence for your team will appear here.'}
          </p>
        </div>
      </div>

      {user?.role === 'manager' && (
        <form onSubmit={handleCreateTeam} className="flex gap-2">
          <input
            value={newTeamName}
            onChange={(e) => setNewTeamName(e.target.value)}
            placeholder="New team name"
            className="knp-input flex-1"
          />
          <button type="submit" disabled={creating} className="knp-btn-primary">
            {creating ? 'Creating…' : 'Create team'}
          </button>
        </form>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {teams.length === 0 ? (
        <p className="text-sm text-gray-500">No teams yet.</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {teams.map((team) => (
            <li key={team.id}>
              <Link
                to={`/teams/${team.id}`}
                className="knp-card knp-card-hover block h-full p-4 transition-colors hover:border-[var(--color-brand)]"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-red-50 text-sm font-semibold text-[var(--color-brand)]">
                    {team.name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="truncate font-medium text-gray-900">{team.name}</span>
                </div>
                <span className="knp-link mt-3 inline-block text-sm">View team →</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
