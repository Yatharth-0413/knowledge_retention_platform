import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTeamRecommendations } from '../api/recommendations'
import type { TeamRecommendations, TopicRecommendation } from '../api/types'
import { RecommendationsCoverageChart } from './RecommendationsCharts'

const CATEGORY_LABELS: Record<TopicRecommendation['category'], string> = {
  functional: 'Functional',
  technical: 'Technical',
  mixed: 'Mixed',
  unclassified: 'Unclassified',
}

function TopicCard({ topic }: { topic: TopicRecommendation }) {
  const totalScore = topic.existing_contributors.reduce((sum, c) => sum + c.score, 0)

  return (
    <li className="knp-card p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 justify-between">
        <span className="font-medium text-gray-900">{topic.topic_name}</span>
        <div className="flex gap-2">
          <span className="knp-badge knp-badge-neutral">{CATEGORY_LABELS[topic.category]}</span>
          {topic.gap_candidates.length > 0 ? (
            <span className="knp-badge knp-badge-warning">{topic.gap_candidates.length} gap(s)</span>
          ) : (
            <span className="knp-badge knp-badge-success">Fully covered</span>
          )}
        </div>
      </div>

      {topic.existing_contributors.length > 0 ? (
        <>
          <div className="flex h-2 overflow-hidden rounded-full bg-gray-100">
            {topic.existing_contributors.map((c, i) => (
              <div
                key={c.user_id}
                className="h-full bg-[var(--color-brand)] first:rounded-l-full last:rounded-r-full"
                style={{ width: `${totalScore > 0 ? (c.score / totalScore) * 100 : 0}%`, opacity: Math.max(0.25, 1 - i * 0.15) }}
              />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
            {topic.existing_contributors.map((c) => (
              <Link key={c.user_id} to={`/people/${c.user_id}`} className="hover:text-[var(--color-brand)] hover:underline">
                {c.name} — {totalScore > 0 ? Math.round((c.score / totalScore) * 100) : 0}%
              </Link>
            ))}
          </div>
        </>
      ) : (
        <p className="text-xs text-gray-500">No documented evidence yet</p>
      )}

      <div className="mt-3 border-t border-gray-100 pt-2">
        {topic.gap_candidates.length > 0 ? (
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-xs font-medium text-gray-500">Knowledge gap:</span>
            {topic.gap_candidates.map((c) => (
              <Link key={c.user_id} to={`/people/${c.user_id}`} className="knp-link text-xs">
                {c.name}
              </Link>
            ))}
          </div>
        ) : (
          <p className="text-xs text-green-700">No gap — everyone in this category has documented evidence.</p>
        )}
      </div>
    </li>
  )
}

function TopicGroup({ title, topics, emptyText }: { title: string; topics: TopicRecommendation[]; emptyText: string }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-gray-700">{title}</h3>
      {topics.length === 0 ? (
        <p className="text-sm text-gray-500">{emptyText}</p>
      ) : (
        <ul className="space-y-3">
          {topics.map((topic) => (
            <TopicCard key={topic.topic_id} topic={topic} />
          ))}
        </ul>
      )}
    </div>
  )
}

export function KnowledgeRecommendations({ teamId }: { teamId: number }) {
  const [data, setData] = useState<TeamRecommendations | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getTeamRecommendations(teamId)
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [teamId])

  if (loading) return <p className="text-sm text-gray-500">Loading…</p>
  if (!data || data.topics.length === 0) return <p className="text-sm text-gray-500">Not enough documented evidence yet.</p>

  const functionalTopics = data.topics.filter((t) => t.category === 'functional')
  const technicalTopics = data.topics.filter((t) => t.category === 'technical')
  const otherTopics = data.topics.filter((t) => t.category === 'mixed' || t.category === 'unclassified')

  return (
    <div className="space-y-6">
      <RecommendationsCoverageChart summary={data.summary} />
      <TopicGroup title="Functional knowledge" topics={functionalTopics} emptyText="No functional topics yet." />
      <TopicGroup title="Technical knowledge" topics={technicalTopics} emptyText="No technical topics yet." />
      <TopicGroup title="Mixed / unclassified topics" topics={otherTopics} emptyText="No mixed or unclassified topics." />
    </div>
  )
}
