# Outlook Email Ingestion (`.msg` / `.eml`)

> Turn knowledge trapped in inboxes into searchable, attributable, citable team knowledge.

---

## 1. Executive Summary & Purpose

The Outlook Email Ingestion feature lets a user upload Outlook `.msg` files or standard `.eml` (MIME) messages through the same endpoint used for PDFs, Word, Excel and CSV files. The email body and its supported attachments flow through the platform's existing pipeline: chunking, topic extraction, vector embedding and retrieval-augmented chat.

### The problem: the "Inbox Silo"

Much of a team's real decision-making lives in email: why a threshold changed, who owns a process, which customer is at risk. That knowledge is:

- **Private by default.** It sits in one person's mailbox.
- **Unsearchable by the team.** Colleagues can't query it.
- **Lost on departure.** When the person leaves, so does their inbox.

### The solution

| Before | After |
|---|---|
| Decision context lives in one inbox | Cleaned body is stored as a team `EMAIL` document |
| Attachments are detached from the discussion | Attachments become child documents linked to the email |
| Expertise is invisible | Authorship credits topics to the sender's knowledge profile |
| Answers need "ask Priya" | RAG chat answers with source citations |

---

## 2. Architecture & Technical Overview

```
 .msg / .eml upload
        │
        ▼
 parse_outlook_file ──► extract-msg (.msg)  |  mail-parser (.eml)
        │
        ▼
 clean_email_body  ──► HTML → text, reply-chain + quoted-line trimming
        │
        ├─► EMAIL Document (parent) ─► _run_pipeline ─► chunks → topics → embeddings
        │
        └─► each .pdf/.docx/.xlsx/.csv attachment
                 └─► child Document (parent_document_id = email.id) ─► _run_pipeline
```

### 2.1 Dual parser pipeline

Implemented in `backend/app/documents/email_parser.py`.

| Format | Library | What is extracted |
|---|---|---|
| `.msg` (OLE2 binary) | `extract-msg` | subject, sender name/email, date, HTML or plain body, attachments |
| `.eml` (MIME) | `mail-parser` | subject, `From:` name/email, date, HTML or plain body, attachments |

- `parse_outlook_file(file_bytes, file_name)` dispatches on the extension and returns a dict: `subject`, `sender_email`, `sender_name`, `date`, `body` (cleaned), and `attachments` as `(filename, bytes)` tuples.
- If a `.msg` has an HTML body it is preferred over plain text. For `.eml` the same applies.
- The sender address is lower-cased. For `.msg`, if `msg.sender` is a bare Exchange name with no `@`, the parser falls back to `senderEmail`.
- Corrupt, empty or unsupported input raises `EmailParseError`, which the API returns as **HTTP 422**. `mail-parser` is lenient, so an `.eml` with no subject, body, sender or attachments is rejected explicitly.
- Embedded messages (a `.msg` nested inside a `.msg`) are skipped because they expose no raw bytes.

### 2.2 Text sanitation engine

`clean_email_body()` prepares text "good enough for chunking and topic extraction", not a faithful mail rendering.

1. **HTML stripping (BeautifulSoup4).** If the text looks like HTML, `script`, `style` and `head` tags are removed. Newlines are inserted only at block boundaries (`p`, `div`, `br`, `tr`, `li`, headings) so inline tags such as `<b>` don't split sentences.
2. **Normalisation.** Line endings are normalised, non-breaking spaces become spaces, trailing whitespace is trimmed and runs of blank lines are collapsed.
3. **Reply-chain trimming.** Everything from the first match of any of these patterns onward is dropped:

   | Pattern | Example |
   |---|---|
   | `-----Original Message-----` / `----- Forwarded message -----` | Outlook / Gmail dividers |
   | Underscore divider (5 or more `_`) | Outlook reply separator |
   | `On <date> <name> wrote:` (may wrap two lines) | Gmail / Apple Mail style |
   | `From:` followed within 3 lines by `Sent:` or `Date:` | Outlook header block |

