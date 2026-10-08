# Progress — Knowledge Retention Platform

Tracks implementation status against `Knowledge-Retention-Platform-Hackathon-README.md` (section 18, MVP checklist). Updated after every completed task so a new session can resume without re-reading the whole codebase.

Last updated: 2026-10-08 (Knowledge Recommendation System added)

## How this file is used
- One task worked at a time, in the "Next up" order below.
- After each task is finished (code + manually verified working), move it from "Next up" to "Done" with a one-line note, and update "Currently in progress".
- "Done" items are assumed working; if something regresses, note it under Known issues instead of silently rewriting history.
- **Start here.** A fresh session should read this file first, then `README.md` (repo root) for the full doc map. Don't re-derive project state from scratch — it's all below.

## Currently in progress
Nothing. The Knowledge Recommendation System (branch `feature/recoomendation_model`) is complete and
verified live in-browser — see "Knowledge Recommendation System" below. MVP, the Outlook email-ingestion
feature, and the 4-phase post-MVP bug-fix pass (triggered by `My_analysis_on_project.md`) were already
complete and verified on `frontend-redesign-company-style` before this branch started.
One housekeeping item is still open: **the latest commit on `frontend-redesign-company-style` (`ed1938d`)
has not been pushed to `origin/frontend-redesign-company-style` yet** — the sandboxed environment's
auto-mode classifier blocks `git push` even on explicit user request; run it manually:
`git push origin frontend-redesign-company-style`. The work below is also uncommitted as of this update.

## Test suite added (2026-10-08)

First automated tests in this repo — previously everything was verified by manual in-browser testing
only (still the right call for UI/UX work, but the core attribution/scoring/leak-fix logic from the
post-MVP pass below now has regression coverage too).

- **Backend** (`backend/tests/`, pytest): `requirements-dev.txt` (pytest, pytest-cov, freezegun),
  `pytest.ini`. `tests/unit/` — 9 files, 79 tests, no DB/Docker dependency (pure functions + mocked
  `Session`/`monkeypatch`'d Ollama/embeddings): `test_security.py`, `test_teams_access.py`,
  `test_users_access.py`, `test_person_attribution.py`, `test_extraction_rows.py`,
  `test_topic_extraction.py`, `test_scoring.py`, `test_knowledge_service_dedup.py`,
  `test_chat_matching.py`. `tests/integration/` — 2 files, 6 tests, against a real disposable
  `knowledge_retention_test` Postgres/pgvector database (own `tests/integration/conftest.py`, separate
  from the dev DB) with a real FastAPI `TestClient`, Ollama/embeddings monkeypatched out for speed:
  `test_person_attribution_pipeline.py` (uploads a roster CSV through the real API, asserts the P0 fix —
  knowledge credited to the named person, not the uploader, and the chat endpoint answers "What does
  `<name>` know?" correctly for *both* people) and `test_cross_team_isolation.py` (a manager managing two
  teams — asserts Team B's dashboard/topics/contributions never leak Team A's evidence, the exact bug
  class found and fixed in Phase 1 below). Run with:
  `docker compose exec backend pip install -r requirements-dev.txt` once, then
  `docker compose exec backend pytest` (both suites) or `pytest tests/unit` / `pytest tests/integration`
  separately. All 85 tests pass, confirmed stable across repeated runs.
- **Frontend** (`frontend/`, vitest): `vitest.config.ts` — **deliberately a separate file from
  `vite.config.ts`**, not merged in. Vitest pins its own nested copy of Vite; merging `test:` into
  `vite.config.ts` and importing `defineConfig` from `vitest/config` there broke `tsc -b` with a
  plugin-type mismatch between that nested copy and the top-level `vite` used by
  `@vitejs/plugin-react`/`@tailwindcss/vite`. Keeping them separate (Vitest auto-resolves
  `vitest.config.ts` over `vite.config.ts`) avoids it entirely — if a future change ever needs to touch
  `vite.config.ts`, don't re-merge the two without re-testing `npm run build`. One new test file,
  `src/pages/GraphPage.test.ts` (4 tests), covering `computeFocusSet` (now exported) — the Phase 2
  click-to-focus cascade logic, asserting the person-focus-doesn't-pull-in-other-contributors behavior
  specifically. Run with `npm install` once, then `npm run test`.
- **Found and fixed one real (if minor) bug while writing these tests**: `app/auth/security.py::
  verify_password` raised `passlib.exc.UnknownHashError` (an unhandled 500) instead of returning `False`
  when given a `password_hash` that isn't a parseable hash at all (e.g. corrupted DB data) — fixed to
  fail closed. Caught by `test_security.py::test_verify_password_rejects_garbage_hash`, not by guessing.
- **Not covered yet** (acknowledged gap, not silently skipped): the `recommendations/classification.py`
  module from the Knowledge Recommendation System above is explicitly called out in its own section as
  "two pure, independently-testable functions" — good unit-test candidates, just not written in this
  pass. Document upload pipeline edge cases (malformed files, email parsing) and the analytics router's
  remaining endpoints (`/dependency`) also have no dedicated tests yet.

## Knowledge Recommendation System (2026-10-08, branch `feature/recoomendation_model`)

New feature, not part of the original hackathon spec — requested directly by the user: classify
documented knowledge as **Functional** (business/process — Business Analyst, Consultant, Manager, Agile/
Scrum roles) vs **Technical** (DevOps/Software/QA/Architect engineering roles), derived from each person's
free-text `designation`, then per team topic show who in the *same* role category still has **no**
documented evidence on it — a knowledge-gap recommender, surfaced as a new inline "Knowledge
recommendations" section on the Team page (confirmed with the user — not a modal; the app has no modal
precedent anywhere).

