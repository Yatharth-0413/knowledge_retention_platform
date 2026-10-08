# Improvements Needed — Knowledge Retention Platform

What's left to make this a genuinely efficient, robust platform, beyond the hackathon MVP. Compiled
from a full manual test pass (`TESTING_LOG.md`, 2026-10-08) plus a review of `TECHNICAL_ARCHITECTURE.md`
§18–19 (security notes and known hackathon-scope simplifications). Nothing here blocks the hackathon
demo — the MVP works end to end — this is the "what's next" list.

Grouped by what it actually affects, roughly in priority order within each group.

---

## 1. Performance / latency

### 1.1 Ollama calls have no max-token cap — found 2026-10-08
`backend/app/knowledge/ollama_client.py::ollama_generate()` calls `/api/generate` with `format: "json"`
but no `options.num_predict` and no stop sequence. `format: json` only constrains output to be
*syntactically valid* JSON — it doesn't cap length. Observed during testing: a topic-extraction call that
should need under 100 tokens ran to 500+ tokens and took ~23–40s on CPU-only `llama3.2` (~7 tokens/s).
Affects both topic extraction (`topic_extraction.py`) and the RAG chatbot's answer generation
(`chat/service.py`), making every upload and every chat question 15–90s instead of the "a few seconds"
the demo script promises.
**Fix:** add `"options": {"num_predict": 120}` (topic extraction) and a sensible cap for chat (e.g. 300)
to the `ollama_generate()` payload.

### 1.2 Embedding model cache isn't persisted — found 2026-10-08
`sentence-transformers` downloads `all-MiniLM-L6-v2` from the HuggingFace Hub on first use and caches it
under the container's home directory. `docker-compose.yml` has no volume for that cache (only
`postgres_data`, `ollama_data`, `uploads_data` are persisted) — unlike the Ollama model, which *is*
cached and only needs pulling once ever. Every backend container rebuild re-downloads the embedding
model, and the very first upload after a rebuild silently eats that cost with the upload button just
saying "Uploading…" for up to a few minutes.
**Fix:** mount a named volume (e.g. `huggingface_cache:/root/.cache/huggingface`) in
`docker-compose.yml`, and/or warm the embedding model on backend startup the way Ollama is warmed.

### 1.3 Document processing runs inline in the upload request
No background job queue — `extract_text`, `process_document_topics`, and `embed_document_chunks` all run
inside the `POST /teams/{id}/documents` request (offloaded to a threadpool, but still holding the HTTP
connection open). A large document, or several of the above being slow (see 1.1/1.2), means the upload
request itself can take minutes. Acceptable for a hackathon demo with small files; won't scale to larger
documents or concurrent uploads.
**Fix:** move processing to a background worker (even a simple in-process queue) and have the frontend
poll for status, the way it already polls for `processing → ready` — the plumbing for polling already
exists, it's just the "upload returns immediately" half that's missing.

### 1.4 No streaming chat responses
Ollama is called with `stream: false`, so the full answer is generated before anything reaches the
browser — the user sees "Thinking…" then the entire answer appears at once. Combined with 1.1, this
makes a 15–90s question feel like a hang rather than visible progress.
**Fix:** switch to `stream: true` and forward tokens to the frontend as they arrive (SSE or chunked
response); lower priority than 1.1/1.2 which address the actual root cause of the slowness.

### 1.5 No client-side data cache
Every page fetches fresh on mount (no React Query/SWR) — navigating back to a page re-fetches
everything. A deliberate hackathon simplification per `TECHNICAL_ARCHITECTURE.md` §15, but worth
revisiting if the team/document counts grow.

---

## 2. Reliability / correctness

### 2.1 No retry mechanism for failed document processing
If text extraction throws, the document is marked `status = "failed"` and stays that way until
re-uploaded from scratch — no retry button, no automatic retry.
**Fix:** add a "Retry" action on failed documents that re-runs steps 3–6 of the pipeline without
requiring a fresh upload.

