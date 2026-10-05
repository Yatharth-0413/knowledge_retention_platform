import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTeamDependency } from '../api/analytics'
import type { DependencyTopic } from '../api/types'

const CONCENTRATION_STYLES: Record<DependencyTopic['concentration'], string> = {
  HIGH: 'bg-red-100 text-red-800',
  DISTRIBUTED: 'bg-green-100 text-green-800',
}

export function DependencyAnalyzer({ teamId }: { teamId: number }) {
  const [topics, setTopics] = useState<DependencyTopic[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getTeamDependency(teamId)
      .then(setTopics)
      .finally(() => setLoading(false))
  }, [teamId])

  if (loading) return <p className="text-sm text-gray-500">Loading…</p>
  if (topics.length === 0) return <p className="text-sm text-gray-500">Not enough documented evidence yet.</p>

  return (
    <ul className="space-y-3">
      {topics.map((topic) => (
        <li key={topic.topic_id} className="rounded-lg border border-gray-200 bg-white p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-medium text-gray-900">{topic.topic_name}</span>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${CONCENTRATION_STYLES[topic.concentration]}`}>
              {topic.concentration}
            </span>
          </div>
          <div className="flex h-2 overflow-hidden rounded-full bg-gray-100">
            {topic.contributors.map((c, i) => (
              <div
                key={c.user_id}
                className="h-full bg-indigo-500 first:rounded-l-full last:rounded-r-full"
                style={{ width: `${c.share * 100}%`, opacity: Math.max(0.25, 1 - i * 0.15) }}
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            {topic.contributors.map((c) => (
              <Link key={c.user_id} to={`/people/${c.user_id}`} className="hover:text-indigo-600 hover:underline">
                {c.name} — {Math.round(c.share * 100)}%
              </Link>
            ))}
          </div>
        </li>
      ))}
    </ul>
  )
}