- **Backend:** new top-level package `backend/app/recommendations/` — `classification.py` (two pure,
  independently-testable functions: `classify_designation` does tier-1 phrase / tier-2 keyword matching
  with a deterministic "functional wins" tie-break for ambiguous titles like "Engineering Manager";
  `classify_topic_category` does majority-vote-with-tie-as-"mixed" over a topic's evidence contributors),
  `schemas.py`, and `router.py` exposing `GET /teams/{team_id}/recommendations` in exactly 3 DB queries
  (no N+1), reusing this codebase's established cross-team-leak-safe pattern (`DocumentTopic`/
  `Document.team_id` scoping — `KnowledgeEvidence` has no `team_id` of its own, same trap documented in
  Phase 1 below). No schema/migration change — classification is computed at request time from the
  existing `User.designation` field.
- **Frontend:** `KnowledgeRecommendations.tsx` (structurally mirrors `DependencyAnalyzer.tsx` — per-topic
  cards with a category badge, existing-contributors bar, and a "Knowledge gap" link row to each
  candidate's Person page) + `RecommendationsCharts.tsx` (one new recharts bar chart, reusing
  `AnalyticsCharts.tsx`'s `ChartCard`/brand colors), wired into `TeamPage.tsx` right after Contribution
  Activity, visible to the whole team (not manager-only), using the page's existing
  `knowledgeRefreshKey`-as-remount-key pattern.
- **Verified live in Chrome** (full test matrix + edge cases in `Test_logging_v3.md`): functional vs
  technical classification and gap candidates both correct against the user's own described scenario (a
  Business Analyst's CCR/risk upload vs a DevOps engineer's Java/deployment upload); the "Engineering
  Manager" ambiguous-title tie-break resolves to functional as designed; an unclassifiable designation
  ("Intern") never appears in any gap list; a topic with both functional and technical contributors
  correctly shows as "Mixed" with a gap pool spanning both categories; cross-team isolation verified
  bidirectionally with a colliding topic name on a second team (no leakage either direction); `npm run
  build` (tsc + vite) clean; no console/network errors; no regressions in any existing feature.

## Post-MVP bug-fix & analytics pass (2026-10-08, branch `frontend-redesign-company-style`)

