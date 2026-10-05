import { type ChangeEvent, type FormEvent, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { listDocuments, uploadDocument } from '../api/documents'
import { addMember, getTeam } from '../api/teams'
import type { KnowledgeDocument, TeamDetail } from '../api/types'
import { DependencyAnalyzer } from '../components/DependencyAnalyzer'
import { TeamChat } from '../components/TeamChat'
import { TeamDashboardStats } from '../components/TeamDashboardStats'
import { TopicExplorer } from '../components/TopicExplorer'
import { useAuthStore } from '../store/authStore'

const STATUS_STYLES: Record<KnowledgeDocument['status'], string> = {
  processing: 'bg-amber-100 text-amber-800',
  ready: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
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

  if (loading) return <p className="text-gray-500">Loading…</p>
  if (error || !team) return <p className="text-sm text-red-600">{error ?? 'Team not found.'}</p>

  const isOwnerManager = user?.role === 'manager' && user.id === team.manager_id

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-semibold text-gray-900">{team.name}</h1>

      <TeamDashboardStats teamId={team.id} key={`stats-${knowledgeRefreshKey}`} />

      <section>
        <h2 className="mb-2 text-lg font-medium text-gray-900">AI knowledge assistant</h2>
        <TeamChat teamId={team.id} />
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium text-gray-900">Members</h2>
        {team.members.length === 0 ? (
          <p className="text-sm text-gray-500">No members yet.</p>
        ) : (
          <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
            {team.members.map((member) => (
              <li key={member.id} className="flex flex-col px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-medium text-gray-900">{member.name}</p>
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
          <h2 className="text-lg font-medium text-gray-900">Documents</h2>
          <label className="cursor-pointer rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
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
          <ul className="divide-y divide-gray-200 rounded-lg border border-gray-200 bg-white">
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="font-medium text-gray-900">{doc.filename}</p>
                  <p className="text-sm text-gray-500">
                    {doc.file_type.toUpperCase()} · {new Date(doc.created_at).toLocaleString()}
                  </p>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[doc.status]}`}>
                  {doc.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium text-gray-900">Topic explorer</h2>
        <TopicExplorer teamId={team.id} key={`topics-${knowledgeRefreshKey}`} />
      </section>

      <section>
        <h2 className="mb-2 text-lg font-medium text-gray-900">Dependency analyzer</h2>
        <p className="mb-3 text-sm text-gray-500">
          Topics where documented knowledge is concentrated around one person. This reflects team knowledge
          distribution, not the person.
        </p>
        <DependencyAnalyzer teamId={team.id} key={`dependency-${knowledgeRefreshKey}`} />
      </section>

      {isOwnerManager && (
        <section>
          <h2 className="mb-2 text-lg font-medium text-gray-900">Add a member</h2>
          <form onSubmit={handleAddMember} className="grid max-w-lg gap-3 rounded-lg border border-gray-200 bg-white p-4">
            <input
              placeholder="Name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
            <input
              type="email"
              placeholder="Email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
            <input
              type="password"
              placeholder="Temporary password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
            <input
              placeholder="Designation"
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
            <input
              placeholder="Phone number"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
            {addError && <p className="text-sm text-red-600">{addError}</p>}
            <button
              type="submit"
              disabled={adding}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {adding ? 'Adding…' : 'Add member'}
            </button>
          </form>
        </section>
      )}
    </div>
  )
}