4. **Quoted-line removal.** Lines beginning with `>` are removed.
5. **Safety net.** If trimming would leave nothing (for example a pure forward), the un-trimmed text is returned so content isn't lost.

> **Not implemented: signature filtering.** There is no dedicated signature stripper. Sign-offs such as "Thanks, Priya / Customer Success Lead" remain in the body, and in practice the sign-off is often useful evidence of a person's role. Add a rule to `clean_email_body` if stripping is wanted.

### 2.3 Relational database schema

Defined in `backend/app/documents/models.py`.

| Element | Detail |
|---|---|
| `DocumentType.EMAIL = "email"` | New enum member. The Postgres enum `document_type` stores labels in **uppercase** (`PDF`, `DOCX`, `XLSX`, `CSV`, `EMAIL`). |
| `documents.parent_document_id` | Nullable, indexed self-referencing foreign key to `documents.id`. `NULL` for top-level documents, including the email itself. Set for attachments. |
| `documents.uploaded_by_id` | The **author**: see below. |

**Dynamic author mapping.** The email is credited to the person who wrote it, not necessarily the person who uploaded it:

1. Take the sender address parsed from `From:` (or the `.msg` sender).
2. Look for a user with that email (case-insensitive) **within the same team**.
3. If found, that user becomes `uploaded_by_id`. Otherwise it falls back to the uploader.

Attachments inherit the same owner as the email. This is what feeds the per-person knowledge evidence, so an email Priya wrote counts toward Priya's expertise even if a manager uploaded it.

### 2.4 Vector store & RAG pipeline

Each document, whether email body or attachment, goes through the same stages:

| Stage | Implementation |
|---|---|
| Text assembly | Email text is `Subject / From / Date` header lines, a blank line, then the cleaned body. Headers go first because topic extraction reads only the head of the text. |
| Chunking | `chunking.py`: 200 words per chunk with 40 words of overlap |
| Embeddings | 384-dimensional vectors (`sentence-transformers/all-MiniLM-L6-v2`) stored in PostgreSQL with `pgvector` in `document_chunks.embedding` |
| Topic extraction | Local LLM via Ollama (default model `llama3.2`), producing topics linked through `document_topics` and aggregated into per-user `knowledge_evidence` |
| Retrieval | Chat embeds the question and takes the 5 nearest chunks by cosine distance, scoped to the team, `READY` documents only, minimum similarity 0.2 |

### 2.5 Transactional safety

`_run_pipeline()` in `backend/app/documents/router.py` runs extract → chunk → topics → embeddings inside `db.begin_nested()` (a savepoint).

- **On success:** chunks are kept and the document is marked `READY`.
- **On any exception:** the savepoint rolls back, and the document is marked `FAILED` with `error_message` set. It never stays stuck in `PROCESSING`.
- A failure on one attachment doesn't affect the email or sibling attachments.
- Slow synchronous work (parsing, Ollama, embedding) runs in the threadpool so the event loop stays responsive.

---

## 3. End-to-End Workflow & Execution

### 3.1 Lifecycle of an uploaded email

1. **Request.** The client sends `POST /teams/{team_id}/documents` as multipart with a `file`.
2. **Authorisation.** `require_team_access` checks the caller can use the team.
3. **Routing.** The extension is read. `msg` or `eml` goes to `_ingest_email`. `pdf`, `docx`, `xlsx` and `csv` go through the standard path. Anything else returns **400**.
4. **Parse.** `parse_outlook_file` runs in the threadpool. `EmailParseError` returns **422**.
5. **Attribute.** The author is resolved from the sender (section 2.3).
6. **Persist the parent.** The original file is saved under the upload directory. A `Document` is created with `file_type=EMAIL`, `filename="Email: <subject>"` and `status=PROCESSING`, then committed.
7. **Process the body.** `_run_pipeline` chunks the text, extracts topics, embeds the chunks and sets `READY` (or `FAILED`).
8. **Process attachments.** For each attachment:
   - Supported types (`pdf`, `docx`, `xlsx`, `csv`) become child `Document` rows with `parent_document_id` set, each run through `_run_pipeline`.
   - Unsupported types are reported under `attachments_skipped` with `status="skipped"`.
   - Children that fail processing are reported under `attachments_skipped` with `status="failed"` and the error detail.