Triggered by the user's own manual test pass, documented in `My_analysis_on_project.md` (bugs,
irregularities, and feature requests found by testing the live app after the email-ingestion merge).
Executed as a 4-phase plan (saved at the time to `C:\Users\Pavilion\.claude\plans\eager-munching-sunbeam.md`),
each phase verified live in-browser against real team data before moving to the next.

### Phase 1 — P0 critical bugs
- **Root cause found & fixed:** a document's extracted topics were always credited to whoever *uploaded*
  it, never to a person *named inside* it (e.g. a roster spreadsheet with one row per team member). This
  made "What does Shivam know?" fail while "What does Sriram know?" worked from the exact same file,
  purely by embedding-similarity luck in RAG retrieval — not a real per-person attribution mechanism.
- Fix: new `backend/app/knowledge/person_attribution.py` matches XLSX/CSV rows against the team's actual
  roster (name/email, case-insensitive, no hardcoded names) and a new nullable
  `document_topics.subject_user_id` column credits each row's topics to the matched person instead of the
  uploader. `knowledge/scoring.py::recompute_evidence` unions subject-attributed + legacy uploader-fallback
  evidence. `chat/service.py` got entity-aware retrieval: when a question names a team member (or says
  "I"/"my"), their `KnowledgeEvidence` is pulled directly and blended into the RAG context so the answer
  no longer depends on embedding-similarity luck.
- Also fixed in this phase: synthetic `# Sheet:` header leaking into Excel topics (same bug class as the
  earlier email `Subject:`/`From:` leak), a few-shot prompt + stoplist to stop the heuristic fallback from
  extracting verbs like "occurs" as topics, Ollama JSON-parsing robustness (dict-shaped `{"Topic": null}`
  responses, truncated multi-key objects from the `num_predict` cutoff, bounded retry), and topic
  deduplication via embedding cosine-similarity (new `topics.embedding` column, threshold 0.82) so
  "Deployment"/"Deployment Approval"/"DevOps Deployment" merge into one topic instead of tripling.
- **Unplanned but fixed (found via our own testing, not user-reported):** two pre-existing cross-team data
  leaks. `KnowledgeEvidence` has no `team_id` of its own; several queries in `analytics/router.py`
  (dashboard coverage, active-contributor count, contribution activity) and `knowledge/router.py`
  (`list_team_topics`, `get_team_topic`) filtered only by team-roster membership, which leaked a manager's
  evidence from *every* team they manage into each one individually. Fixed by scoping all of these through
  `DocumentTopic`/`Document.team_id` instead of a bare `KnowledgeEvidence.user_id IN roster` filter.

### Phase 2 — Knowledge Graph focus mode (`frontend/src/pages/GraphPage.tsx`)
Click a node to focus on it: a type-aware cascade (`computeFocusSet`) dims everything except a
person's topics and those topics' documents (or the reverse for a document), reusing the graph's
existing opacity/`transition-opacity` dimming mechanism — no new animation library. Added a
People/Topics/Documents visibility toggle via clickable legend dots, kept mutually exclusive with the
existing search-to-highlight behavior.

### Phase 3 — Analytics dashboard
- New `knowledge_evidence.freshness_label` column (`New`/`Medium`/`Old`, computed in
  `scoring.py::recompute_evidence`) — kept deliberately separate from the existing 0-100 `score` so
  "how much documented knowledge" and "how recently it was updated" are never conflated in the UI.
- `GET /teams/{id}/dashboard` extended with `knowledge_by_member`, `knowledge_by_topic`,
  `freshness_breakdown`, `documents_by_type` — all scoped through the same team-topic/roster pattern used
  to fix the Phase 1 leaks. Rendered as 4 new `recharts` charts (`frontend/src/components/AnalyticsCharts.tsx`)
  inside `TeamDashboardStats.tsx`, reusing its single existing `/dashboard` fetch (no new network calls).
- New `GET /users/{id}/documents` endpoint — needed because a **manager's** own `User.team_id` is `NULL`
  (managers relate to a team via `Team.manager_id`, not `team_id`, and can manage more than one team), so
  the obvious "fetch the person's team's documents and filter by uploader" approach silently breaks for a
  manager viewing their own profile. Caught live during testing, not guessed. `PersonPage.tsx` now shows
  per-topic freshness badges and a documents-uploaded list with a type breakdown.

