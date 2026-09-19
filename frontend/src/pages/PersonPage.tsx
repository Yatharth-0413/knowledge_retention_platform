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

  if (loading) return <p className="text-gray-500">Loading…</p>
  if (error || !profile) return <p className="text-sm text-red-600">{error ?? 'Person not found.'}</p>

  const documentCount = evidence.reduce((sum, e) => sum + e.document_count, 0)

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">{profile.name}</h1>
        <p className="text-sm text-gray-500">
          {profile.designation ?? 'Team member'} · {profile.email}
          {profile.phone_number ? ` · ${profile.phone_number}` : ''}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-2xl font-semibold text-gray-900">{evidence.length}</p>
          <p className="text-xs text-gray-500">Topics with documented evidence</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-2xl font-semibold text-gray-900">{documentCount}</p>
          <p className="text-xs text-gray-500">Contributing documents (across topics)</p>
        </div>
      </div>

      <section>
        <h2 className="mb-2 text-lg font-medium text-gray-900">Documented knowledge</h2>
        {evidence.length === 0 ? (
          <p className="text-sm text-gray-500">No documented knowledge evidence yet.</p>
        ) : (
          <ul className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
            {evidence.map((item) => (
              <li key={item.topic_id}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="font-medium text-gray-900">{item.topic_name}</span>
                  <span className="text-gray-700">
                    {item.score}% · {item.document_count} {item.document_count === 1 ? 'doc' : 'docs'}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                  <div className="h-full rounded-full bg-indigo-500" style={{ width: `${item.score}%` }} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