### 2.2 No database migrations
`backend/alembic/versions/` is empty; schema changes are applied via `Base.metadata.create_all()` on
startup, which only *adds* missing tables — it never alters or drops a column. Any schema change
currently requires dropping the affected table or the whole `postgres_data` volume, which means losing
all data. Fine for a hackathon, risky the moment there's real demo data worth keeping.
**Fix:** start writing real Alembic migrations before the next schema change.

### 2.3 Silent fallback with no user-visible indicator
When Ollama is unreachable or times out (90s), topic extraction silently falls back to a keyword
heuristic and chat falls back to printing raw excerpts — both deliberate, documented fallbacks, but
nothing in the UI tells the user "this answer wasn't AI-generated." A demo could show a "fallback"
badge/tooltip without much effort, since the backend already knows (`grounded: false` is already
returned by the chat endpoint but isn't rendered differently in `TeamChat.tsx`).

---

## 3. Security (needed before anything beyond a local demo)

- **JWT secret:** `JWT_SECRET_KEY` defaults to `dev-secret-change-me` in code — must be overridden via
  `.env` before this is shown to anyone outside a local demo.
- **No refresh tokens / revocation:** a leaked token is valid for the full 24h expiry with no way to
  invalidate it early.
- **No rate limiting:** login, chat, and upload endpoints have no throttling — trivially brute-forceable
  or abusable.
- **Uploaded files aren't scanned:** PyMuPDF/python-docx/openpyxl run directly against untrusted bytes
  with no sandboxing.
- **No row-level security:** team/profile access is enforced only in Python (`require_team_access`,
  `can_view_user_profile`) — a bug in either function is the only thing standing between teams' data,
  with no database-level backstop.

None of these are hackathon blockers; all of them matter the moment this handles real company data.

---

## 4. Infra / DevOps

- **Backend image bloat (fixed 2026-10-08, uncommitted):** `requirements.txt` has `sentence-transformers`
  unpinned, which pulled a `torch` version that defaults to the full NVIDIA CUDA wheel set on Linux,
  ballooning the image to 10.4GB and adding minutes to every clean build for GPU libraries this CPU-only
  container never uses. Fixed in `backend/Dockerfile` by installing a CPU-only torch wheel first. Needs
  a commit.
- **No health checks** on `backend`, `frontend`, or `ollama` in `docker-compose.yml` — only `postgres`
  has one. `depends_on: condition: service_started` for `ollama` means the backend can start before
  Ollama is actually ready to serve requests.
- **Ollama model isn't pulled automatically:** a fresh `ollama_data` volume needs a manual
  `ollama pull llama3.2` or the app silently degrades (documented in `PROGRESS.md`, but still a trap for
  a new environment).

---

## 5. UX polish

- **No "this may take a while" messaging on upload:** the button just says "Uploading…" indefinitely —
  no indication whether it's seconds or minutes away (compounds 1.1/1.2 above).
- **No way to view or download the original uploaded file** — the UI only ever shows extracted/derived
  data (`TECHNICAL_ARCHITECTURE.md` §7 confirms nothing re-serves the raw file).
- **No topic edit/verify UI:** the README (§5) describes "the uploader can verify/edit detected topics,"
  but no such UI exists — topics are purely AI/heuristic-extracted with no human-in-the-loop correction.
- **No document deletion.**

---

## 6. Optional / bonus features (README §17 — not started)

These were explicitly scoped as "only after MVP is fully done," and the MVP is done, so these are the
natural next build targets:

1. **Knowledge Gap indicator** — flag topics with very few documented contributors.
2. **Duplicate document detection** — similarity check against existing uploads.
3. **Knowledge Conflict detection** — flag contradictory documented facts across documents (e.g. "Java 17"
   vs "Java 21").
4. **Knowledge Handoff suggestion** — when a topic is HIGH concentration, suggest creating
   knowledge-transfer documentation.

---

## Suggested order of attack

If picking this up next, the highest-leverage fixes for "feels fast and solid in a live demo" are, in
order: **1.1 (token cap) → 1.2 (HF cache volume) → 2.3 (fallback indicator) → 5 (upload messaging)**. Those
four are small, isolated changes that directly fix what testers will actually notice. Everything in
§3 (security) matters before any real/external use, not before a demo.
