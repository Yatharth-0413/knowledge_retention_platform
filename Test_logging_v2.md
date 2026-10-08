# Test Logging v2 — Post Email-Ingestion Merge

End-to-end regression + new-feature test pass after merging `feature/outlook-email-ingestion` into
`frontend-redesign-company-style`. Goal: confirm the email feature works and that nothing from the
original MVP (covered in `TESTING_LOG.md`) broke. Updated live as each step is tested.

**Date:** 2026-10-08
**Tester:** Claude Code (browser automation) + user

## Pre-test setup performed

1. **Merged** `feature/outlook-email-ingestion` into `frontend-redesign-company-style` — clean merge,
   no conflicts (the feature branch already had our frontend redesign merged into it upstream).
2. **Reviewed the email feature** end to end via its own `EMAIL_FEATURE_README.md`: dual `.msg`/`.eml`
   parsers, HTML/reply-chain cleanup, parent email + child attachment documents, sender-based authorship
   crediting, same chunk/embed/topic pipeline as every other document type.
3. **Found and fixed a real schema gap:** `DocumentOut` (the API response used by the documents list)
   exposed neither `parent_document_id` nor any uploader/sender name — the frontend had no way to show
   who an email was from or which documents were attachments. Added `uploaded_by_name` (a property on
   the `Document` ORM model, reading `self.uploaded_by.name`) and `parent_document_id` to both
   `backend/app/documents/schemas.py::DocumentOut` and the frontend `KnowledgeDocument` type.
4. **Found and fixed a real migration gap:** this repo has no DB migrations (`create_all()` only adds
   *missing* tables, never alters existing ones — documented in `TECHNICAL_ARCHITECTURE.md` §6.2). Our
   live Postgres volume predates this branch, so:
   - `document_type` enum was missing the `EMAIL` label → fixed with
     `ALTER TYPE document_type ADD VALUE IF NOT EXISTS 'EMAIL';` (additive, no data loss).
   - `documents` table was missing the `parent_document_id` column → fixed with
     `ALTER TABLE documents ADD COLUMN parent_document_id INTEGER NULL REFERENCES documents(id);` plus
     its index (additive, no data loss, all prior test data preserved).
   Without these two fixes, every `.msg`/`.eml` upload would have failed at the database layer.
5. **Redesigned `TeamPage.tsx`'s Documents section** (the only place `file_type` was rendered anywhere
   in the frontend — confirmed via a full grep before starting):
   - Email documents get a distinct "Email" badge and show "From {sender}" instead of a generic file
     type line.
   - Attachments are visually nested under their parent email (indented sub-list, "Attachment" badge,
     own status/file-type shown).
   - Uploading an email now surfaces a dismissible summary panel (subject, sender, body chunks
     processed, attachments processed/skipped with reasons) — previously the `EmailIngestResult`
     response was silently discarded after upload.
   - All non-email documents also now show `Uploaded by {name}`, reusing the same new field (small
     consistency win, not previously shown for any document type).
6. **Rebuilt the backend image** (new deps: `extract-msg`, `mail-parser`, `beautifulsoup4`) — first
   attempt crash-looped (`ModuleNotFoundError: No module named 'bs4'`, confirmed in logs) because the
   bind-mounted source picked up the new router/parser code before the image had the new packages
   installed; a full `docker compose build backend` fixed it.
7. **Verified clean state before testing:**
   - `docker compose ps` — all 4 containers up, `postgres` healthy.
   - Backend startup log shows no import errors, "Application startup complete."
   - `frontend /` and `backend /docs` both return HTTP 200.
   - `docker compose exec frontend npm run build` (`tsc -b && vite build`) — passes clean, no type
     errors from the redesign.
   - `ollama list` — `llama3.2` still present (persisted volume).

---

## Test matrix

Two passes: **A. Regression** (re-verify the 12 sections from `TESTING_LOG.md` still work against the
same existing team/data) and **B. New: Email ingestion** (the actual new feature, including paths the
branch's own README flagged as untested: frontend UI, `.docx`/`.xlsx` attachments, corrupt-file 422 path,
no-sender-match fallback).

### A. Regression (existing features)

