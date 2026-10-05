import { type ChangeEvent, type FormEvent, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { listDocuments, uploadDocument } from '../api/documents'
import { addMember, getTeam } from '../api/teams'
import type { KnowledgeDocument, TeamDetail } from '../api/types'
import { ContributionActivity } from '../components/ContributionActivity'
import { DependencyAnalyzer } from '../components/DependencyAnalyzer'
import { TeamChat } from '../components/TeamChat'
import { TeamDashboardStats } from '../components/TeamDashboardStats'
import { TopicExplorer } from '../components/TopicExplorer'
import { useAuthStore } from '../store/authStore'

const STATUS_STYLES: Record<KnowledgeDocument['status'], string> = {
  processing: 'knp-badge knp-badge-warning',
  ready: 'knp-badge knp-badge-success',
  failed: 'knp-badge knp-badge-danger',
}

export function TeamPage() {
  const { teamId } = useParams<{ teamId: string }>()
  const user = useAuthStore((s) => s.user)
  const [team, setTeam] = useState<TeamDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [designation, setDesignation] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [documentsLoading, setDocumentsLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [knowledgeRefreshKey, setKnowledgeRefreshKey] = useState(0)

  async function refresh() {
    if (!teamId) return
    setLoading(true)
    try {
      setTeam(await getTeam(Number(teamId)))
    } catch {
      setError('Could not load team.')
    } finally {
      setLoading(false)
    }
  }

  async function refreshDocuments() {
    if (!teamId) return
    setDocumentsLoading(true)
    try {
      setDocuments(await listDocuments(Number(teamId)))
    } finally {
      setDocumentsLoading(false)
    }
  }

  useEffect(() => {
    refresh()
    refreshDocuments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [teamId])

  // Documents are processed (topic extraction + embedding) asynchronously after upload.
  // Poll while any are still "processing" so the page doesn't sit on a stale status.
  useEffect(() => {
    if (!documents.some((d) => d.status === 'processing')) return
    const timeout = setTimeout(async () => {
      await refreshDocuments()
      setKnowledgeRefreshKey((k) => k + 1)
    }, 2500)
    return () => clearTimeout(timeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents])

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !teamId) return
    setUploading(true)
    setUploadError(null)
    try {
      await uploadDocument(Number(teamId), file)
      await refreshDocuments()
      setKnowledgeRefreshKey((k) => k + 1)
    } catch {
      setUploadError('Could not upload document. Allowed types: pdf, docx, xlsx, csv, msg, eml.')
    } finally {
      setUploading(false)
    }
  }

  async function handleAddMember(e: FormEvent) {
    e.preventDefault()
    if (!teamId) return
    setAdding(true)
    setAddError(null)
    try {
      await addMember(Number(teamId), {
        name,
        email,
        password,
        designation: designation || undefined,
        phone_number: phoneNumber || undefined,
      })
      setName('')
      setEmail('')
      setPassword('')
      setDesignation('')
      setPhoneNumber('')
      await refresh()
    } catch {
      setAddError('Could not add member. That email may already be registered.')
    } finally {
      setAdding(false)
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Loading…</p>
  if (error || !team) return <p className="text-sm text-red-600">{error ?? 'Team not found.'}</p>

  const isOwnerManager = user?.role === 'manager' && user.id === team.manager_id

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="knp-page-title">{team.name}</h1>
        <Link to={`/teams/${team.id}/graph`} className="knp-btn-secondary">
          View knowledge graph →
        </Link>
      </div>

      <TeamDashboardStats teamId={team.id} key={`stats-${knowledgeRefreshKey}`} />

      <section>
        <h2 className="mb-2 knp-section-title">AI knowledge assistant</h2>
        <TeamChat teamId={team.id} />
      </section>

      <section>
        <h2 className="mb-2 knp-section-title">Members</h2>
        {team.members.length === 0 ? (
          <p className="text-sm text-gray-500">No members yet.</p>
        ) : (
          <ul className="knp-list">
            {team.members.map((member) => (
              <li key={member.id} className="flex flex-col px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <Link to={`/people/${member.id}`} className="knp-link font-medium">
                    {member.name}
                  </Link>
                  <p className="text-sm text-gray-500">
                    {member.designation ?? 'Member'} · {member.email}
                    {member.phone_number ? ` · ${member.phone_number}` : ''}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="knp-section-title">Documents</h2>
          <label className="knp-btn-primary cursor-pointer">
            {uploading ? 'Uploading…' : 'Upload document'}
            <input
              type="file"
              accept=".pdf,.docx,.xlsx,.csv,.msg,.eml"
              onChange={handleUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>
        {uploadError && <p className="mb-2 text-sm text-red-600">{uploadError}</p>}
        {documentsLoading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-gray-500">No documents uploaded yet.</p>
        ) : (
          <ul className="knp-list">
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="font-medium text-gray-900">{doc.filename}</p>
                  <p className="text-sm text-gray-500">
                    {doc.file_type.toUpperCase()} · {new Date(doc.created_at).toLocaleString()}
                  </p>
                </div>
                <span className={STATUS_STYLES[doc.status]}>{doc.status}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-2 knp-section-title">Topic explorer</h2>
        <TopicExplorer teamId={team.id} key={`topics-${knowledgeRefreshKey}`} />
      </section>

      <section>
        <h2 className="mb-1 knp-section-title">Dependency analyzer</h2>
        <p className="mb-3 text-sm text-gray-500">
          Topics where documented knowledge is concentrated around one person. This reflects team knowledge
          distribution, not the person.
        </p>
        <DependencyAnalyzer teamId={team.id} key={`dependency-${knowledgeRefreshKey}`} />
      </section>

      <section>
        <h2 className="mb-1 knp-section-title">Knowledge contribution activity</h2>
        <p className="mb-3 text-sm text-gray-500">
          Documents uploaded and topics contributed per person. This tracks documented contribution, not performance.
        </p>
        <ContributionActivity teamId={team.id} key={`contributions-${knowledgeRefreshKey}`} />
      </section>

      {isOwnerManager && (
        <section>
          <h2 className="mb-2 knp-section-title">Add a member</h2>
          <form onSubmit={handleAddMember} className="grid max-w-lg gap-3 knp-card p-4">
            <div>
              <label className="knp-label">Name</label>
              <input required value={name} onChange={(e) => setName(e.target.value)} className="knp-input" />
            </div>
            <div>
              <label className="knp-label">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="knp-input"
              />
            </div>
            <div>
              <label className="knp-label">Temporary password</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="knp-input"
              />
            </div>
            <div>
              <label className="knp-label">Designation</label>
              <input
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
                className="knp-input"
              />
            </div>
            <div>
              <label className="knp-label">Phone number</label>
              <input
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                className="knp-input"
              />
            </div>
            {addError && <p className="text-sm text-red-600">{addError}</p>}
            <button type="submit" disabled={adding} className="knp-btn-primary">
              {adding ? 'Adding…' : 'Add member'}
            </button>
          </form>
        </section>
      )}
    </div>
  )
}
