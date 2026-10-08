# Technical Architecture — How the Knowledge Retention Platform Actually Works

This document explains, in detail, how data flows through this system end to end: where user
data lives, how files are stored, how the frontend and backend talk to each other, how the
database is structured, and how the AI (Ollama + sentence-transformers) actually works. It's
written against the code as it exists today — every claim below points at a real file.

For the *product* spec (what the platform is supposed to do), see
`Knowledge-Retention-Platform-Hackathon-README.md`. For *implementation status*, see
`PROGRESS.md`. This document is the *how it's built* reference.

---

## 1. The one-paragraph version

A React frontend talks to a FastAPI backend over plain JSON REST calls, authenticated with a
JWT bearer token. The backend stores structured data (users, teams, documents, topics, scores)
in Postgres, and stores the actual uploaded files as plain files on disk. When a document is
uploaded, the backend extracts its text, splits it into chunks, asks a locally-running LLM
(**Ollama**) to name the topics it covers, and computes a vector **embedding** for each chunk
using a local model (**sentence-transformers**) — that vector is stored directly in Postgres via
the **pgvector** extension. A simple formula turns "this person uploaded documents covering this
topic" into a 0–100 "documented knowledge evidence" score. The chatbot answers questions by
embedding the question, finding the most similar stored chunks (vector similarity search in
Postgres), and asking Ollama to write an answer grounded only in those chunks.

Nothing here calls a paid API. Ollama and sentence-transformers both run entirely on your own
machine (or your own Docker containers).

---

## 2. System architecture diagram

```
┌──────────────────────────┐         HTTP/JSON (axios)         ┌───────────────────────────────┐
│   Browser (React SPA)     │  ───────────────────────────────▶ │   FastAPI backend (Uvicorn)    │
│   localhost:5173          │  ◀─────────────────────────────── │   localhost:8000               │
│   frontend/src/**         │      Authorization: Bearer <JWT>   │   backend/app/**                │
└──────────────────────────┘                                    └───────┬───────────┬────────────┘
                                                                         │           │
                                          SQLAlchemy ORM (psycopg3)     │           │ httpx (plain HTTP)
                                                                         ▼           ▼
                                                        ┌────────────────────┐  ┌──────────────────────┐
                                                        │ PostgreSQL 16       │  │ Ollama (local LLM)     │
                                                        │ + pgvector ext.     │  │ localhost:11434         │
                                                        │ localhost:5432      │  │ model: llama3.2         │
                                                        │ (users, teams,      │  └──────────────────────┘
                                                        │  documents, topics, │
                                                        │  chunks+embeddings, │  ┌──────────────────────┐
                                                        │  evidence scores)   │  │ sentence-transformers  │
                                                        └──────────┬──────────┘  │ (in-process, no server)│
                                                                   │             │ all-MiniLM-L6-v2       │
                                                                   │             └──────────────────────┘
                                                                   ▼
                                                        ┌────────────────────┐
                                                        │ Local disk           │
                                                        │ backend/uploads/     │
                                                        │  <team_id>/<uuid>.ext│
                                                        │ (the actual files)   │
                                                        └────────────────────┘
```

Four moving parts, each its own Docker container in `docker-compose.yml`:

| Service | Image / build | Port | Purpose |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | All structured data + vector embeddings |
| `ollama` | `ollama/ollama` | 11434 | Local LLM runtime (topic extraction + chat answers) |
| `backend` | built from `backend/Dockerfile` (Python 3.11) | 8000 | FastAPI app — all business logic |
| `frontend` | built from `frontend/Dockerfile` (Node 20) | 5173 | Vite dev server serving the React app |

---

## 3. Repository layout

