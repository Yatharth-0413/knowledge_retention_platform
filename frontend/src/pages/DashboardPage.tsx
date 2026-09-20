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
        <ul className="knp-list">
          {teams.map((team) => (
            <li key={team.id} className="flex items-center justify-between px-4 py-3">
              <span className="font-medium text-gray-900">{team.name}</span>
              <Link to={`/teams/${team.id}`} className="knp-link text-sm">
                View team →
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
