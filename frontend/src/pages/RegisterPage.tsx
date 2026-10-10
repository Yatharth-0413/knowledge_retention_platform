import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import sgLogo from '../assets/societe-generale-logo.png'
import { useAuthStore } from '../store/authStore'

export function RegisterPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [designation, setDesignation] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const registerManager = useAuthStore((s) => s.registerManager)
  const navigate = useNavigate()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await registerManager({
        name,
        email,
        password,
        designation: designation || undefined,
        phone_number: phoneNumber || undefined,
      })
      navigate('/')
    } catch {
      setError('Could not register. That email may already be in use.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="w-full max-w-sm knp-card p-8">
        <div className="mb-8 flex flex-col items-center gap-2">
          <img src={sgLogo} alt="Société Générale" className="h-10 w-auto" />
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Knowledge Retention Platform</span>
        </div>
        <h1 className="mb-1 text-2xl font-bold text-gray-900">Manager registration</h1>
        <p className="mb-6 text-sm text-gray-500">Team members are added by their manager after this step.</p>
        <form onSubmit={handleSubmit} className="space-y-4">
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
            <label className="knp-label">Password</label>
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
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={submitting} className="knp-btn-primary w-full">
            {submitting ? 'Creating account…' : 'Create manager account'}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-gray-500">
          Already have an account?{' '}
          <Link to="/login" className="knp-link">
            Log in
          </Link>
        </p>
      </div>
    </div>
  )
}
