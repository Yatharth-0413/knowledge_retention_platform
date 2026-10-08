# Architecture decision log

Records the important technical decisions behind this project, in the format below. Newest decisions
are appended at the bottom. See `PROGRESS.md` for day-to-day implementation status and `TECHNICAL_ARCHITECTURE.md`
for how the system works today — this file is for *why* it's built this way.

---

## ADR-001: Local-only AI stack (Ollama + sentence-transformers), no paid APIs

- **Date:** 2026-09-19
- **Status:** Accepted
- **Context:** Hackathon constraint — no budget for external API keys, and the demo needed to run fully
  offline/self-hosted without depending on a third party's rate limits, billing, or network availability.
- **Decision:** Run a local Ollama instance (`llama3.2` model) for topic extraction and chat generation,
  and a local `sentence-transformers` model (`all-MiniLM-L6-v2`) for embeddings, both served from Docker
  containers alongside the app.
- **Alternatives:**
  - Hosted APIs (OpenAI/Anthropic/Azure OpenAI) — faster, higher quality, but cost money per request and
    require API keys and outbound network access.
  - A smaller rule-based, no-AI approach only — cheaper to build, but far worse topic/chat quality.
- **Consequences:** No per-request cost and works fully offline. Trade-off: slower CPU-only inference
  (cold starts of 15-30s), weaker output quality than hosted frontier models, and unreliable output
  *shape* (not just quality) — every caller has to treat `None`/malformed JSON as "unavailable" and
  degrade gracefully rather than trust the model's response is well-formed.

---

## ADR-002: No database migration framework — schema changes applied live via `ALTER TABLE`/`ALTER TYPE`

- **Date:** 2026-09-19
- **Status:** Accepted
- **Context:** Hackathon timeline — needed to iterate on the schema quickly without the overhead of
  writing and maintaining Alembic migration scripts for every model change.
- **Decision:** Rely on SQLAlchemy's `Base.metadata.create_all()` at app startup to create any
  missing tables/columns on a fresh database, and apply changes to an already-running dev database by
  hand (`docker compose exec postgres psql ... -c "ALTER TABLE ..."`). The `backend/alembic/` folder
  exists but is left empty.
- **Alternatives:**
  - Set up and use real Alembic migrations from day one — safer and repeatable, but materially slower to
    iterate during a time-boxed hackathon.
  - Drop and recreate the database on every schema change — loses all test/demo data each time.
- **Consequences:** Very fast to iterate. Trade-off: `create_all()` never alters *existing* tables or
  columns, so every schema change to a live dev database needs a manual step that's easy to forget — this
  has already caused at least one real bug (merging a branch whose schema the live dev DB didn't have
  yet). Not viable for a real production deployment without migrating to Alembic.

---

## ADR-003: Per-person knowledge attribution via a nullable `document_topics.subject_user_id` column

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** Knowledge was always credited to whoever *uploaded* a document, never to a person *named
  inside* it (e.g. a manager uploading a team roster spreadsheet). This caused a P0 bug: asking the chat
  about one person named in the sheet worked (by RAG luck), another didn't, from the identical file.
- **Decision:** Add a single nullable `subject_user_id` FK column to `document_topics`. `NULL` keeps
  today's behavior (credit the uploader). When a structured document (XLSX/CSV) has a row matched to a
  team member, that row's topics get `subject_user_id` set to that member, and
  `knowledge/scoring.py::recompute_evidence` unions both the subject-attributed and uploader-fallback
  evidence paths.
- **Alternatives:**
  - A separate `evidence_attribution` join table mapping (document, row, person) — more normalized, but
    added schema/query surface with no real benefit over an additive nullable column.
  - Re-run full-document topic extraction once per matched person without row-splitting — would credit
    *every* topic in the whole document to *every* matched person, far too coarse.
  - Keep crediting the uploader and rely entirely on improving RAG retrieval — doesn't fix the underlying
    attribution gap, only papers over one symptom of it.
- **Consequences:** Minimal, fully backward-compatible schema change (additive, `NULL` = old behavior);
  ordinary non-roster uploads are completely unaffected. Trade-off: every knowledge-evidence query from
  here on must remember the `subject_user_id OR (NULL AND uploader)` union — forgetting it is exactly how
  the cross-team leak in ADR-006 happened, so this pattern needs to be applied deliberately, not assumed.