9. **Respond.** **201 Created** with `EmailIngestOut`.

### 3.2 Parent–child relationship

```
documents
 ├─ id=1  EMAIL  "Email: Q3 retention review - decisions"   parent_document_id = NULL
 │    └─ id=2  PDF  "q3_retention_notes.pdf"                parent_document_id = 1
 └─ id=3  EMAIL  "Email: Q3 renewal numbers - ..."          parent_document_id = NULL
      └─ id=4  CSV  "at_risk_accounts.csv"                  parent_document_id = 3
```

The email body and the attachments are searchable independently, yet remain linked, so context from the conversation and the underlying data can be traced back together.

---

## 4. User Experience & How to Use

### 4.1 Uploading

Upload a `.msg` or `.eml` file the same way as any other document, via `POST /teams/{team_id}/documents`. Exporting from Outlook is a drag-and-drop to the desktop (`.msg`) or *Save As* (`.eml`).

### 4.2 Where ingested emails show up

| Surface | How emails appear |
|---|---|
| **RAG Chat** (`POST /teams/{id}/chat`) | Email and attachment chunks are retrieved alongside other documents. Answers cite `sources` (document id, filename such as `Email: <subject>`, excerpt) and list `contributors`. |
| **Team Member Profiles** (`GET /users/{id}/knowledge`) | Topics extracted from emails an author wrote add to that person's topic scores and document counts. |
| **Topic explorer / search** (`GET /teams/{id}/topics`, `/topics/{topic_id}`) | Email documents are listed under their topics with relevance, along with the people who have evidence for that topic. |
| **Document Library** (`GET /teams/{id}/documents`, `GET /documents/{id}`) | Emails appear with `file_type: "email"`, and chunk text can be inspected on the detail endpoint. |

> There is no separate full-text "global search" endpoint. Discovery today is semantic retrieval via chat plus topic browsing.

### 4.3 Example business queries

- *"Who has been involved in churn-alert threshold decisions?"* returns contributors and topic evidence drawn from the emails.
- *"Summarise what was decided about the weekly renewal digest."* gives a grounded 2–4 sentence answer from the email body and its PDF attachment.
- *"Which accounts are most at risk and who owns them?"* is answered from an attached CSV, with a citation to `at_risk_accounts.csv`.
- *"Where did that answer come from?"* Open the cited source to see the filename and excerpt, and trace an attachment back to its parent email through `parent_document_id`.

If nothing clears the similarity threshold, chat says it couldn't find enough documented information instead of guessing. If Ollama is unreachable, it falls back to returning the most relevant evidence excerpts.

---

## 5. Strategic Impacts & Business Benefits

- **Centralised enterprise memory.** Knowledge from an employee's mailbox can be preserved before they leave, and stays queryable and attributed to them afterwards.
- **Automated skill mapping.** Authorship plus topic extraction builds evidence of who knows what, which helps find subject-matter experts without manual tagging.
- **Complete context preservation.** The conversation (why) and its files (what) are kept together through parent–child linking.
- **Low friction.** Ingestion reuses the existing upload endpoint and pipeline, with no new infrastructure.
- **Private by design.** Parsing, embedding and the LLM all run locally (Ollama and local sentence-transformers), so no email content goes to a paid external API.

---

## 6. API Reference & Database Verification

### 6.1 `POST /teams/{team_id}/documents`

| | |
|---|---|
| **Auth** | Bearer token; caller must have access to the team |
| **Body** | `multipart/form-data` with `file` (`.pdf`, `.docx`, `.xlsx`, `.csv`, `.msg`, `.eml`) |
| **Response model** | `DocumentOut` for regular files, `EmailIngestOut` for `.msg` / `.eml` |

