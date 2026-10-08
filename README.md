# Knowledge Retention Platform

A hackathon MVP that turns documents, spreadsheets, and emails a team already has into a searchable,
attributable map of who knows what — topic extraction, per-person knowledge-evidence scoring, a
knowledge graph, analytics, and a RAG chatbot, all running on local/self-hosted AI (Ollama +
`sentence-transformers`, no paid APIs). Stack: FastAPI + SQLAlchemy 2.0 + Postgres 16/pgvector backend,
React + TypeScript + Vite + Tailwind + reactflow + recharts frontend, Docker Compose for everything.

**Status as of 2026-10-08:** MVP complete, Outlook email ingestion merged in, and a full 4-phase
post-MVP bug-fix + analytics pass complete and verified live. One commit (`ed1938d`) is still unpushed —
see `PROGRESS.md` → "Next up" #1.

## Start here

**Read `PROGRESS.md` first, before anything else.** It's the authoritative, continuously-updated record
of what's built, what's in progress, and what's next — written specifically so a new chat session (with
no memory of prior ones) can resume work without re-deriving project state from the code.

Then, depending on what you're doing:

| If you need to... | Read |
|---|---|
| Resume/continue work, see what's done and what's next | **`PROGRESS.md`** (start here) |
| Run the app locally, test it in the browser, shut it down | `steps_to_start_this_platform.md` |
| Understand the original product spec / MVP checklist | `Knowledge-Retention-Platform-Hackathon-README.md` |
| Understand how the system actually works internally (data flow, DB schema, AI pipeline) | `TECHNICAL_ARCHITECTURE.md` |
| See a feature inventory of what's built today | `EXISTING_FEATURES.md` *(written 2026-10-08, before the post-MVP pass above — cross-check against `PROGRESS.md` for anything added since)* |
| See what's left for a more production-grade version | `IMPROVEMENTS_NEEDED.md` *(same caveat — some items here were since fixed; `PROGRESS.md` is current)* |
| Understand the Outlook email-ingestion feature specifically | `EMAIL_FEATURE_README.md` (+ `EMAIL_FEATURE_PROMPTS.md` for its build log) |
| See manual test run logs | `TESTING_LOG.md` (original MVP demo script), `Test_logging_v2.md` (post-email-merge regression pass), `Test_logging_v3.md` (Knowledge Recommendation System) |
| See the bug report that drove the 2026-10-08 post-MVP pass | `My_analysis_on_project.md` |

## Quick start

```
docker compose up -d --build
```

Four containers: `postgres` (pgvector), `ollama`, `backend` (FastAPI, hot-reload), `frontend` (Vite, HMR).
First run needs an Ollama model pulled once (`docker compose exec ollama ollama pull llama3.2`) — see
`steps_to_start_this_platform.md` for the full walkthrough, troubleshooting, and how to test every
feature in-browser. No migration system exists yet — schema changes are applied live via
`docker compose exec postgres psql ... -c "ALTER TABLE ..."`; see `PROGRESS.md`'s infra notes for the
pattern and a gotcha around importing SQLAlchemy models in one-off debug scripts.

## Starting a new feature

1. Read `PROGRESS.md` in full (it's not long) — know what exists before building on top of it.
2. Check `IMPROVEMENTS_NEEDED.md` and `PROGRESS.md`'s "Next up" for anything already queued that might
   overlap with what you're about to build.
3. Follow this repo's established conventions: no migrations (live `ALTER TABLE`), no hardcoded
   names/teams (match against the actual team roster, same pattern as
   `backend/app/knowledge/person_attribution.py`), scope any new team-level query through
   `Document.team_id` rather than a bare roster-membership filter (`KnowledgeEvidence` has no `team_id` of
   its own — see the cross-team leak fixes in `PROGRESS.md` for why this matters), and verify changes
   live in-browser against real data, not just a clean `tsc`/`vite build`.
4. Update `PROGRESS.md` after each completed task, same as every prior session has.
