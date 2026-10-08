import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getUserDocuments } from '../api/documents'
import { getUserKnowledge } from '../api/knowledge'
import type { FreshnessLabel, KnowledgeDocument, UserProfile, UserTopicEvidence } from '../api/types'
import { getUserProfile } from '../api/users'

const FRESHNESS_STYLES: Record<FreshnessLabel, string> = {
  New: 'knp-badge knp-badge-success',
  Medium: 'knp-badge knp-badge-warning',
  Old: 'knp-badge knp-badge-neutral',
}

export function PersonPage() {
  const { userId } = useParams<{ userId: string }>()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [evidence, setEvidence] = useState<UserTopicEvidence[]>([])
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!userId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([getUserProfile(Number(userId)), getUserKnowledge(Number(userId)), getUserDocuments(Number(userId))])
      .then(([profileData, evidenceData, documentsData]) => {
        if (cancelled) return
        setProfile(profileData)
        setEvidence(evidenceData)
        setDocuments(documentsData)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load this knowledge profile. You may not have access to it.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [userId])

  if (loading) return <p className="text-sm text-gray-500">Loading…</p>
  if (error || !profile) return <p className="text-sm text-red-600">{error ?? 'Person not found.'}</p>

  const documentCount = evidence.reduce((sum, e) => sum + e.document_count, 0)
  const typeBreakdown = documents.reduce<Record<string, number>>((acc, d) => {
    acc[d.file_type] = (acc[d.file_type] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-8">
      <div>
        <Link to="/" className="knp-link mb-1 inline-block text-sm">
          ← Back to teams
        </Link>
        <h1 className="knp-page-title">{profile.name}</h1>
        <p className="knp-page-subtitle">
          {profile.designation ?? 'Team member'} · {profile.email}
          {profile.phone_number ? ` · ${profile.phone_number}` : ''}
        </p>
      </div>

      <div className="knp-stat-strip !grid-cols-2">
        <div className="knp-stat-cell">
          <p className="knp-stat-label">Topics with documented evidence</p>
          <p className="knp-stat-value">{evidence.length}</p>
        </div>
        <div className="knp-stat-cell">
          <p className="knp-stat-label">Contributing documents (across topics)</p>
          <p className="knp-stat-value">{documentCount}</p>
        </div>
      </div>

      <section>
        <h2 className="mb-2 knp-section-title">Documented knowledge</h2>
        {evidence.length === 0 ? (
          <p className="text-sm text-gray-500">No documented knowledge evidence yet.</p>
        ) : (
          <ul className="space-y-3 knp-card p-4">
            {evidence.map((item) => (
              <li key={item.topic_id}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="font-medium text-gray-900">{item.topic_name}</span>
                  <span className="flex items-center gap-2 text-gray-700">
                    {item.score}% · {item.document_count} {item.document_count === 1 ? 'doc' : 'docs'}
                    <span className={FRESHNESS_STYLES[item.freshness_label]}>{item.freshness_label}</span>
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                  <div className="h-full rounded-full bg-[var(--color-brand)]" style={{ width: `${item.score}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-2 knp-section-title">Documents uploaded</h2>
        {documents.length === 0 ? (
          <p className="text-sm text-gray-500">No documents uploaded yet.</p>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {Object.entries(typeBreakdown).map(([type, count]) => (
                <span key={type} className="knp-badge knp-badge-neutral">
                  {type.toUpperCase()}: {count}
                </span>
              ))}
            </div>
            <ul className="knp-list">
              {documents.map((doc) => (
                <li key={doc.id} className="flex items-center justify-between gap-4 px-4 py-3">
                  <p className="min-w-0 truncate text-sm text-gray-700">{doc.filename}</p>
                  <span className="shrink-0 text-xs text-gray-400">{new Date(doc.created_at).toLocaleDateString()}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
