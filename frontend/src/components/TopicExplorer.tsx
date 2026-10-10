import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTopic, listTeamTopics } from '../api/knowledge'
import type { TopicDetail, TopicSummary } from '../api/types'
import { Dropdown, DropdownItem } from './ui/Dropdown'

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
      .then((data) => {
        setTopics(data)
        setSelectedId((prev) => prev ?? data[0]?.id ?? null)
      })
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

  const selectedTopic = topics.find((t) => t.id === selectedId) ?? null

  if (loading) return <p className="text-sm text-gray-500">Loading topics…</p>
  if (topics.length === 0) return <p className="text-sm text-gray-500">No topics found yet. Upload documents to extract topics.</p>

  return (
    <div className="space-y-4">
      <Dropdown
        className="block"
        trigger={({ toggle }) => (
          <button
            type="button"
            onClick={toggle}
            className="knp-input flex w-full max-w-sm items-center justify-between text-left sm:w-80"
          >
            <span className="truncate">{selectedTopic ? selectedTopic.name : 'Select a topic…'}</span>
            <span className="ml-2 shrink-0 text-gray-400">▾</span>
          </button>
        )}
      >
        {(close) => (
          <div className="w-80">
            <div className="border-b border-gray-100 p-2">
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search topics…"
                className="knp-input"
              />
            </div>
            <div className="max-h-72 overflow-y-auto">
              {filtered.length === 0 ? (
                <p className="px-3 py-3 text-sm text-gray-500">No topics match.</p>
              ) : (
                filtered.map((topic) => (
                  <DropdownItem
                    key={topic.id}
                    active={selectedId === topic.id}
                    onClick={() => {
                      setSelectedId(topic.id)
                      close()
                    }}
                  >
                    <span className="truncate">{topic.name}</span>
                    <span className="shrink-0 text-xs text-gray-400">
                      {topic.contributor_count} {topic.contributor_count === 1 ? 'person' : 'people'} ·{' '}
                      {topic.document_count} {topic.document_count === 1 ? 'doc' : 'docs'}
                    </span>
                  </DropdownItem>
                ))
              )}
            </div>
          </div>
        )}
      </Dropdown>

      <div className="knp-card p-4">
        {selectedId === null ? (
          <p className="text-sm text-gray-500">Select a topic to see who has documented knowledge evidence.</p>
        ) : detailLoading || !detail ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">{detail.name}</h3>

            <div>
              <p className="knp-section-title mb-1">People</p>
              {detail.people.length === 0 ? (
                <p className="text-sm text-gray-500">No documented evidence yet.</p>
              ) : (
                <ul className="space-y-2">
                  {detail.people.map((person) => (
                    <li key={person.user_id}>
                      <div className="flex items-center justify-between text-sm">
                        <Link to={`/people/${person.user_id}`} className="knp-link">
                          {person.name}
                          {person.designation ? <span className="text-gray-400"> · {person.designation}</span> : null}
                        </Link>
                        <span className="font-medium text-gray-700">{person.score}%</span>
                      </div>
                      <div className="knp-bar-track mt-1">
                        <div className="knp-bar-fill" style={{ width: `${person.score}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <p className="knp-section-title mb-1">Documents</p>
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