---

## ADR-004: Generic, roster-based name/email matching for person attribution — no hardcoded names

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** The attribution fix (ADR-003) needs to detect, from a spreadsheet row's own cell text,
  which team member it's about. Hardcoding a specific team's member names would make the feature
  unusable for any other team.
- **Decision:** Match each row's cells against the uploading team's actual live roster
  (members + owning manager), exact full-name/email match first, falling back to a first-name-only
  whole-token match (never a substring match). Implemented once in `person_attribution.py` and reused
  identically by the chat module's entity-aware retrieval (ADR-005).
- **Alternatives:**
  - An LLM call per row asking "who is this row about" — slower, non-deterministic, and an extra Ollama
    round-trip per row.
  - Hardcode known team-member names — fast to write, completely non-generic, breaks for every other
    team.
  - Fuzzy/approximate string matching — a riskier false-positive rate for a correctness-critical
    attribution feature than we were willing to accept.
- **Consequences:** Works for any team/roster with zero configuration; deterministic and cheap (no extra
  LLM calls). Known, accepted limitation: the first-name-only fallback would collide if two team members
  shared a first name — not hit in practice yet, flagged here rather than solved pre-emptively.

---

## ADR-005: Entity-aware chat retrieval blended with vector search, not vector-only RAG

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** Embedding-similarity retrieval alone was unreliable for "What does `<name>` know?"
  questions — a short proper-noun query scored just above or below the similarity cutoff against the same
  shared chunk almost arbitrarily. This was the second symptom of the P0 bug: one person's name "worked,"
  another's didn't, from the identical source chunk.
- **Decision:** Before running vector search, match the question against the team roster (reusing
  ADR-004's matching function) and, for anyone named (or a first-person "I"/"my" reference), pull their
  `KnowledgeEvidence` directly from the database as ground truth. Merge those results with whatever
  vector search also finds, de-duplicated by chunk id.
- **Alternatives:**
  - Raise/lower the similarity threshold — doesn't fix the root cause, still luck-based for short
    proper-noun queries.
  - Switch to a larger/different embedding model — more reliable but heavier and slower, with still no
    real guarantee for proper nouns specifically.
  - Rely on prompt engineering alone — doesn't address that the right chunk was never retrieved in the
    first place.
- **Consequences:** Named-person questions are now always grounded in real evidence, immune to
  embedding-similarity luck. Adds extra DB queries per chat request when a person is named, but is purely
  additive — non-person questions are completely unaffected, which made it safe to add without touching
  the existing vector-search path.

---

## ADR-006: Team-scoped knowledge queries via `Document.team_id` joins, not a `team_id` column on `KnowledgeEvidence`

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** Found during our own testing (not user-reported): a manager who manages more than one team
  had their `KnowledgeEvidence` from Team A leak into Team B's dashboard, topic explorer, and
  contribution views, because `KnowledgeEvidence` has no `team_id` of its own and several queries
  filtered only by "is this user on the team's roster," not "did this evidence actually come from this
  team's own documents."
- **Decision:** Scope every team-level knowledge query by joining through
  `DocumentTopic → Document.team_id` (deriving the contributor as
  `coalesce(subject_user_id, uploaded_by_id)`), instead of filtering `KnowledgeEvidence.user_id` against
  the team roster directly.
- **Alternatives:**
  - Add a `team_id` column directly to `KnowledgeEvidence` — simpler queries, but `KnowledgeEvidence` is
    a per-(user, topic) cache that can legitimately be fed by documents from more than one team on the
    same shared topic name; a `team_id` column would force redesigning it into per-team rows, a bigger
    change than warranted just to fix this leak.
  - Keep roster-based filtering and add a second manual "does this topic belong to this team" check per
    call site — more fragile and easy to miss on a future endpoint, which is exactly how this bug
    happened the first time.
- **Consequences:** Fixes the leak at its root for every current call site. Trade-off: this scoping
  pattern has to be remembered and applied to any *future* team-scoped query over
  `KnowledgeEvidence`/`DocumentTopic` — nothing structurally stops a new endpoint from repeating the same
  mistake, which is why it's recorded here and covered by an integration-test regression guard
  (`tests/integration/test_cross_team_isolation.py`).

---

## ADR-007: Knowledge freshness stored as its own labeled field, kept distinct from the knowledge score

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** The 0-100 `knowledge_evidence.score` already factors in a freshness component internally,
  but there was no way to show "how recent is this" separately from "how strong is this" on screen — a
  high-scoring topic could still be stale, and the two concepts were at risk of being visually conflated
  in the new analytics dashboard.
- **Decision:** Add a separate `knowledge_evidence.freshness_label` column (`New`/`Medium`/`Old`, same
  day-threshold boundaries as the existing internal freshness weighting), computed and stored alongside
  the score in `recompute_evidence`, and surfaced as its own badge/chart wherever the score is shown.
- **Alternatives:**
  - Compute freshness on the fly from `updated_at`/most-recent-document-date instead of storing it —
    avoids a schema change, but duplicates the day-threshold logic in a second place and can't be
    grouped-by as cheaply in the dashboard's SQL.
  - Don't expose freshness as a separate concept at all, leave it folded into the score — simplest, but
    doesn't meet the requirement to keep the two ideas visually distinct.
- **Consequences:** One more column to keep in sync (every `recompute_evidence` call must set it, which
  it now does). Enables a dedicated freshness-breakdown chart and per-topic badges without recomputing
  anything at read time. Existing rows needed a one-time backfill script when the column was added.

---

## ADR-008: Knowledge Graph focus mode uses a type-aware cascade, not a plain breadth-first search

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** The knowledge graph became too crowded to read as teams added more documents. Clicking a
  node needed to narrow the view to "what's relevant," but a plain 2-hop BFS from a clicked person would
  also pull in every *other* person who happens to share one of that person's topics — not what "focus on
  this person" should mean.
- **Decision:** Implement `computeFocusSet` as an explicit, type-aware cascade: focusing a **person**
  shows their own topics and those topics' documents only (not other contributors to the same topic);
  focusing a **document** shows its topics and *all* of those topics' contributors (a document's topic is
  genuinely shared knowledge, so this direction intentionally does cascade further); focusing a **topic**
  shows only its direct one-hop neighbors.
