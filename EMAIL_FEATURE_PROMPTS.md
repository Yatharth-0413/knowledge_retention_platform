# Outlook Email Ingestion Feature - Prompt Engineering & Verification Log

> A record of the prompts that guided Claude through restoring context, generating fixtures, bringing up the stack, and verifying the Outlook Email Ingestion feature (`.msg` / `.eml`).

---

## 1. Overview

One session, three user prompts:

1. A **master prompt** restored the feature's context in a fresh session and defined a five-step execution plan: inspect the disk state, synthesize fixtures, set up Docker, test the API, and verify the database.
2. **No user prompts** were sent during execution. The environment problems that came up were handled by Claude within the plan's scope. They are recorded in section 2 as an issue log, because they are what the master prompt's plan had to adapt to.
3. A **documentation prompt** asked for the feature README, and the prompt log (this file) followed.

| Phase | Driven by | Output |
|---|---|---|
| Context restoration & code inspection | Prompt 1, Step 1 | Confirmed code on disk matches the described design |
| Fixture synthesis | Prompt 1, Step 2 | `tests/fixtures/sample_email.eml`, `sample_email.msg`, `generate_fixtures.py` |
| Environment setup | Prompt 1, Step 3 | Postgres + pgvector, Ollama (`llama3.2`), backend running |
| API verification | Prompt 1, Step 4 | `201 Created` for both files, `EmailIngestOut` payloads |
| Database verification | Prompt 1, Step 5 | Parent/child rows and 384-dim vector chunks confirmed |
| Documentation | Prompts 3 | `EMAIL_FEATURE_README.md`, `EMAIL_FEATURE_PROMPTS.md` |

---

## 2. Prompt Sequence (Chronological)

### Prompt 1: Full Context Restoration & Verification Orchestration

- **Purpose:** Gives a new session the feature's architecture, the state of the code, the schema changes and a concrete execution plan, so work resumes without re-deriving anything.
- **Role:** Master Execution & Testing Prompt.
- **Content:** the prompt exactly as sent:

````text
We are resuming work on the Outlook Email Ingestion feature (.msg and .eml support) in this repository.

### Architecture & Feature Overview
1. Tech Stack: FastAPI, PostgreSQL + pgvector, SQLAlchemy, Ollama (local LLM), React.
2. Implemented Logic:
   - Dependencies: `extract-msg`, `mail-parser`, `beautifulsoup4` declared in `requirements.txt`.
   - Parser Utility (`backend/app/documents/email_parser.py`): Contains `clean_email_body` (HTML cleanup + reply-chain/header stripping) and `parse_outlook_file` (extracts metadata, cleaned body, and `(filename, bytes)` attachments). Raises `EmailParseError` on corrupt/empty files.
   - DB Models (`backend/app/documents/models.py`): Added `DocumentType.EMAIL = "email"` and `parent_document_id` foreign key for attachments.
   - API Router (`backend/app/documents/router.py`): Updated `POST /teams/{id}/documents` to handle `.msg`/`.eml`, returning `EmailIngestOut`. Routes email bodies into chunking/pgvector/Ollama and forwards `.pdf`/`.docx`/`.xlsx`/`.csv` attachments as child documents linked via `parent_document_id`.
   - Pipeline Resilience: Refactored shared ingestion into `_run_pipeline` operating inside DB savepoints.

### Execution Plan (Step-by-Step)

Step 1: Codebase Verification
- Scan and inspect the current files on disk (`requirements.txt`, `email_parser.py`, `models.py`, `schemas.py`, and `router.py`) to confirm the active state of the email ingestion code.
- Ensure all Python dependencies are installed (`pip install -r requirements.txt`).

Step 2: Generate Sample Email Fixtures
- Create a directory `tests/fixtures/` if it doesn't already exist.
- Programmatically generate `sample_email.eml` containing HTML text, reply history, email headers, and a dummy PDF attachment.
- Programmatically generate `sample_email.msg` containing metadata, cleaned body text, and an attached dummy CSV or Word document.

Step 3: Environment Setup
- Check that Docker containers are running (`docker compose up -d`). If the database schema needs a refresh to pick up `parent_document_id` and the `EMAIL` enum value, run a volume reset (`docker compose down -v && docker compose up -d`).
- Confirm the FastAPI backend is ready (or run `uvicorn app.main:app --reload` / test client execution).

Step 4: End-to-End API Controller Testing
- Send upload requests with `sample_email.msg` and `sample_email.eml` to `POST /api/teams/1/documents`.
- Print and format the returned `EmailIngestOut` response payload, verifying `file_type`, `body_chunk_count`, `attachments_processed`, and author mapping logic.

Step 5: PostgreSQL Database Inspection
- Execute queries against PostgreSQL inside the Docker container (`docker exec ... psql`) to verify:
  a) Parent email row in `documents` with `file_type = 'email'` and `parent_document_id = NULL`.
  b) Child attachment rows in `documents` with `parent_document_id` correctly referencing the parent email ID.
  c) Vector chunks generated in `document_chunks`.

