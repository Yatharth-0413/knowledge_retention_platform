import { type FormEvent, useState } from 'react'
import { askQuestion } from '../api/chat'
import type { ChatResponse } from '../api/types'

interface Exchange {
  question: string
  response: ChatResponse | null
  error: boolean
}

export function TeamChat({ teamId }: { teamId: number }) {
  const [question, setQuestion] = useState('')
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [asking, setAsking] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || asking) return
    setQuestion('')
    setAsking(true)
    setExchanges((prev) => [...prev, { question: q, response: null, error: false }])
    try {
      const response = await askQuestion(teamId, q)
      setExchanges((prev) => prev.map((ex, i) => (i === prev.length - 1 ? { ...ex, response } : ex)))
    } catch {
      setExchanges((prev) => prev.map((ex, i) => (i === prev.length - 1 ? { ...ex, error: true } : ex)))
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="space-y-4">
      {exchanges.length === 0 ? (
        <p className="text-sm text-gray-500">
          Ask a question about your team's documented knowledge, e.g. "How do we deploy the Risk Engine?"
        </p>
      ) : (
        <ul className="space-y-4">
          {exchanges.map((ex, i) => (
            <li key={i} className="knp-card p-4">
              <p className="font-medium text-gray-900">{ex.question}</p>
              {ex.error ? (
                <p className="mt-2 text-sm text-red-600">Something went wrong. Try again.</p>
              ) : !ex.response ? (
                <p className="mt-2 text-sm text-gray-500">Thinking…</p>
              ) : (
                <div className="mt-2 space-y-3">
                  <p className="whitespace-pre-wrap text-sm text-gray-700">{ex.response.answer}</p>
                  {!ex.response.grounded && ex.response.sources.length === 0 && (
                    <p className="text-xs text-amber-700">No documented evidence found for this question.</p>
                  )}
                  {ex.response.sources.length > 0 && (
                    <div>
                      <p className="knp-section-title mb-1">Sources</p>
                      <ul className="space-y-1 text-xs text-gray-600">
                        {ex.response.sources.map((s, si) => (
                          <li key={si}>
                            <span className="font-medium text-gray-800">{s.filename}</span> — {s.excerpt}
                            {s.excerpt.length >= 280 ? '…' : ''}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {ex.response.contributors.length > 0 && (
                    <div>
                      <p className="knp-section-title mb-1">Relevant contributors</p>
                      <ul className="text-xs text-gray-600">
                        {ex.response.contributors.map((c) => (
                          <li key={c.user_id}>
                            {c.name}
                            {c.designation ? ` — ${c.designation}` : ''}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your team's documented knowledge…"
          className="knp-input flex-1"
        />
        <button type="submit" disabled={asking} className="knp-btn-primary">
          {asking ? 'Asking…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}
