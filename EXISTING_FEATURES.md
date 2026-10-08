# Existing Features — Knowledge Retention Platform

A full inventory of what's actually built and working today. Every item below was either verified live
in-browser during the 2026-10-08 test pass (`TESTING_LOG.md`) or traced to a real file in the codebase
(`TECHNICAL_ARCHITECTURE.md` is the source for implementation details). Nothing here is aspirational —
see `IMPROVEMENTS_NEEDED.md` for what's *not* built yet.

---

## 1. Authentication & accounts

- **Manager self-registration** (`POST /auth/register`) — name, email, password (min 8 chars),
  optional designation and phone number. Only role that can self-register.
- **Login** (`POST /auth/login`) for both managers and members, returning a JWT.
- **Session restore on page load** (`GET /auth/me`) — reloading the app or returning later keeps you
  logged in via the stored token.
- **JWT-based sessions** — no server-side session store; a bearer token in `localStorage`, stamped onto
  every request by an axios interceptor. Tokens expire after 24h (configurable).
- **Password hashing** via bcrypt (passlib) — plaintext never stored, logged, or returned by any endpoint.
- **Two roles, one `users` table** — `manager` / `member` enum column, not separate tables.
- **Member accounts are created by managers**, not self-service — a manager picks a temporary password
  when adding a member; there's no member sign-up page by design.
- **Graceful auth failures:** wrong password shows a clear inline error, no crash; duplicate email on
  register or add-member shows a clear inline error, no crash.

## 2. Teams & membership

- **A manager can create multiple teams** (`POST /teams`), becoming each one's owner (`teams.manager_id`).
- **Team listing** scoped to "teams you manage or belong to" (`GET /teams`).
- **Adding members** to a team (`POST /teams/{id}/members`) — manager-only, sets name/email/temp
  password/designation/phone.
- **Membership model:** a member belongs to exactly one team (`users.team_id`); a manager owns teams via
  `teams.manager_id` and their own uploads count toward their team's stats too.
- **Access control:** every team/profile-scoped endpoint enforces "are you a member of this team, or the
  manager who owns it" server-side, not just hidden in the UI — verified directly via a cross-team access
  test (a team member navigating straight to another team's colleague's profile page gets a clean
  "you may not have access" message, not the data).

## 3. Document upload & processing

- **Supported formats:** PDF, DOCX, XLSX, CSV.
- **Upload endpoint** (`POST /teams/{id}/documents`) stores the raw file to disk (`backend/uploads/`,
  a Docker volume in the compose setup) under a random UUID filename, with the original filename kept in
  the database for display.
- **Text/data extraction per format:**
  - PDF → PyMuPDF, page-by-page text.
  - DOCX → python-docx, paragraphs + table cells.
  - XLSX → openpyxl, sheet names + row values.
  - CSV → the Python standard library's csv module.
- **Chunking:** extracted text is split into ~200-word chunks with 40-word overlap, each stored as its
  own `DocumentChunk` row — this is what both topic relevance and chat retrieval operate on, not the
  whole document at once.
- **Status lifecycle:** `processing → ready` (or `failed`, with an error message, if extraction throws).
  The frontend polls every 2.5s while any document is `processing`, so a finished upload appears without
  a manual page refresh.
- **Graceful failure on unsupported file types** (e.g. `.png`) — backend returns a 400, frontend shows a
  clear inline error, no crash, no wasted AI pipeline work.

## 4. AI topic extraction

- **Primary path:** the document's first 4000 characters are sent to the local Ollama LLM (`llama3.2` by
  default) with a prompt asking for up to 8 topic strings as a JSON array.
- **Fallback path:** if Ollama is unreachable or returns unparseable output, a regex-based heuristic finds
  capitalized word sequences (candidate proper nouns), filters stopwords, and ranks by frequency — so
  topic extraction never hard-fails even with no AI running.
- **Verified live with real AI:** uploading realistic technical documentation (Risk Engine architecture,
  Kubernetes deployment guide) produced sensible, specific topics — "Kubernetes," "AKS," "Helm," "Java,"
  "Docker," "PostgreSQL read replicas," etc. — not generic keyword noise.
- Each document↔topic link carries a **relevance score** that decays by rank (1st topic ~1.0, 8th ~0.6),
  stored on `DocumentTopic`.

## 5. Embeddings & semantic search

- **Local embedding model:** `sentence-transformers/all-MiniLM-L6-v2`, run in-process inside the backend
  (no network call, no API key) — converts text into a 384-dimension vector.
- **Storage:** vectors live directly in Postgres via the `pgvector` extension (`document_chunks.embedding`,
  `Vector(384)`) — no separate vector database.
- **Similarity search:** cosine-distance search (`embedding <=> query_vector`) runs as real SQL inside
  Postgres, not in Python — this is what powers the chatbot's retrieval step.

## 6. Documented knowledge evidence score

- **Formula** (per person per topic), explicitly simple and explainable rather than ML-based:
  `score = 0.4×relevance + 0.3×doc_count + 0.2×depth(chunk count) + 0.1×freshness`, clamped to 0–100.
- Recomputed automatically every time a user's document finishes processing.
- Only counts documents with `status == "ready"` — a still-processing or failed upload doesn't
  contribute yet.
- Framed throughout the product as **"documented knowledge evidence," never "skill" or "competence"** —
  this distinction is enforced in the copy on every screen that shows a score.

## 7. Topic Explorer

- **Search box** filters the team's topic list live as you type.
- **Click a topic** to see: every person with documented evidence on it (name, designation, percentage,
  progress bar) and every contributing document (filename).