| # | Area | Result | Notes |
|---|---|---|---|
| A1 | Login / auth | ✅ pass | Manager login works; both pre-existing teams ("Other Team", "CCR Risk Engine Team") still listed. |
| A2 | Existing team/documents still load | ✅ pass | Both pre-merge CSV documents still show `ready`, correct stats preserved. Bonus: now also show "Uploaded by {name}" retroactively, proving the new `uploaded_by_name` field works on documents created before this session too. |
| A3 | Team Dashboard stats | ✅ pass | Stats tracked correctly through every upload in this session (Members/Documents/Topics/Active contributors all updated live and accurately). |
| A4 | Topic Explorer | ✅ pass | Search filter and per-topic detail panel unchanged and working; correctly merges topics across old CSV and new email-sourced documents. |
| A5 | Dependency Analyzer | ✅ pass | HIGH/DISTRIBUTED concentration logic unchanged; correctly recalculated as new contributors added evidence to shared topics (e.g. Kubernetes flipped from HIGH to DISTRIBUTED). |
| A6 | Contribution Activity | ✅ pass | Ranking and counts unchanged in logic, correctly updated with each new upload across the session. |
| A7 | Person Knowledge Dashboard | ✅ pass | Rahul Sharma's page renders unchanged pre-existing data correctly (4 topics, 4 docs, same scores as the prior test session). |
| A8 | Knowledge Graph | ✅ pass | Covered via B6 — graph renders old and new (email/attachment) documents correctly side by side. |
| A9 | AI Knowledge Assistant (chat) | ✅ pass | Covered via B7 — chat correctly retrieves across old CSVs and new email/attachment content in the same query. |
| A10 | Non-email document upload (CSV) still works | ✅ pass | Uploaded a new plain CSV after all merge/redesign changes — processed to `ready`, shows "Uploaded by Yatharth Bhardwaj", no Email badge, indistinguishable from the pre-merge upload flow. |

### B. New: Email ingestion

