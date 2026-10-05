import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTeamContributions } from '../api/analytics'
import type { ContributionActivity as ContributionActivityItem } from '../api/types'

export function ContributionActivity({ teamId }: { teamId: number }) {
  const [items, setItems] = useState<ContributionActivityItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getTeamContributions(teamId)
      .then((data) => {
        if (!cancelled) setItems(data)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [teamId])

  if (loading) return <p className="text-sm text-gray-500">Loading…</p>

  const maxDocuments = Math.max(1, ...items.map((i) => i.document_count))
  const hasActivity = items.some((i) => i.document_count > 0)

  if (!hasActivity) {
    return <p className="text-sm text-gray-500">No documented contributions yet.</p>
  }

  return (
    <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
      {items.map((item) => (
        <li key={item.user_id} className="px-4 py-3">
          <div className="mb-1 flex items-center justify-between text-sm">
            <Link to={`/people/${item.user_id}`} className="font-medium text-gray-900 hover:text-indigo-600 hover:underline">
              {item.name}
            </Link>
            <span className="text-gray-600">
              {item.document_count} {item.document_count === 1 ? 'document' : 'documents'} · {item.topic_count}{' '}
              {item.topic_count === 1 ? 'topic' : 'topics'}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-gray-100">
            <div
              className="h-full rounded-full bg-indigo-500"
              style={{ width: `${(item.document_count / maxDocuments) * 100}%` }}
            />
          </div>
          {item.last_activity && (
            <p className="mt-1 text-xs text-gray-400">Last activity {new Date(item.last_activity).toLocaleDateString()}</p>
          )}
        </li>
      ))}
    </ul>
  )
}