- **Click a person's name** from the topic panel to jump to their Person Knowledge Dashboard.

## 8. Dependency Analyzer

- For each topic, computes each contributor's **share of total evidence** for that topic.
- Flags **HIGH** concentration (red) when one person holds ≥60% of the evidence, **DISTRIBUTED** (green)
  otherwise — pure arithmetic, no AI involved.
- Correctly shows HIGH/100% when a topic currently has only one contributor (expected behavior, not a
  bug, per the product spec) — verified live.

## 9. Team Dashboard

- **Stat strip:** Members / Documents / Topics / Active contributors, all live counts.
- **Knowledge coverage** bucketing: Well / Moderately / Weakly covered, based on how many distinct people
  have documented evidence per topic.
- **Recent activity feed** — who uploaded what, most recent first.

## 10. Person Knowledge Dashboard

- Reachable from a person's name anywhere in the app (Members list, Topic Explorer, Dependency Analyzer,
  Contribution Activity, Knowledge Graph side panel).
- Shows name, designation, email, phone, a per-topic "Documented knowledge" list with percentage +
  progress bar per topic, and summary stats (topics with evidence, contributing documents).
- Access-controlled: viewable by yourself, a teammate, or the manager who owns your team — anyone else
  gets a clean "could not load this profile" message instead of the data.

## 11. Knowledge Contribution Activity

- Ranked list (most documents first) of **documents uploaded**, **distinct topics touched**, and
  **last activity date** per person — explicitly framed as activity, not a performance ranking.
- Each name links to that person's Person page.

## 12. Interactive Knowledge Graph

- Three-column layout — **People** (indigo/red), **Topics** (amber), **Documents** (green) — connected by
  Person→Topic→Document edges, built from the same evidence/relevance data as everything else (no
  separate graph database).
- **Search box** highlights matching nodes at full opacity and fades everything else, so you can visually
  trace what one person or topic connects to.
- **Click any node** to open a side panel with its details; clicking a person node includes a
  "View profile →" link straight to their Person page.
- **Pan, zoom (+/− buttons and mouse wheel), fit-to-view, and a minimap** — built with `reactflow`.

## 13. AI Knowledge Assistant (RAG chatbot)

- Ask a free-text question about the team's documented knowledge; answered by:
  1. Embedding the question with the same model used for document chunks.
  2. Vector-searching the team's `ready` document chunks in Postgres for the 5 closest matches.
  3. Discarding anything below a similarity threshold (0.2) — if nothing survives, returns a canned
     "couldn't find enough documented information" response **without calling the LLM at all**.
  4. Sending the surviving chunks to Ollama with a strict "answer only from this context" prompt.
- **Verified live:** "How do we deploy the Risk Engine?" produced a genuinely grounded answer
  synthesized from two different people's uploaded documents.
- **Source citations:** every answer includes the filename + excerpt of each chunk it was built from.
- **Relevant contributors:** every answer lists the people who uploaded the source documents, with their
  designation, so the user knows who to actually go ask.
- **Refuses to invent facts:** a question unrelated to any uploaded content ("What is the capital of
  France?") correctly returns the "couldn't find enough documented information" response instead of a
  hallucinated answer — verified live.
- **Graceful AI-down fallback:** if Ollama is unreachable, falls back to printing the top 3 retrieved
  excerpts verbatim with a note that AI generation isn't available, rather than failing the request.

## 14. Frontend / design

- React 19 + TypeScript + Vite, Tailwind CSS v4, `react-router-dom` for routing, `zustand` for the single
  piece of global state (auth), `axios` for HTTP, `reactflow` for the graph.
- **Company internal-website visual style** (added 2026-09-20, branch `frontend-redesign-company-style`):
  bold black headings, uppercase gray field/section labels, thin 1px borders instead of shadows, a
  divided stat-strip, pill-shaped status/concentration badges, and a red (`#c8102e`) accent for primary
  actions — applied consistently via shared Tailwind component classes, not one-off inline styling.
- **Protected routing** — unauthenticated visits to any app page redirect to `/login`.
- **Live-ish updates without a page reload:** member counts, document status, and dashboard stats update
  in place after actions like adding a member or uploading a document.

## 15. Infra

- **Four-container Docker Compose stack:** `postgres` (pgvector/pg16), `ollama` (local LLM runtime),
  `backend` (FastAPI/Uvicorn), `frontend` (Vite dev server) — brought up with one command
  (`docker compose up -d --build`).
- **No paid APIs anywhere** — Ollama (`llama3.2`) for generation, `sentence-transformers` for embeddings,
  both running entirely on local/Docker compute.
- **Persisted data across restarts:** Postgres data, uploaded files, and the pulled Ollama model all
  survive `docker compose down` (not `down -v`) via named volumes.
- **Live code editing without rebuilds:** both `backend/` and `frontend/` are bind-mounted into their
  containers, with hot-reload for both (Uvicorn `--reload`, Vite HMR with polling enabled for Docker
  Desktop on Windows).

---

## What's deliberately *not* built (by design, not oversight)

Per the hackathon README's explicit scope: no microservices, no Kafka, no Kubernetes, no Redis cluster, no
Neo4j/dedicated graph database, no separate vector database, no streaming chat, no database migrations
(schema created via `create_all` on startup), no background job queue, no object storage (plain disk/volume
for uploaded files). See `TECHNICAL_ARCHITECTURE.md` §19 for the full list and reasoning, and
`IMPROVEMENTS_NEEDED.md` for which of these are worth revisiting.