### Phase 4 — UI polish
Explicit "← Back to team" / "← Back to teams" links on `GraphPage.tsx` / `PersonPage.tsx` (a fixed
destination, not `history.back()`, since a deep link or refresh breaks that). Document-type filter
dropdown on the team Documents list in `TeamPage.tsx`.

### Verification
All 4 phases verified live in Chrome against team 8 ("CCR Risk Engine Team", real multi-document test
data) and a fresh "Phase1 Verify Team". Backend: `docker compose logs backend` shows no errors after each
change; DB schema changes (`document_topics.subject_user_id`, `topics.embedding`,
`knowledge_evidence.freshness_label`) applied live via `ALTER TABLE`/`ALTER TYPE` (see infra notes — this
project still has no migration system) and existing rows backfilled with a one-off recompute script.
Frontend: `docker compose exec frontend npm run build` (tsc + vite) clean on every change.

**Known residual, non-blocking issue:** team 8's *pre-existing* topic data (extracted before this
session's Phase 1 pipeline fixes existed) still has some garbage topic names ("Subject", "Date",
"PDF. Thanks", "Dana\nGlobex") left over from the old header-leak bug. Phase 1 fixed the extraction
*pipeline* going forward; it does not retroactively clean already-extracted topics on old documents.
Not fixed in this pass — flagged here rather than silently mutating existing data.

