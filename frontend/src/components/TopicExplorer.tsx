import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTopic, listTeamTopics } from '../api/knowledge'
import type { TopicDetail, TopicSummary } from '../api/types'

export function TopicExplorer({ teamId }: { teamId: number }) {
  const [topics, setTopics] = useState<TopicSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<TopicDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    listTeamTopics(teamId)
      .then(setTopics)
      .finally(() => setLoading(false))
  }, [teamId])

  useEffect(() => {
    if (selectedId === null) {
      setDetail(null)
      return
    }
    setDetailLoading(true)
    getTopic(teamId, selectedId)
      .then(setDetail)
      .finally(() => setDetailLoading(false))
  }, [teamId, selectedId])

  const filtered = useMemo(
    () => topics.filter((t) => t.name.toLowerCase().includes(query.trim().toLowerCase())),
    [topics, query],
  )

  if (loading) return <p className="text-sm text-gray-500">Loading topics…</p>

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search topics…"
          className="mb-2 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        />
        {filtered.length === 0 ? (
          <p className="text-sm text-gray-500">No topics found yet. Upload documents to extract topics.</p>
        ) : (
          <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
            {filtered.map((topic) => (
              <li key={topic.id}>
                <button
                  onClick={() => setSelectedId(topic.id)}
                  className={`flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50 ${
                    selectedId === topic.id ? 'bg-indigo-50' : ''
                  }`}
                >
                  <span className="font-medium text-gray-900">{topic.name}</span>
                  <span className="text-xs text-gray-500">
                    {topic.contributor_count} {topic.contributor_count === 1 ? 'person' : 'people'} ·{' '}
                    {topic.document_count} {topic.document_count === 1 ? 'doc' : 'docs'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4">
        {selectedId === null ? (
          <p className="text-sm text-gray-500">Select a topic to see who has documented knowledge evidence.</p>
        ) : detailLoading || !detail ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : (
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-gray-900">{detail.name}</h3>

            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">People</p>
              {detail.people.length === 0 ? (
                <p className="text-sm text-gray-500">No documented evidence yet.</p>
              ) : (
                <ul className="space-y-2">
                  {detail.people.map((person) => (
                    <li key={person.user_id}>
                      <div className="flex items-center justify-between text-sm">
                        <Link to={`/people/${person.user_id}`} className="text-gray-900 hover:text-indigo-600 hover:underline">
                          {person.name}
                          {person.designation ? <span className="text-gray-400"> · {person.designation}</span> : null}
                        </Link>
                        <span className="font-medium text-gray-700">{person.score}%</span>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
                        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${person.score}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-500">Documents</p>
              {detail.documents.length === 0 ? (
                <p className="text-sm text-gray-500">No documents.</p>
              ) : (
                <ul className="space-y-1 text-sm text-gray-700">
                  {detail.documents.map((doc) => (
                    <li key={doc.id}>{doc.filename}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