Please execute these steps sequentially and display the results step-by-step.
````

> **Why it worked:** the prompt names exact files, symbols, endpoints and acceptance checks, so each step could be verified rather than assumed.

---

### Prompt 2: Interactive Session & Progress Guidance

- **Purpose:** Covers the Docker build and model pull, auth setup, seeding the team member `priya.sharma@example.com`, and the PostgreSQL enum-casing fix.
- **Role:** Execution & Environment Management.
- **Content:** The user did not send any prompts in this phase. The master prompt's plan was followed autonomously, and the table records where reality differed from the plan's assumptions and how each difference was resolved.

| # | Situation | Resolution |
|---|---|---|
| 1 | Docker daemon was not running | Started Docker Desktop and waited for `docker info` to succeed |
| 2 | No `.env` file; `docker-compose.yml` requires one | Copied `.env.example` to `.env` after confirming it is gitignored |
| 3 | Plan said "volume reset if needed" | Checked first: no volumes existed, so the DB was fresh and nothing was reset |
| 4 | Backend image build exceeded the 10-minute foreground limit | Ran in the background and polled `docker compose ps` until the backend was `running` |
| 5 | Ollama had no model | Ran `ollama pull llama3.2` inside the container |
| 6 | Plan used `/api/teams/1/documents`; the app has **no `/api` prefix** | Used `/teams/1/documents` after reading `main.py` |
| 7 | `POST /register` returned 404; auth routes live under `/auth` | Used `/auth/register` |
| 8 | Needed a user matching the email's `From:` to test author mapping | Registered a manager, created a team, then added `priya.sharma@example.com` as a member |
| 9 | `psql` helper stored in a shell variable failed in zsh (no word splitting) | Switched to a shell function |
| 10 | `file_type='email'` query failed: `invalid input value for enum document_type` | The Postgres enum stores **uppercase** labels; queried `'EMAIL'` |
| 11 | `.msg` fixture date parsed as `None` | The properties header was 24 bytes instead of 32; fixed in the generator |
| 12 | A virtualenv created in the repo was not gitignored | Deleted it and recreated it in the scratchpad directory |

---

### Prompt 3: Documentation & Artifact Synthesis

- **Purpose:** Directs synthesis of the feature documentation and this prompt log, grounded in the real code.
- **Role:** Documentation Prompt.
- **Content:** structured summary of the two documentation requests (condensed, not verbatim):

**3a. `EMAIL_FEATURE_README.md`**

| Section | Requested content |
|---|---|
| 1 | Executive summary; the "Inbox Silo" problem |
| 2 | Architecture: dual parsers, text sanitation, schema, vector/RAG pipeline, savepoint safety |
| 3 | End-to-end workflow; parent-child handling |
| 4 | UX: chat, member profiles, search, document library; example queries |
| 5 | Strategic benefits |
| 6 | API reference; SQL verification queries |
| 7 | Verification & test summary |

Constraint: *"ensure technical accuracy matching our codebase implementation."*

**3b. `EMAIL_FEATURE_PROMPTS.md`**: this file. The requested structure was Overview, the chronological prompt sequence, and best practices.

> **Outcome note:** because accuracy was requested, the README corrected two points from the request. Signature filtering is not implemented in `clean_email_body`, and there is no dedicated global-search endpoint. Both are documented as such.
>
> **Git:** the original brief mentioned commit and push. No commit or push has been made. Both documents are uncommitted. Per project memory, the merge target is `frontend-redesign-company-style`, not `main`.

---

## 3. Best Practices & Key Prompting Strategies

| Principle | How it appeared |
|---|---|
| **Explicit environment context** | Stack, file paths, symbol names (`clean_email_body`, `_run_pipeline`, `parent_document_id`) stated up front |
| **Step-by-step sequencing** | Five numbered steps, each depending on the previous one |
| **Verdict criteria** | Step 4 and 5 list the exact fields and rows that must hold (`file_type`, `body_chunk_count`, `parent_document_id = NULL`, child links, vector chunks) |
| **Conditional instructions** | "If the schema needs a refresh, reset the volume": Claude checked for existing volumes before acting |
| **Verify, don't assume** | Plan details were checked against the code, which exposed the missing `/api` prefix and the `/auth` route prefix |
| **Safe handling of destructive steps** | `down -v` is destructive; it was only a fallback, and was not needed |
| **Honest reporting** | Gaps were reported, not hidden: no signature filter, no automated tests, uncovered paths |

> **Reusable lessons**
> - Give the plan's endpoints as hints and let the assistant confirm them against the router. Paths drift.
> - State when a destructive command is allowed and when it is not.
> - Say "report what you ran", so test summaries can't claim coverage that didn't happen.
> - Postgres enum labels follow SQLAlchemy member **names** (`EMAIL`), not their string **values** (`"email"`). The API returns the value; SQL needs the name.

---

*Generated alongside `EMAIL_FEATURE_README.md`.*