## Outlook email ingestion (2026-10-08, merged from `feature/outlook-email-ingestion`)
Merged into `frontend-redesign-company-style`. Lets `.msg`/`.eml` files go through the same upload
endpoint as PDFs/DOCX/XLSX/CSV: dual parsers, HTML/reply-chain cleanup, parent email + child attachment
documents, sender-based authorship (falls back to uploader if the sender doesn't match a team member).
Full detail in `EMAIL_FEATURE_README.md`. The merge required manually reconciling schema gaps (the live
dev DB predated this branch — missing `document_type` enum value and `parent_document_id` column, fixed
via `ALTER TYPE`/`ALTER TABLE`, same no-migrations pattern as everywhere else in this project) and fixing
a synthetic-header leak (`Subject:`/`From:`/`Date:` lines were being read by topic extraction as if they
were real content — same bug class fixed for Excel sheet headers in the Phase 1 work above).

## Frontend redesign (2026-09-20, branch `frontend-redesign-company-style`)
Restyled the frontend to match the company's internal-website design language (from `Compamy_sample_internal_website_common_design.pdf`): bold black headings, uppercase gray section/field labels, thin 1px borders instead of card shadows, a divided stat-strip for dashboard numbers, pill-shaped status/concentration badges, and a red accent (`#c8102e`) for primary buttons, links, focus rings and progress bars (replacing the old indigo). Added a footer bar and a brand mark (red square + wordmark) in the header, matching the PDF's layout pattern.

Styling/layout only — no backend, API, or business-logic changes. Shared the new look via Tailwind `@layer components` classes in `frontend/src/index.css` (`knp-btn-primary`, `knp-card`, `knp-stat-strip`, `knp-badge-*`, etc.) reused across all pages/components instead of one-off inline classes.

Verified: `npm run build` (tsc + vite) passes clean. Manually exercised the real app in Chrome against live `postgres`+`backend` containers — register, login, create team, add member, and the team dashboard all render correctly and the stat strip updates live after adding a member. Ollama/document upload/chat were not re-verified visually in this pass (no functional code touched there), but nothing in those components changed beyond swapping class names.

## Done (MVP checklist, section 18)

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Authentication | ✅ | JWT via `backend/app/auth`; manager self-registers (`POST /auth/register`), members added by manager and log in with assigned password. |
| 2 | Manager creates multiple teams | ✅ | `POST /teams`, `GET /teams` (backend/app/teams/router.py). |
| 3 | Manager adds members | ✅ | `POST /teams/{id}/members`; frontend form in `TeamPage.tsx`. |
| 4 | PDF/DOCX/XLSX/CSV upload | ✅ | `documents/router.py` + `extraction.py` (PyMuPDF, python-docx, openpyxl, pandas). |
| 5 | AI text/data extraction | ✅ | `documents/extraction.py`. |
| 6 | Topic extraction | ✅ | `knowledge/topic_extraction.py` — Ollama primary path, frequency-heuristic fallback if Ollama unavailable. |
| 7 | Embeddings | ✅ | `knowledge/embeddings.py`, local `sentence-transformers`, stored via pgvector on `DocumentChunk.embedding`. |
| 8 | Person → topic knowledge evidence | ✅ | `knowledge/scoring.py` — relevance + doc count + depth + freshness, matches README section 6 formula. |
| 9 | Topic → people overlap | ✅ | `GET /teams/{id}/topics/{topic_id}` returns people + documents; `TopicExplorer.tsx`. |
| 10 | Interactive knowledge graph | ✅ | `GET /teams/{id}/graph` returns Person/Topic/Document nodes + weighted edges (evidence score, doc relevance). `GraphPage.tsx` at `/teams/:teamId/graph` renders it with `reactflow` — 3-column layout, search-to-highlight, click-to-inspect side panel, pan/zoom/minimap. Linked from the Team page header. Verified in-browser 2026-09-20; caught and fixed a real bug (edges didn't render — custom node component was missing `<Handle>` elements). |
| 11 | Dependency analyzer | ✅ | `GET /teams/{id}/dependency` (HIGH/DISTRIBUTED concentration); `DependencyAnalyzer.tsx`. |
| 12 | Team dashboard | ✅ | `GET /teams/{id}/dashboard`; `TeamDashboardStats.tsx`. |
| 13 | Person dashboard | ✅ | New `PersonPage.tsx` at `/people/:userId` — name/designation/contact, per-topic evidence bars, doc counts. Linked from team members list, Topic Explorer, and Dependency Analyzer. Verified in-browser 2026-09-20 with real uploaded-document data. |
| 14 | Topic search | ✅ | `TopicExplorer.tsx` (search box + list), embedded in Team page. |
| 15 | RAG chatbot | ✅ | `chat/service.py` — pgvector similarity retrieval + Ollama generation, graceful fallback if Ollama down; `TeamChat.tsx`. |
| 16 | Source citations | ✅ | `ChatSourceOut` (filename + excerpt) returned and rendered. |
| 17 | Relevant contributor/contact info | ✅ | `ChatContributorOut` (name + designation) on chat responses. |
| 18 | Basic contribution activity | ✅ | New `GET /teams/{id}/contributions` (documents + distinct topics per person, ranked, plus last activity date) and `ContributionActivity.tsx` on the Team page, linking each name to their Person page. Verified in-browser 2026-09-20 with two members uploading different documents — counts and ranking were correct. |

All MVP checklist items (README section 18, 1–18) are now done, and the known event-loop-blocking issue is fixed. What's left is a final polish pass.

## Next up

Nothing queued. The app covers the full MVP, the email-ingestion feature, and the full 4-phase post-MVP
bug-fix/analytics pass. Remaining options, roughly in order of what's likely to matter most for a new
feature session:
1. **Push `ed1938d` to the remote** (`git push origin frontend-redesign-company-style`) — blocked for the
   assistant by the sandboxed environment's auto-mode classifier, needs a manual run.
2. Clean up team 8's legacy garbage topics (see "Known residual" note above) — optional, cosmetic, no
   correctness impact.
3. Frontend bundle-size warning (`vite build` reports one >500kB chunk) — pre-existing, not a regression,
   not addressed in this pass; would need `build.rolldownOptions`/dynamic `import()` code-splitting.
4. The optional/bonus README features below.
5. Whatever the user wants next.

## Polish pass (completed 2026-09-20)

Ran the full README section 24 "Hackathon Demo" script manually in-browser against real data: registered a manager, created "CCR Risk Engine Team", added Rahul/Priya/Amit, had each upload a realistic document (Risk Engine architecture, Kubernetes deployment guide, database recovery notes), then checked every downstream view. Result: it all works as the README describes —
- Topics extracted by the **real Ollama LLM** (not the heuristic fallback): "The Risk Engine", "Kubernetes", "CI/CD", "Helm", "AKS", "PostgreSQL".
- Topic Explorer: "Kubernetes" correctly shows 2 contributors (Rahul, Priya) with evidence percentages.
- Dependency Analyzer: "The Risk Engine" correctly shows HIGH concentration, 100% Rahul Sharma — matches the README's worked example almost exactly.
- AI assistant, asked "How do we deploy the Risk Engine?": returned a genuinely grounded answer synthesized from both Rahul's and Priya's documents, with source excerpts and all 3 members listed as relevant contributors with designations.
- Auth edge cases and error/empty states (login/register error messages, chat failure state, empty topic/dependency/contribution views) were already correctly handled from earlier work — spot-checked, no issues found.

Also found and fixed three real issues along the way (see "Fixed" under Known issues below): invisible form text on dark-mode systems, the backend event-loop stall, and document status not live-updating. Root-caused and fixed a fourth: Ollama had no model pulled at all, which was silently degrading topic extraction and chat to their fallback paths — see infra notes.

## Optional / bonus (README section 17 — only after MVP is fully done)
- Knowledge Gap indicator
- Duplicate document detection
- Knowledge Conflict detection
- Knowledge Handoff suggestion

None started; not required for MVP.

## Infra / housekeeping notes
- `backend/alembic/versions/` exists but is empty — schema is currently created via `Base.metadata.create_all()` on FastAPI startup (`app/main.py`), not migrations. Fine for hackathon speed; flag if this becomes a problem (e.g. needing to alter existing data).
- Docker stack (`postgres+pgvector`, `ollama`, `backend`, `frontend`) verified working end-to-end on 2026-09-20 after a Docker Desktop restart. All four services come up via `docker compose up -d --build`; backend `/docs` and frontend `/` both return 200.
- **Fixed 2026-09-20**: Vite's file watcher wasn't detecting edits made from the host into the container (bind mount on Windows/Docker Desktop doesn't propagate fs events) — hot reload silently did nothing. Added `server.watch.usePolling: true` to `frontend/vite.config.ts` and restarted the `frontend` service. If you edit frontend files and don't see changes in the browser, first check `docker compose logs frontend` for `[vite] hmr update` lines before assuming a code bug.
- **Ollama needs a model pulled manually — it is not automatic.** The `ollama` container starts with zero models (`docker compose exec ollama ollama list` was empty on 2026-09-20 even though `.env`/`config.py` already default `OLLAMA_MODEL=llama3.2`). Without this, `ollama_generate()` returns `None` on every call and the app silently degrades to its fallback paths — topic extraction uses the keyword heuristic instead of the LLM, and chat answers become "AI generation isn't available right now..." instead of a real grounded answer. Nothing in the app surfaces this to the user; it just quietly gets worse. Run this once per fresh `ollama_data` volume (e.g. after `docker compose down -v`, or on a new machine) — **before a demo**:
  ```
  docker compose exec ollama ollama pull llama3.2
  ```
  Pull took ~2 minutes for the 2GB model on 2026-09-20. First generate call after a pull (or after Ollama has been idle) is a cold start and took ~28s in testing — close to the old 30s client timeout (see "Fixed" below, now 90s). Consider running one throwaway `curl .../api/generate` warmup call right before a live demo so the first real question doesn't hit that cold-start delay.
- Git: current branch `frontend-redesign-company-style`, HEAD at `ed1938d` ("Fix multi-user knowledge
  attribution and add graph focus mode, analytics dashboard, UI polish"), 6 commits ahead of
  `origin/frontend-redesign-company-style` as of 2026-10-08 — **not yet pushed**, see "Next up" #1.
  `My_analysis_on_project.md` and `Test_logging_v2.md` are intentionally untracked (the user asked to push
  everything except markdown files in this pass).
- **Importing SQLAlchemy models directly for a one-off script throws `InvalidRequestError` on unresolved
  relationship strings** (e.g. `KeyError: 'User'`/`'Team'`) unless the full model graph is loaded first.
  `docker compose exec backend python -c "..."` scripts that query the ORM must start with
  `import app.main` (not just the specific model module) so every router/model gets imported and
  SQLAlchemy's declarative registry is fully populated before the first query runs.
- The `knowledge_evidence.freshness_label` column (added 2026-10-08) was backfilled for all existing rows
  via a one-off recompute script right after the `ALTER TABLE`; any *new* evidence gets it automatically
  through `scoring.py::recompute_evidence`, so no further backfill should be needed going forward.

## Known issues
- **Legacy garbage topic names on team 8** ("Subject", "Date", "PDF. Thanks", "Dana\nGlobex", etc.) —
  extracted before the Phase 1 header-leak fix existed; cosmetic only, not re-fixed retroactively. See
  "Known residual, non-blocking issue" under the post-MVP pass above.
- Frontend production bundle has one chunk >500kB (`vite build` warning) — not a regression, not addressed.

### Fixed
- **Invisible/low-contrast form input text on dark-mode systems** (fixed 2026-09-20, reported by user: "values are getting typed but not visible in form submission"). `frontend/src/index.css` had the default Vite template's `:root { color-scheme: light dark }`, but the app has no dark theme anywhere (`grep dark: frontend/src` → no matches) — it's light-only by design. On a browser/OS with a dark preference, this made the browser apply native dark form-control rendering to `<input>` elements (which have no explicit `bg-`/`text-` Tailwind classes), while the surrounding page stayed light — so typed text became invisible or low-contrast even though the value was actually being entered and submitted correctly. Fixed by changing to `color-scheme: light` and giving `body` an explicit background/text color. Verified in a browser with `prefers-color-scheme: dark` actually true (confirmed via `matchMedia`): before checking the fix, computed input text color needed to be readable against the input background — after the fix, input text renders as dark gray (`rgb(17,24,39)`) on a transparent/white background and is clearly visible in a screenshot.
- **Backend event loop stalling during document upload** (fixed 2026-09-20). `documents/router.py`'s `upload_document` is `async def` but was calling synchronous, potentially slow work directly (`embed_document_chunks` → `sentence_transformers` model load/encode; `process_document_topics` → `ollama_generate` via blocking `httpx.post`). Since Uvicorn runs a single worker/event loop, a slow upload could block *all other requests* — this was observed during testing as the frontend hanging on "Loading…" while `/auth/me` queued behind an in-flight upload. Fixed by wrapping `extract_text`, `process_document_topics`, and `embed_document_chunks` in `run_in_threadpool` inside the upload route. Verified: fired a document upload that took ~11s and a concurrent `/auth/me` request 0.3s later — the second request returned in 0.16s instead of waiting. (Note: FastAPI's plain `def` routes, like `chat/router.py`'s `chat` endpoint, already run in a threadpool automatically — only `async def` routes doing blocking work needed this fix.)
- **Document status could get stuck showing "processing" until a manual reload** (fixed 2026-09-20, found during the demo run-through). Not a backend bug — documents do transition to `ready` correctly (verified directly in Postgres) — but `TeamPage.tsx` only fetched the documents list once on mount, so if you loaded/revisited the page while a document (yours or a teammate's) was still processing, the page would sit on the stale "processing" status forever with no way to know it had actually finished, short of a manual refresh. In a live demo this would look like the app was broken. Fixed by polling `GET /teams/{id}/documents` every 2.5s in `TeamPage.tsx` while any document is `processing`, stopping automatically once none are.
- **Ollama client timeout too tight for a cold start** (fixed 2026-09-20). `knowledge/ollama_client.py` had a 30s timeout; an observed cold-start generate call (model not yet loaded into memory) took 28.4s — close enough to risk a spurious timeout and silent fallback on a slower machine. Bumped to 90s.
