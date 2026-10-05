import { useEffect, useState } from 'react'
import { getTeamDashboard } from '../api/analytics'
import type { TeamDashboard } from '../api/types'

const STAT_TILES: { key: keyof Pick<TeamDashboard, 'member_count' | 'document_count' | 'topic_count' | 'active_contributor_count'>; label: string }[] = [
  { key: 'member_count', label: 'Members' },
  { key: 'document_count', label: 'Documents' },
  { key: 'topic_count', label: 'Topics' },
  { key: 'active_contributor_count', label: 'Active contributors' },
]

export function TeamDashboardStats({ teamId }: { teamId: number }) {
  const [dashboard, setDashboard] = useState<TeamDashboard | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getTeamDashboard(teamId)
      .then((data) => {
        if (!cancelled) setDashboard(data)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [teamId])

  if (loading) return <p className="text-sm text-gray-500">Loading dashboard…</p>
  if (!dashboard) return null

  const coverageTotal =
    dashboard.coverage.well_covered + dashboard.coverage.moderately_covered + dashboard.coverage.weakly_covered

  return (
    <section className="space-y-4">
      <div className="knp-stat-strip">
        {STAT_TILES.map(({ key, label }) => (
          <div key={key} className="knp-stat-cell">
            <p className="knp-stat-label">{label}</p>
            <p className="knp-stat-value">{dashboard[key]}</p>
          </div>
        ))}
      </div>

      {coverageTotal > 0 && (
        <div className="knp-card p-4">
          <p className="knp-section-title mb-2">Knowledge coverage</p>
          <div className="flex h-2 overflow-hidden rounded-full bg-gray-100">
            <div
              className="bg-green-500"
              style={{ width: `${(dashboard.coverage.well_covered / coverageTotal) * 100}%` }}
            />
            <div
              className="ml-0.5 bg-amber-400"
              style={{ width: `${(dashboard.coverage.moderately_covered / coverageTotal) * 100}%` }}
            />
            <div
              className="ml-0.5 bg-red-400"
              style={{ width: `${(dashboard.coverage.weakly_covered / coverageTotal) * 100}%` }}
            />
          </div>
          <div className="mt-2 flex gap-4 text-xs text-gray-600">
            <span>
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-green-500" />
              Well covered: {dashboard.coverage.well_covered}
            </span>
            <span>
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-amber-400" />
              Moderately: {dashboard.coverage.moderately_covered}
            </span>
            <span>
              <span className="mr-1 inline-block h-2 w-2 rounded-full bg-red-400" />
              Weakly: {dashboard.coverage.weakly_covered}
            </span>
          </div>
        </div>
      )}

      {dashboard.recent_activity.length > 0 && (
        <div className="knp-card p-4">
          <p className="knp-section-title mb-2">Recent activity</p>
          <ul className="space-y-1 text-sm text-gray-700">
            {dashboard.recent_activity.map((item, i) => (
              <li key={i}>
                <span className="font-medium text-gray-900">{item.user_name}</span> uploaded {item.filename}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