```
knowledge-retention-platform/
├── frontend/                    React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── api/                 One file per backend resource — thin axios wrappers
│       ├── components/          Reusable pieces (chat, graph legend, stat strips, etc.)
│       ├── pages/                One file per route (Login, Dashboard, Team, Person, Graph)
│       ├── store/authStore.ts    zustand store — the ONLY client-side auth/session state
│       └── routes/ProtectedRoute.tsx  redirects to /login if not authenticated
│
├── backend/
│   └── app/
│       ├── auth/                 register/login, JWT issuing & verification, password hashing
│       ├── users/                 user profile reads, "can I view this person's profile" rule
│       ├── teams/                 team CRUD, adding members, "am I allowed into this team" rule
│       ├── documents/             upload endpoint, text extraction, chunking
│       ├── knowledge/             topics, embeddings, Ollama client, scoring formula, topic API
│       ├── chat/                  the RAG chatbot endpoint
│       ├── graph/                 Person→Topic→Document graph endpoint
│       ├── analytics/             dashboard stats, dependency analysis, contribution activity
│       ├── config.py              all environment-driven settings (one Settings object)
│       ├── database.py            SQLAlchemy engine/session setup
│       ├── models.py              imports every ORM model once (see §6.2)
│       └── main.py                FastAPI app, CORS, router wiring, startup hook
│
├── database/init.sql              runs once when the postgres container is first created —
│                                    just `CREATE EXTENSION vector;`
├── docker-compose.yml             wires all four services together
└── .env.example                   every environment variable the stack reads
```

---

## 4. How the frontend and backend actually integrate

### 4.1 The HTTP layer

Every frontend API call goes through one shared axios instance:

`frontend/src/api/client.ts`
```ts
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('krp_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
```

That's the entire integration mechanism: a `VITE_API_BASE_URL` env var points the SPA at the
FastAPI server, and a request interceptor stamps every outgoing call with `Authorization: Bearer
<token>` if one is stored. There is no server-rendering, no GraphQL, no websockets — just REST
calls returning JSON, one `api/*.ts` file per backend resource (`auth.ts`, `teams.ts`,
`documents.ts`, `knowledge.ts`, `analytics.ts`, `chat.ts`, `graph.ts`, `users.ts`), each calling
`apiClient.get/post(...)` and typed against `api/types.ts`.

### 4.2 CORS

The backend explicitly allows the frontend's origin (`CORSMiddleware` in `backend/app/main.py`,
origins list from `settings.cors_origins`, default `["http://localhost:5173"]`). If you ever
serve the frontend from a different host/port, you must add it to `CORS_ORIGINS` in `.env` or
every request will be blocked by the browser.

### 4.3 Auth token lifecycle (the actual session mechanism)

There are **no server-side sessions and no cookies**. The "session" is entirely:
a JWT string, in `localStorage`, read by axios on every request.

1. `POST /auth/login` or `POST /auth/register` → backend returns `{ access_token: "<jwt>" }`.
2. Frontend (`frontend/src/store/authStore.ts`) writes it to `localStorage.setItem('krp_token', ...)`.
3. Every subsequent request carries it via the axios interceptor above.
4. On backend, `app.auth.dependencies.get_current_user` decodes the JWT (`jose.jwt.decode`,
   HS256, secret = `JWT_SECRET_KEY`), reads the `sub` claim as the user id, and loads that
   `User` row from Postgres. If the token is missing/invalid/expired → `401`.
5. On page load, `authStore.hydrate()` calls `GET /auth/me` with whatever token is in
   `localStorage` to restore the session; if that fails, the token is cleared and the user is
   bounced to `/login` by `ProtectedRoute`.
6. Tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default **1440 minutes = 24 hours**,
   `backend/app/config.py:9`). There is no refresh-token flow — after 24h you just log in again.

Passwords are hashed with **bcrypt** via `passlib` (`backend/app/auth/security.py`) — the plain
password is never stored, never logged, and never sent back by any endpoint.

---

## 5. Users — where "all user info" actually lives

Every user (manager or team member) is one row in the **`users`** table
(`backend/app/users/models.py`). There is exactly one table for both roles — a `role` enum column
(`manager` / `member`) distinguishes them, not separate tables.

| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `name` | string | |
| `email` | string, **unique** | login identifier |
| `password_hash` | string | bcrypt hash, never the plaintext |
| `designation` | string, nullable | e.g. "Senior Software Engineer" |
| `phone_number` | string, nullable | |
| `role` | enum: `manager` \| `member` | |
| `team_id` | FK → `teams.id`, nullable | **only set for members** — see below |
| `created_at` | timestamp | |

**Two ways a person relates to a team**, and this trips people up if you don't know it:
- A **member** belongs to exactly one team via `users.team_id`.
- A **manager** doesn't set `team_id` at all — instead they *own* teams via `teams.manager_id`
  (a manager can own several teams). So "who's on this team" is `team.members` (members whose
  `team_id` points here) **plus** `team.manager` (the owner) — see
  `backend/app/teams/access.py::team_user_ids`, which every knowledge/analytics endpoint uses so
  a manager's own uploads count toward their team's stats.

