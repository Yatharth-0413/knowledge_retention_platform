import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/')
    } catch {
      setError('Invalid email or password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="w-full max-w-sm knp-card p-8">
        <div className="mb-6 flex items-center gap-2.5">
          <span className="h-6 w-6 rounded-sm bg-[var(--color-brand)]" />
          <span className="text-sm font-bold tracking-tight text-gray-900">Knowledge Retention Platform</span>
        </div>
        <h1 className="mb-1 text-2xl font-bold text-gray-900">Log in</h1>
        <p className="mb-6 text-sm text-gray-500">Team Workspace</p>
        <form onSubmit={handleSubmit} className="space-y-4">
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="knp-input"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={submitting} className="knp-btn-primary w-full">
            {submitting ? 'Logging in…' : 'Log in'}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-gray-500">
          Manager without an account?{' '}
          <Link to="/register" className="knp-link">
            Register
          </Link>
        </p>
      </div>
    </div>
  )
}