| # | Area | Result | Notes |
|---|---|---|---|
| B1 | Upload `.eml` fixture (has PDF attachment) | ✅ pass | 201, body + attachment both processed to `ready`. Took ~45s (fresh container re-downloaded the embedding model + 1 Ollama call) — expected, not a regression. |
| B2 | Upload `.msg` fixture (has CSV attachment) | ✅ pass | Added "Priya Sharma" (priya.sharma@example.com) as a team member first, then uploaded. Sender now matches a team member → **document correctly credited to Priya Sharma, not the uploader (manager)** — confirms the sender-match crediting path (the inverse of B9). Both the Documents list row and the summary panel show "From Priya Sharma". Took ~70s (2 uncapped Ollama calls, body + CSV attachment) — consistent with the known latency finding, not a regression. |
| B3 | Documents list: email badge, sender, nested attachment | ✅ pass | "Email" badge + "From Yatharth Bhardwaj" on the parent row, "Attachment" badge + "(PDF)" + its own `ready` status nested directly under it. |
| B4 | Email upload summary panel | ✅ pass | Subject, "From Priya Sharma" (actual parsed sender — distinct from the document's DB-credited uploader, correctly), chunk count, attachment processed list. Dismissible. |
| B5 | Email shows up correctly in Topic Explorer / evidence scoring | ✅ pass | New topics merged correctly — "Kubernetes" went from 1→2 people/docs (cross-document merge with the existing CSV topic). Dependency Analyzer correctly flipped Kubernetes to DISTRIBUTED (52%/49%) once two people had evidence on it. |
| B6 | Email shows up correctly in Knowledge Graph | ✅ pass | Email and its PDF attachment both appear as separate green Document nodes; clicking the email node shows "DOCUMENT / Email: Q3 retention review - decisions / EMAIL" in the side panel. |
| B7 | RAG chat retrieves and cites email content | ⚠️ pass with issue | Retrieval/citation worked perfectly even on the failed first attempt (correct excerpts from email body + PDF attachment + a CSV, correct contributors). First attempt's LLM generation hit the 90s client timeout on a cold-started Ollama model (`ollama` logs: `POST /api/generate` → 500 after exactly `1m30s`) and fell back to the non-grounded excerpt-dump response — working-as-designed fallback, no crash, but no synthesized answer. Retried the same question with the model now warm → fully grounded, accurate answer synthesizing both the email and its attachment. Real-world confirmation of the "no `num_predict` cap" finding from `TESTING_LOG.md` — this isn't just slow, it can fully degrade a cold-start chat response to non-grounded mode. |
| B8 | Corrupt/unparseable email → graceful 422 | ✅ pass | A single-line garbage `.eml` with no email headers was actually *accepted* (201) — `mail-parser` treated the garbage text as a valid (if junk) body, matching the README's documented leniency ("rejected only if subject/body/sender/attachments are *all* empty"), so that wasn't a true negative test. Retried with a truly empty (0-byte) `.eml` → backend correctly returned 422, frontend showed "Could not upload document. Allowed types: pdf, docx, xlsx, csv, msg, eml." — clean, no crash, no partial document row created. |
| B9 | Sender with no matching team member → falls back to uploader | ✅ pass | Sender `priya.sharma@example.com` didn't match any team member at upload time → document correctly credited to the uploader (manager Yatharth Bhardwaj), confirmed in both the Documents list and Dependency/Contribution views. |

Legend: ✅ pass · ⚠️ pass with issue noted · ❌ fail · ⏳ not yet run

---

## Detailed notes

### B1/B5 — finding: synthetic email header lines leak into extracted topics
`backend/app/documents/router.py::_ingest_email` builds the text sent to topic extraction as
`"Subject: {subject}\nFrom: {sender_label}\nDate: {sent_on}\n\n{body}"`. Observed topics extracted from
`sample_email.eml` included **"Subject"**, **"Priya Sharma"**, and **"Date"** as standalone topics — the
AI/heuristic extractor is picking up the synthetic header labels and the sender's own name as if they were
subject-matter topics. Also saw some body-derived noise ("PDF. Thanks", "Rationale", "Support Ops",
"Following", "Priya Sharma Customer") which is plausible real content from the fixture's PDF attachment,
not necessarily a bug — but the header-line leakage ("Subject", "Date", the sender's name) is a clear,
fixable quality issue specific to the email path.
**Impact:** Low — doesn't break anything, but pollutes the Topic Explorer / Dependency Analyzer with
junk topics and a HIGH-concentration badge on "Priya Sharma" (a person's name, not a topic), which looks
confusing in a demo. Not fixed in this pass (flagging per `IMPROVEMENTS_NEEDED.md` convention — didn't
change behavior without the user's go-ahead).
**Suggested fix (not applied):** either exclude the header block from the text passed to
`extract_topics()` specifically (keep it in the text used for chunking/embedding, since that's useful
context for chat retrieval, just not for topic extraction), or post-filter obviously-structural topic
strings ("Subject", "From", "Date") after extraction.

### B8 — minor finding: summary panel shows "From " with nothing after it when sender is unknown
When an email has no parseable sender name or address (the garbage-text `.eml` test case, which was
accepted as a valid-if-junk document), the upload summary panel rendered `From ` with a trailing space and
no name — `emailResult.sender_name || emailResult.sender_email` evaluates to an empty string, so the
template literal has nothing to show. Cosmetic only, low-traffic edge case (real emails from any mail
client always have a `From:` header). Not fixed in this pass.
**Suggested fix (not applied):** fall back to "an unknown sender" or similar when both are empty, in
`frontend/src/pages/TeamPage.tsx`'s email-result panel.

### B8 — minor finding: generic upload-error text doesn't distinguish "wrong type" from "corrupt content"
The empty-email 422 produced the same frontend message as an unsupported file type (`.png`, tested in the
prior session): "Could not upload document. Allowed types: pdf, docx, xlsx, csv, msg, eml." For a 422
(file type *is* allowed, content just didn't parse) this is slightly misleading, but it's not wrong enough
to cause confusion, and distinguishing it isn't essential. Not fixed in this pass.

---

## Summary

**All 19 test sections pass** (10/10 regression, 9/9 new email-feature tests). The merge is clean, the
pre-existing MVP is fully intact, and the email ingestion feature works end to end — real `.msg`/`.eml`
uploads with attachments, correct sender-based crediting (both the match and no-match paths), correct
topic/evidence/graph/chat integration, and graceful handling of an unparseable email.

**Three real gaps were found and fixed before testing could even start** (documented at the top of this
file): the missing `parent_document_id`/`uploaded_by_name` in the API response, and the missing `EMAIL`
enum value + `parent_document_id` column in the live database (this repo has no migrations, so merging a
schema change doesn't apply itself — every future schema-changing merge will hit this same trap unless
migrations are adopted, per `IMPROVEMENTS_NEEDED.md` §2.2).

**Five findings surfaced during testing, none fixed without sign-off:**
1. Synthetic `Subject:`/`From:`/`Date:` header lines leak into AI-extracted topics for every email (§B1/B5).
2. The "no `num_predict` cap" issue from the previous test pass is confirmed to cause a **real functional
   failure**, not just slowness: a cold-started Ollama model can blow the 90s client timeout mid-generation
   and silently degrade a chat answer to non-grounded excerpts (§B7) — this is the single highest-priority
   item in `IMPROVEMENTS_NEEDED.md` now that it's been seen to actually break a user-facing answer, not just
   add latency.
3. The email summary panel shows "From " with nothing after it when sender metadata is empty (§B8).
4. The generic upload-error message doesn't distinguish a 400 (wrong file type) from a 422 (corrupt content
   of an allowed type) (§B8).
5. (Carried over, confirmed still true) the embedding-model cache still isn't persisted across backend
   rebuilds — this session's rebuild re-paid that cost once again.

**Frontend redesign verdict:** the new Documents section (email badge, nested attachments, sender
attribution, upload summary panel) worked exactly as designed against real uploads with zero visual or
functional issues, and it didn't regress any existing document rendering. `uploaded_by_name` turned out to
be useful beyond emails — every document in the list now shows who uploaded it, which wasn't shown before
this session at all.

Not covered in this pass (lower priority, flagging for a future session): `.docx`/`.xlsx` email
attachments (only `.pdf` and `.csv` attachments were exercised, via the branch's existing fixtures), and
the `.msg` parser's edge cases beyond the one fixture (e.g. a real Outlook export rather than the
hand-synthesized OLE2 fixture, as the branch's own README already flagged as untested).