**How accounts get created** (`backend/app/auth/router.py`, `backend/app/teams/router.py`):
- Managers **self-register** via `POST /auth/register` (only role that can do this).
- Members are **added by their manager** via `POST /teams/{id}/members` — the manager picks a
  temporary password for them; there's no invite-email flow, no self-service signup for members.

**Who can see whose profile** (`backend/app/users/access.py::can_view_user_profile`): yourself,
anyone on the same team, or a manager who owns that person's team. Enforced on
`GET /users/{id}` and `GET /users/{id}/knowledge`.

---

## 6. The database, in full

### 6.1 What it is

**PostgreSQL 16** with the **pgvector** extension, run via the official `pgvector/pgvector:pg16`
Docker image (`docker-compose.yml`). pgvector adds a `vector` column type and similarity-search
operators directly inside Postgres — so embeddings live in the *same* database as everything
else, no separate vector database (Pinecone/Weaviate/etc.) needed. This is intentional per the
README's "no microservices, no separate vector database" hackathon constraint.

The only manual SQL that ever runs is `database/init.sql`:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
This fires once, automatically, the first time the `postgres` container initializes its data
volume (Postgres's own `docker-entrypoint-initdb.d` convention).

### 6.2 How tables get created — **no migrations are actually applied**

This is a hackathon shortcut worth knowing about explicitly:

- `backend/alembic/` exists (Alembic is installed, in `requirements.txt`) but
  `alembic/versions/` is **empty**.
- Instead, on every backend startup, `backend/app/main.py` runs:
  ```python
  @app.on_event("startup")
  def on_startup():
      Base.metadata.create_all(bind=engine)
  ```
  SQLAlchemy inspects every model class that's been imported and issues `CREATE TABLE IF NOT
  EXISTS` for each one. `backend/app/models.py` exists *purely* to import every model
  (`User`, `Team`, `Document`, `DocumentChunk`, `Topic`, `DocumentTopic`, `KnowledgeEvidence`)
  in one place so they're all registered before `create_all` runs.
- **Consequence:** this only *adds* missing tables. It will never alter an existing column, drop
  a column, or migrate data. If you change a model's schema, you need to drop the affected
  table (or the whole `postgres_data` volume) for the change to take effect — there's no `alembic
  upgrade head` step anywhere in the current flow.

### 6.3 The schema

```
users                          teams                        documents
─────                          ─────                        ─────────
id PK                          id PK                        id PK
name                           name                         team_id ──────► teams.id
email (unique)                 manager_id ──► users.id       uploaded_by_id ─► users.id
password_hash                  created_at                   filename
designation                                                  file_type (enum: pdf/docx/xlsx/csv)
phone_number                                                 file_path        (disk path, see §7)
role (enum: manager/member)                                  status (enum: processing/ready/failed)
team_id ──► teams.id (nullable)                              error_message
created_at                                                   created_at


document_chunks                topics                        document_topics
────────────────               ──────                        ───────────────
id PK                          id PK                          id PK
document_id ──► documents.id    name                           document_id ──► documents.id
chunk_index                    normalized_name (unique)         topic_id ──► topics.id
content (raw text)                                             relevance (0.0–1.0)
embedding vector(384) ◄── pgvector column                      UNIQUE(document_id, topic_id)


knowledge_evidence
──────────────────
id PK
user_id ──► users.id
topic_id ──► topics.id
score (0–100, float)            ◄── the "documented knowledge evidence" number
document_count
updated_at
UNIQUE(user_id, topic_id)
```

Full column-level detail is in `backend/app/users/models.py`, `teams/models.py`,
`documents/models.py`, `knowledge/models.py` — the diagram above is a faithful summary, not an
approximation.

**Why `document_chunks` and not just `documents` for embeddings?** A whole document is too big
and too topically mixed to embed as one vector and get useful similarity search. Each document
is split into ~200-word chunks (`backend/app/documents/chunking.py`) and **each chunk gets its
own embedding** — that's what the chatbot actually searches over (§9).

**`topics` vs `document_topics`**: `topics` is the deduplicated global list of topic names across
the whole platform (`normalized_name` is unique — "Kubernetes" and "kubernetes " both fold to the
same row). `document_topics` is the many-to-many join saying "this specific document mentions
this topic, with this relevance."

### 6.4 How the backend talks to Postgres

SQLAlchemy 2.0's typed ORM (`Mapped[...]`/`mapped_column`), synchronous engine, `psycopg` v3
driver. Connection string comes from `DATABASE_URL` (`backend/app/config.py`,
`backend/app/database.py`). Every request gets its own `Session` via FastAPI's dependency
injection (`Depends(get_db)`), opened and closed per-request — no long-lived global session, no
raw SQL anywhere in the app code (except that one `CREATE EXTENSION` line).

---

## 7. File storage — where the actual uploaded files go

This is separate from the database. The **database** stores metadata about a document (filename,
type, status, who uploaded it). The **file bytes themselves** are written straight to disk:

`backend/app/documents/router.py::upload_document`:
```python
team_dir = Path(settings.upload_dir) / str(team_id)      # backend/uploads/<team_id>/
team_dir.mkdir(parents=True, exist_ok=True)
stored_name = f"{uuid.uuid4().hex}.{extension}"           # random name, original extension kept
stored_path = team_dir / stored_name
stored_path.write_bytes(file_bytes)
```

So a file uploaded to team 7 ends up at `backend/uploads/7/9f3a1c...b2.pdf` — a random UUID
filename, **not** the original filename (the original filename is preserved only in the
`documents.filename` DB column, for display). `documents.file_path` in the database stores this
full disk path so the file can be located later (though nothing currently re-serves the raw file
back to the browser — the UI only ever shows extracted/derived data, never a raw file download).

In Docker, `docker-compose.yml` mounts a **named volume** `uploads_data:/app/uploads`, so files
survive container restarts/rebuilds but live inside Docker's storage, not a folder you'll
casually find in the repo when running via `docker compose up`. Running the backend directly
(not in Docker) writes to `backend/uploads/` on your actual filesystem, relative to wherever
`UPLOAD_DIR` resolves (default `"uploads"`, `backend/app/config.py:17`).

---

## 8. The document processing pipeline, end to end

This is what happens between clicking "Upload document" and seeing topics/evidence appear.

```
1. POST /teams/{id}/documents  (multipart file upload)
        │
2. Save raw bytes to disk (§7) + insert a `documents` row, status = "processing"
        │
3. extract_text(bytes, file_type)          [backend/app/documents/extraction.py]
        │   PDF  → PyMuPDF (pymupdf), page.get_text() per page
        │   DOCX → python-docx, paragraphs + table cells
        │   XLSX → openpyxl, sheet name + row values, read-only mode
        │   CSV  → stdlib csv module
        │   (not meant to be perfect — README explicitly says "perfect fidelity not required")
        │
4. chunk_text(text)                        [backend/app/documents/chunking.py]
        │   naive word-count split: 200-word chunks, 40-word overlap between consecutive chunks
        │   → one `DocumentChunk` row per chunk, status flips to "ready" here
        │
5. process_document_topics(db, document, text)   [backend/app/knowledge/service.py]
        │   → extract_topics(text)  — see §10 (Ollama, with heuristic fallback)
        │   → get-or-create a `Topic` row per name, link via `DocumentTopic` (with a
        │     relevance score that decays by rank: 1st topic ~1.0, 8th ~0.6)
        │   → recompute_evidence_for_document()  — see §11 (the scoring formula)
        │
6. embed_document_chunks(chunks)           [backend/app/knowledge/embeddings.py + service.py]
        │   → sentence-transformers encodes every chunk's text into a 384-dim vector
        │   → vector is written into DocumentChunk.embedding (pgvector column)
        │
7. Final `db.commit()` — everything above becomes visible to the frontend
```

If text extraction throws, the document is marked `status = "failed"` with `error_message` set,
and steps 4–6 are skipped. There is currently no retry mechanism — a failed document stays failed
until re-uploaded.

**Why `run_in_threadpool` wraps steps 3, 5, and 6** (`documents/router.py`): the upload route is
`async def`, but extraction/Ollama calls/embedding are all *synchronous, blocking* calls. Uvicorn
runs one event loop; without threadpool offloading, a slow upload would freeze every other
concurrent request (this was a real bug, found and fixed during the original build — see
`PROGRESS.md`'s "Known issues → Fixed" section for the story).

---

## 9. AI layer #1: what Ollama actually is, and how it's used here

**What Ollama is:** a small program that runs large language models **entirely on your own
computer** (or your own server) — no API key, no internet call, no per-token cost. You install
it, run `ollama pull <model>` once to download a model's weights, and then it exposes a local
HTTP API (default `http://localhost:11434`) that behaves similarly to a hosted LLM API, but the
actual inference happens on your CPU/GPU. In this project it runs as its own Docker container
(the `ollama` service, official `ollama/ollama` image) with model weights persisted in the
`ollama_data` volume.

**Which model:** `llama3.2` by default (`OLLAMA_MODEL` in `.env`, `backend/app/config.py:12`) — a
small (~2GB) general-purpose model from Meta, good enough to follow short extraction/answer
instructions without needing a GPU. Swappable to any model Ollama supports by changing that env
var and pulling it.

**Important operational detail:** Ollama ships with **zero models pulled by default**. Nothing in
this codebase pulls a model automatically. You must run, once per fresh Ollama data volume:
```
docker compose exec ollama ollama pull llama3.2
```
Without this, every call to Ollama silently fails (times out / connection works but responds
oddly) and the app **quietly degrades** to fallback behavior described below — this caught the
team out once already (see `PROGRESS.md`).

**How the backend talks to it:** one tiny wrapper, `backend/app/knowledge/ollama_client.py`:
```python
def ollama_generate(prompt: str, *, json_mode: bool = False) -> str | None:
    response = httpx.post(f"{OLLAMA_BASE_URL}/api/generate",
                           json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, ...})
    return response.json().get("response", "").strip() or None
    # any HTTP error → returns None, never raises
```
It's a plain HTTP POST to Ollama's `/api/generate` endpoint with `stream: false` (get the whole
answer back in one response, not a token stream) and `format: json` when the caller wants
strict-JSON output. **Every caller treats `None` as "AI unavailable" and has a non-AI fallback**
— this is a deliberate design choice so a demo never hard-crashes if Ollama isn't running.

Ollama is used in exactly two places:

### 9.1 Topic extraction (`backend/app/knowledge/topic_extraction.py`)
Sends the first 4000 characters of a document's extracted text with a prompt asking for a JSON
array of up to 8 topic strings. Parses the JSON response. **If Ollama is unreachable or returns
unparseable output**, falls back to `_extract_via_heuristic`: a regex that finds capitalized
word-sequences (candidate proper nouns / product names), filters common stopwords, and ranks by
frequency. This is why, without a running Ollama model, topics still get extracted — just cruder
ones ("Risk Engine" and "Kubernetes" get caught by capitalization; nuanced topics like "database
recovery process" would not).

### 9.2 The RAG chatbot's answer generation (`backend/app/chat/service.py`)
Covered fully in §12 below.

---

## 10. AI layer #2: embeddings (sentence-transformers) and how pgvector search works

**What "embedding" means here:** a piece of text (a document chunk, or a user's question) is
converted into a fixed-length list of 384 numbers (`backend/app/knowledge/models.py:10`,
`EMBEDDING_DIM = 384`) such that texts with similar *meaning* end up as numerically close
vectors, even if they don't share exact words. This is what lets the chatbot find "how do I
deploy the risk engine" as relevant to a chunk that says "the deployment pipeline for the risk
engine runs through AKS" — no shared keywords needed.

**The model:** `sentence-transformers/all-MiniLM-L6-v2` (`EMBEDDING_MODEL` in `.env`), a small,
well-known open-source embedding model. Unlike Ollama, this does **not** run as a network
service — `sentence-transformers` is a Python library, the model is downloaded once (cached under
the container's home directory) and loaded **in-process** inside the FastAPI backend itself
(`backend/app/knowledge/embeddings.py`, `@lru_cache` so it's loaded once per process, not once
per request).

```python
def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_model()                                   # loaded once, cached
    return model.encode(texts, normalize_embeddings=True).tolist()
```

**Where the vectors live:** directly in Postgres, in `document_chunks.embedding`, typed as
`Vector(384)` via the `pgvector` SQLAlchemy integration (`pgvector.sqlalchemy.Vector`). This
column is populated in step 6 of the pipeline in §8, right after chunks are created.

**How similarity search works:** pgvector adds vector distance operators straight into SQL.
The chatbot's retrieval step (`backend/app/chat/service.py::_retrieve`) does:
```python
distance = DocumentChunk.embedding.cosine_distance(query_vector)
db.query(DocumentChunk, Document, distance.label("distance"))
  .filter(Document.team_id == team_id, Document.status == "ready", DocumentChunk.embedding.isnot(None))
  .order_by(distance)
  .limit(5)
```
This is a real SQL `ORDER BY embedding <=> query_vector LIMIT 5` under the hood (pgvector's
cosine-distance operator) — the nearest-neighbor search happens **inside Postgres**, not in
Python. `similarity = 1 - distance`; anything below `MIN_SIMILARITY = 0.2` is treated as "not
actually relevant" and discarded, so a question with no real matching content correctly gets "I
couldn't find enough documented information" instead of a hallucinated answer built from
unrelated chunks.

---

## 11. The "documented knowledge evidence" score, exactly

`backend/app/knowledge/scoring.py::recompute_evidence` — recomputed for a `(user, topic)` pair
every time one of that user's documents finishes processing:

```
score = relevance_component  × 0.4      (weight: how central the topic is to their docs)
      + doc_count_component  × 0.3      (weight: how many separate documents cover it)
      + depth_component      × 0.2      (weight: how much text — chunk count — covers it)
      + freshness_component  × 0.1      (weight: how recently they last documented it)
```
- **relevance_component** = average `DocumentTopic.relevance` across that user's ready documents
  covering the topic (capped at 1.0), × 100.
- **doc_count_component** = `min(document_count, 5) / 5 × 100` — plateaus at 5 documents.
- **depth_component** = `min(total_chunk_count, 30) / 30 × 100` — plateaus at 30 chunks (~6,000
  words) of evidence.
- **freshness_component** = 100 if most recent qualifying document is ≤30 days old, 60 if ≤90
  days, else 30 (matches README §15's Fresh/Aging/Stale buckets exactly).

Result is clamped to `[0, 100]` and stored in `knowledge_evidence.score`. This is intentionally a
simple, explainable formula (README §6 explicitly asks for that) — not a machine-learned model.
It only counts **`status == "ready"`** documents, so a still-processing or failed upload doesn't
contribute yet.

This score feeds: the Topic Explorer's per-person bars, the Person page's evidence list, the
Dependency Analyzer's concentration calculation (§13), and the knowledge graph's person→topic
edge weights.

---

## 12. The RAG chatbot, end to end

"RAG" = Retrieval-Augmented Generation: instead of asking the LLM to answer from its own
training data (which would risk inventing facts about *your* company), you retrieve the actually
relevant text first and force the LLM to answer only from that.

`backend/app/chat/service.py::answer_question`, triggered by `POST /teams/{id}/chat`:

```
1. Embed the user's question (same sentence-transformers model as document chunks — this
   matters: query and documents must share an embedding space to be comparable).
2. Vector-search the team's document_chunks in Postgres for the 5 closest chunks
   (cosine similarity, §10), restricted to this team's READY documents only — one team can
   never retrieve another team's documents.
3. Drop any result below similarity 0.2 (§10). If nothing survives → return a canned
   "couldn't find enough documented information" response, no LLM call made at all.
4. Build a context block: "[filename]\n<chunk text>" for each surviving chunk, concatenated.
5. Send Ollama a strict prompt: "Answer using ONLY the context below... don't invent facts...
   2-4 sentences" (full prompt in the file) — this is what keeps answers grounded rather than
   free-form.
6. If Ollama responds → that's the answer, `grounded: true`.
   If Ollama is unreachable → fall back to literally printing the top 3 retrieved excerpts
   verbatim ("AI generation isn't available right now, but here's the most relevant documented
   evidence: ..."), `grounded: false`. The user still gets something useful, just not
   LLM-synthesized.
7. Response also includes: `sources` (filename + a 280-char excerpt per retrieved chunk, for
   citation — README §13's "every claim should link to its source") and `contributors`
   (the distinct people who uploaded the retrieved documents, with their designation, so the
   user knows who to actually go ask).
```

The frontend (`frontend/src/components/TeamChat.tsx`) just renders this response shape — it does
no retrieval or grounding logic itself; the backend does all of it in one request/response
round-trip (not streamed — `stream: false` on the Ollama call, and the HTTP response is one JSON
blob, so the UI shows a "Thinking…" state and then the full answer appears at once).

---

## 13. Knowledge graph & analytics — how the "smart" views are actually computed

These aren't separate systems — they're SQL queries over the same tables, re-shaped per view.

- **`GET /teams/{id}/graph`** (`backend/app/graph/router.py`): builds `Person→Topic→Document`
  nodes/edges directly from `KnowledgeEvidence` (person→topic edges, weight = score/100) and
  `DocumentTopic` (topic→document edges, weight = relevance). The frontend
  (`frontend/src/pages/GraphPage.tsx`) lays this out with `reactflow` in three columns and does
  all the visual layout client-side — the backend just returns typed nodes/edges, no graph
  database involved (per README §8's explicit "no dedicated graph database" constraint).

- **`GET /teams/{id}/dependency`** (dependency analyzer): for each topic, `share = person's
  evidence score / sum of all evidence scores for that topic`. If any one person's share ≥ 60%,
  that topic is flagged `HIGH` concentration, else `DISTRIBUTED`. Pure arithmetic over
  `KnowledgeEvidence`, no AI involved.

- **`GET /teams/{id}/dashboard`**: member/document/topic/active-contributor counts, plus a
  "coverage" bucketing (well/moderately/weakly covered = topics with ≥3 / exactly 2 / 0–1
  distinct contributing uploaders) and the 5 most recent document uploads. All `COUNT`/`GROUP BY`
  SQL, no AI.

- **`GET /teams/{id}/contributions`**: documents uploaded + distinct topics touched per person,
  sorted descending — README §16's "Knowledge Contribution Activity", deliberately framed as
  activity, not a performance ranking.

---

## 14. Full API reference

All routes are mounted with no global prefix except where noted; auth is `Authorization: Bearer
<jwt>` on every route except `/auth/register` and `/auth/login`.

| Method & path | Auth | Purpose |
|---|---|---|
| `POST /auth/register` | none | Self-register as a manager |
| `POST /auth/login` | none | Get a JWT |
| `GET /auth/me` | any user | Current user's profile (session restore) |
| `POST /teams` | manager | Create a team (caller becomes owner) |
| `GET /teams` | any user | List teams you manage or belong to |
| `GET /teams/{id}` | member or owning manager | Team detail incl. members |
| `POST /teams/{id}/members` | owning manager | Add a member with a temp password |
| `GET /teams/{id}/members` | member or owning manager | List members |
| `GET /users/{id}` | self/teammate/owning manager | A person's profile |
| `POST /teams/{id}/documents` | member or owning manager | Upload + process a document (§8) |
| `GET /teams/{id}/documents` | member or owning manager | List a team's documents |
| `GET /documents/{id}` | member or owning manager | One document's detail |
| `GET /teams/{id}/topics` | member or owning manager | Topic Explorer list |
| `GET /teams/{id}/topics/{topic_id}` | member or owning manager | People + documents for one topic |
| `GET /users/{id}/knowledge` | self/teammate/owning manager | A person's per-topic evidence |
| `GET /teams/{id}/graph` | member or owning manager | Person→Topic→Document graph (§13) |
| `GET /teams/{id}/dashboard` | member or owning manager | Team stats + coverage + recent activity |
| `GET /teams/{id}/dependency` | member or owning manager | Concentration analysis (§13) |
| `GET /teams/{id}/contributions` | member or owning manager | Contribution activity (§13) |
| `POST /teams/{id}/chat` | member or owning manager | Ask the RAG chatbot a question (§12) |
| `GET /health` | none | Liveness check |

Interactive Swagger docs are auto-generated by FastAPI at `http://localhost:8000/docs` whenever
the backend is running.

---

## 15. Frontend architecture

- **Stack:** React 19 + TypeScript, Vite 8 dev server/bundler, Tailwind CSS v4 (CSS-based config,
  no `tailwind.config.js` — tokens/utilities defined via `@theme`/`@layer` directly in
  `frontend/src/index.css`), `react-router-dom` v7 for routing, `zustand` for the one piece of
  global client state (auth), `axios` for HTTP, `reactflow` for the knowledge graph,
  `recharts` (installed, available for future chart needs).
- **Routing** (`frontend/src/App.tsx`): `/login`, `/register` are public;
  `/`, `/teams/:teamId`, `/teams/:teamId/graph`, `/people/:userId` are wrapped in
  `ProtectedRoute` (redirects to `/login` if `authStore` has no valid session) and `Layout`
  (shared header/footer chrome).
- **State management:** deliberately minimal. `authStore` (zustand) holds the token/current user
  and is the single source of truth for "am I logged in." Every other piece of data (teams,
  documents, topics, dashboard stats, etc.) is fetched with plain `useState` + `useEffect` inside
  the page/component that needs it — there's no global cache (no React Query/SWR), so navigating
  back to a page re-fetches. This is a deliberate hackathon-scope simplification, not an
  oversight.
- **Live-ish updates:** `TeamPage.tsx` polls `GET /teams/{id}/documents` every 2.5s *only* while
  at least one document is still `status == "processing"`, so topic extraction/embedding
  finishing shows up without a manual refresh (see `PROGRESS.md`'s "Fixed" notes for why this was
  added).

---

## 16. Docker Compose & running it locally

`docker-compose.yml` defines the four services from §2. Dependency order:
`backend` waits for `postgres` to be *healthy* (via `pg_isready`) and for `ollama` to have
*started* (not necessarily have a model pulled — that's still a manual step, §9); `frontend`
waits for `backend` to have started.

Key volumes:
- `postgres_data` — the actual database files, persists across `docker compose down` (but not
  `down -v`).
- `ollama_data` — downloaded model weights; **this is why you only need to `ollama pull` once**,
  not on every restart, as long as you don't run `-v`.
- `uploads_data` — uploaded files (§7).
- Both `backend/` and `frontend/` source directories are also bind-mounted into their containers
  for live code editing without rebuilding the image (`--reload` for Uvicorn, Vite's dev server
  with hot-module-reload — note `usePolling: true` was added to `vite.config.ts` because Docker
  Desktop on Windows doesn't propagate filesystem events for bind mounts by default).

To bring the whole stack up: `docker compose up -d --build`, then (once, per fresh
`ollama_data` volume) `docker compose exec ollama ollama pull llama3.2`.

---

## 17. Environment variables (`.env`, from `.env.example`)

| Variable | Consumed by | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | backend | `postgresql+psycopg://postgres:postgres@postgres:5432/knowledge_retention` | psycopg v3 driver |
| `JWT_SECRET_KEY` | backend | `dev-secret-change-me` | **change for anything beyond local demo** |
| `JWT_ALGORITHM` | backend | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | backend | `1440` (24h) | |
| `OLLAMA_BASE_URL` | backend | `http://ollama:11434` (`http://localhost:11434` outside Docker) | |
| `OLLAMA_MODEL` | backend | `llama3.2` | must be pulled manually, §9 |
| `EMBEDDING_MODEL` | backend | `sentence-transformers/all-MiniLM-L6-v2` | downloaded automatically on first use |
| `POSTGRES_USER` / `PASSWORD` / `DB` | postgres container init only | `postgres` / `postgres` / `knowledge_retention` | |
| `VITE_API_BASE_URL` | frontend (build/dev time) | `http://localhost:8000` | baked in at build time, not runtime-configurable after `vite build` |

`UPLOAD_DIR` (backend, default `"uploads"`) and `CORS_ORIGINS` (backend, default
`["http://localhost:5173"]`) exist as `Settings` fields too but aren't in `.env.example` — set
them the same way if you need to override.

---

## 18. Security notes (as currently implemented — hackathon scope, not hardened)

- Passwords: bcrypt via passlib. Good.
- JWT: HS256 with a single shared secret; **the default secret in code must be overridden** via
  `JWT_SECRET_KEY` before this ever leaves a local demo.
- No refresh tokens, no token revocation/blacklist — a leaked token is valid until it expires
  (24h) or the secret is rotated.
- No rate limiting anywhere (login, chat, upload).
- File uploads aren't scanned/sandboxed — extraction libraries (PyMuPDF, python-docx, openpyxl)
  run directly against untrusted file bytes.
- Team/profile access is enforced in Python at the router layer (`require_team_access`,
  `can_view_user_profile`) on every read — there's no row-level security at the Postgres level,
  so a bug in one of those check functions is the only thing standing between teams' data.

---

## 19. Known hackathon-scope simplifications (by design, not bugs)

- No database migrations — schema changes require dropping tables/volumes (§6.2).
- No object storage (S3-style) — uploaded files are plain files on a Docker volume/local disk (§7).
- No background job queue — document processing runs inline in the upload request (offloaded to
  a threadpool, not a separate worker process), so a very large document upload will still hold
  that HTTP request open until processing finishes.
- No streaming chat responses — the whole answer is generated by Ollama before anything is sent
  to the browser.
- No automatic Ollama model pulling — a fresh environment needs one manual `ollama pull` (§9).
- No client-side data cache/refetch strategy — every page fetches fresh on mount.

None of these block the hackathon demo (README §24) — they're the specific places to look first
if this were to grow beyond that scope.
