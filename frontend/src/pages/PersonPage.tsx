import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getUserKnowledge } from '../api/knowledge'
import type { UserProfile, UserTopicEvidence } from '../api/types'
import { getUserProfile } from '../api/users'

export function PersonPage() {
  const { userId } = useParams<{ userId: string }>()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [evidence, setEvidence] = useState<UserTopicEvidence[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!userId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([getUserProfile(Number(userId)), getUserKnowledge(Number(userId))])
      .then(([profileData, evidenceData]) => {
        if (cancelled) return
        setProfile(profileData)
        setEvidence(evidenceData)
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

  return (
    <div className="space-y-8">
      <div>
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
                  <span className="text-gray-700">
                    {item.score}% · {item.document_count} {item.document_count === 1 ? 'doc' : 'docs'}
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
    </div>
  )
}