- **Alternatives:**
  - A plain undirected BFS from the clicked node — much simpler, but produces an overly-broad result for
    a person-focus, exactly the case this was built to avoid.
  - Type-filter toggles only, with no click-to-focus — less work, but doesn't answer "what does this
    specific person/topic/document relate to."
- **Consequences:** Matches the intended product behavior, verified against the original bug report's own
  worked example. The three branches have different semantics by design, which is more code to maintain
  than a single generic BFS — documented in-code and here so it isn't "simplified" back into a uniform
  BFS later, which would reintroduce the over-broad person-focus problem.

---

## ADR-009: A dedicated `GET /users/{id}/documents` endpoint, not client-side filtering of the team's document list

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** The Person page needed a "documents this person uploaded" list. The obvious approach —
  fetch the person's team's documents and filter by uploader on the client — silently breaks for a
  manager viewing their own profile, because `User.team_id` is only ever set for members; a manager
  relates to a team via `Team.manager_id` instead, and can manage more than one team.
- **Decision:** Add a new backend endpoint, `GET /users/{id}/documents`, filtering
  `Document.uploaded_by_id` directly (independent of `team_id`), reusing the same
  `can_view_user_profile` visibility rule already used by `GET /users/{id}/knowledge`.
- **Alternatives:**
  - Have the frontend look up all of a manager's managed teams and fetch+merge each team's document list
    client-side — works, but pushes team-membership logic the backend already models cleanly into the
    frontend, plus an extra round-trip per managed team.
  - Leave the feature limited to member profiles only — doesn't meet the requirement for manager profiles
    to show their own uploads too.
- **Consequences:** Correct for both members and managers with a single request; reuses an existing,
  already-reviewed permission check rather than inventing a new one. This is now the canonical way to
  answer "what did this person upload" — any future feature needing that should call this endpoint rather
  than re-deriving it from `team_id`.

---

## ADR-010: Functional vs. Technical knowledge classification is keyword/phrase matching on free-text designation, not an ML classifier

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** The Knowledge Recommendation feature needed to classify people (by their free-text
  `designation`, e.g. "DevOps Engineer" vs "Business Analyst") and topics (by their contributors'
  categories) into Functional/Technical, to find knowledge gaps within the same role category —
  designations have no fixed enum.