| Status | Meaning |
|---|---|
| `201` | Ingested (check `document.status` and the attachment lists for per-item outcomes) |
| `400` | Unsupported file type |
| `422` | Corrupt, empty or unrecognisable email file |

**`EmailIngestOut`**

```json
{
  "document": {
    "id": 1, "team_id": 1, "uploaded_by_id": 2,
    "filename": "Email: Q3 retention review - decisions",
    "file_type": "email", "status": "ready", "error_message": null,
    "created_at": "2026-10-07T17:41:33.812284Z"
  },
  "subject": "Q3 retention review - decisions",
  "sender_email": "priya.sharma@example.com",
  "sender_name": "Priya Sharma",
  "body_chunk_count": 1,
  "attachments_processed": [
    { "filename": "q3_retention_notes.pdf", "status": "processed", "document_id": 2, "detail": null }
  ],
  "attachments_skipped": []
}
```

`EmailAttachmentOut.status` is one of `processed`, `failed` or `skipped`.

### 6.2 SQL verification queries

```bash
docker compose exec -T postgres psql -U postgres -d knowledge_retention
```

Enum labels are uppercase in the database.

**a) Parent email documents**

```sql
SELECT id, uploaded_by_id, filename, file_type, status, parent_document_id
FROM documents
WHERE file_type = 'EMAIL'
ORDER BY id;
-- expect parent_document_id IS NULL
```

**b) Child attachments linked to their parent**

```sql
SELECT c.id, c.filename, c.file_type, c.status, c.parent_document_id, p.filename AS parent
FROM documents c
JOIN documents p ON p.id = c.parent_document_id
ORDER BY c.id;
```

**c) Vector chunks**

```sql
SELECT d.id AS doc_id, d.file_type, COUNT(ch.*) AS chunks,
       bool_and(ch.embedding IS NOT NULL) AS all_embedded,
       MAX(vector_dims(ch.embedding)) AS dims
FROM documents d
LEFT JOIN document_chunks ch ON ch.document_id = d.id
GROUP BY d.id
ORDER BY d.id;
-- expect dims = 384
```

---

## 7. Verification & Test Summary

Manual end-to-end test run against the Docker stack (PostgreSQL + pgvector, Ollama `llama3.2`, FastAPI backend). Fixtures were generated by `tests/fixtures/generate_fixtures.py`.

| Check | `sample_email.eml` | `sample_email.msg` |
|---|---|---|
| HTTP status | `201 Created` | `201 Created` |
| `file_type` | `email` | `email` |
| Document `status` | `ready` | `ready` |
| `body_chunk_count` | 1 | 1 |
| Attachment | `q3_retention_notes.pdf` → processed | `at_risk_accounts.csv` → processed |
| Author mapping | `uploaded_by_id = 2` (Priya, sender) | `uploaded_by_id = 2` (Priya, sender) |
| Parent row | `EMAIL`, `parent_document_id = NULL` | `EMAIL`, `parent_document_id = NULL` |
| Child row | `PDF`, `parent_document_id` = email id | `CSV`, `parent_document_id` = email id |
| Vector chunks | 384-dim embeddings present | 384-dim embeddings present |

Both uploads were made by the team's manager (user 1). The documents were credited to the sender Priya (user 2), who is a team member, which confirms the author-mapping logic.

**Parser observations**

- `.eml`: HTML was stripped, the quoted `From/Sent/To/Subject` block and `On … wrote:` / `>` history were removed, and the signature remained (see section 2.2).
- `.msg`: metadata, date and the `-----Original Message-----` trimming were verified.

**Not covered:** there is no automated pytest suite for this feature yet. Not exercised in the run: `.docx` / `.xlsx` attachments, unsupported attachment types, corrupt files (the 422 path), the no-sender-match fallback, and the frontend UI. The `.msg` fixture is synthesised by a hand-written OLE2 writer, so it is worth also trying a real file exported from Outlook.