- **Decision:** Use a two-tier deterministic classifier: tier-1 known phrase matches, tier-2 keyword
  matches, with an explicit "functional wins" tie-break rule for ambiguous titles like "Engineering
  Manager." Topic category is a majority vote over contributors' categories, with a tie resolved as
  "Mixed" rather than guessed.
- **Alternatives:**
  - Call the local LLM to classify each designation — more flexible for unusual titles, but
    non-deterministic and an extra Ollama round-trip per person per request.
  - Require managers to manually tag each member Functional/Technical at creation time — fully accurate,
    but an extra manual data-entry burden and a schema change nobody asked for.
- **Consequences:** Fast (no extra model calls), deterministic and explainable, and safely degrades to
  "unclassified"/"Mixed" rather than making a confident wrong guess. Trade-off: it only recognizes
  designation patterns it was built with — a genuinely novel title not covered by either tier falls
  through to "unclassified" and won't appear in any recommendation. Accepted as the right failure mode
  (silence over a wrong guess), not something to fix by guessing harder.

---

## ADR-011: Integration tests reset state with `TRUNCATE ... CASCADE`, not `drop_all`/`create_all` per test

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** Writing the first integration tests against a real Postgres database, the standard
  per-test `Base.metadata.drop_all()` teardown failed with a `CircularDependencyError` —
  `users.team_id → teams.id` and `teams.manager_id → users.id` form a genuine two-table FK cycle that
  SQLAlchemy's `drop_all` can't topologically sort (`create_all` tolerates it; `drop_all` does not).
- **Decision:** Create every table once per test session (`create_all`, idempotent), then reset data
  between tests with a single `TRUNCATE "<table1>", "<table2>", ... RESTART IDENTITY CASCADE` statement,
  which needs no dependency ordering at all.
- **Alternatives:**
  - Add `use_alter=True` to one of the two circular foreign keys in the actual models, just to make
    `drop_all` resolvable — means changing production schema/model code purely to satisfy a
    test-teardown mechanism, for a cycle that's intentional and causes no problem anywhere else.
  - Wrap each test in a savepoint/nested-transaction-and-rollback instead of touching table data directly
    — the more conventional SQLAlchemy testing pattern, but doesn't compose cleanly with this codebase's
    routers, which call `db.commit()` directly in several places, breaking savepoint-based isolation.
- **Consequences:** Fast, reliable per-test isolation against a real database without touching
  application schema code. Required documenting the `drop_all` cycle issue (here and in `PROGRESS.md`) so
  a future contributor doesn't "fix" the conftest back to `drop_all`/`create_all` and silently reintroduce
  flaky teardown failures.

---

## ADR-012: Vitest configuration kept in a separate `vitest.config.ts`, not merged into `vite.config.ts`

- **Date:** 2026-10-08
- **Status:** Accepted
- **Context:** Adding frontend unit tests required a test-runner config. Merging `test: {...}` into the
  existing `vite.config.ts` (via `import { defineConfig } from 'vitest/config'`) broke `tsc -b` with a
  plugin-type mismatch, because Vitest pins its own nested copy of Vite that's structurally incompatible,
  at the TypeScript type level, with the top-level `vite` package the project's own plugins
  (`@vitejs/plugin-react`, `@tailwindcss/vite`) are typed against.
- **Decision:** Keep `vite.config.ts` completely untouched (plain Vite config, as before) and add a
  separate `vitest.config.ts`. Vitest automatically prefers a `vitest.config.*` file over `vite.config.*`
  when both exist, so no explicit wiring is needed.
- **Alternatives:**
  - Use a `/// <reference types="vitest/config" />` triple-slash directive to augment `vite.config.ts`'s
    types in place instead of switching its `defineConfig` import — tried first, still failed, because
    the ambient augmentation targets Vitest's own nested `vite` module, not the top-level one actually
    used by `defineConfig` from `'vite'`.
  - Pin/dedupe npm's nested `vite` install so only one copy exists in `node_modules` — would fix it at
    the root, but is a broader, riskier dependency change for a hackathon-stage project.
- **Consequences:** Zero risk to the production build config. Cost: one extra config file to remember
  exists, with a documented warning (here and in `PROGRESS.md`) against re-merging the two without
  re-running `npm run build` first.
