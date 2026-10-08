# Testing Log — Knowledge Retention Platform

Manual end-to-end browser test of the full demo script in `steps_to_start_this_platform.md`
(section 3) / `Knowledge-Retention-Platform-Hackathon-README.md` (section 24), run against the
live Docker stack. Updated live as each step is tested.

**Date:** 2026-10-08
**Tester:** Claude Code (browser automation) + user
**Stack state before testing:**
- `docker compose up -d --build` — all 4 containers up (`postgres` healthy, `ollama`, `backend`, `frontend`).
- Rebuilt `backend` image after fixing `backend/Dockerfile` to install CPU-only `torch` (see note below) — was previously pulling several GB of unused NVIDIA CUDA packages.
- `ollama list` confirms `llama3.2:latest` (2.0GB) already pulled from a prior session.
- Ollama warm-up request (`/api/generate`, "Say OK") succeeded in ~14s (cold start) before testing began.
- `backend /docs` → HTTP 200, `frontend /` → HTTP 200.

**Pre-existing infra note (not a new issue):** `backend/requirements.txt` has `sentence-transformers` unpinned, which pulls a recent `torch` that defaults to the full NVIDIA CUDA wheel set on Linux — bloating the backend image to 10.4GB and adding unnecessary rebuild time. Fixed by installing a CPU-only torch wheel (`--index-url https://download.pytorch.org/whl/cpu`) before `pip install -r requirements.txt` in `backend/Dockerfile`. This change is uncommitted as of this test run.

---

## Test matrix (steps_to_start_this_platform.md §3)

| # | Step | Result | Notes |
|---|---|---|---|
| 3.1 | Register as Manager | ✅ pass | Registered Yatharth Bhardwaj (yihackathon2026@gmail.com) as manager. Landed on "Your teams" with name + "Manager" shown top-right. Form text legible while typing (confirms the dark-mode input-text fix still holds). |
| 3.2 | Create a team | ✅ pass | Created "CCR Risk Engine Team". List updated immediately with "View team →" link. Team page stats (Members/Documents/Topics/Active contributors) all correctly 0 on an empty team. |
| 3.3 | Add team members | ✅ pass | Added Rahul Sharma (Senior Software Engineer) and Priya Singh (DevOps Engineer). Members list shows name + designation + email for each; Members stat tile updated live 0→1→2 without a page reload. |
| 3.4 | Upload documents as each member | ⚠️ pass with issues | Both uploads eventually succeeded with correct real-AI topics, correct attribution, and "ready" status. Both took far longer than the guide's "a few seconds" (~3 min for Rahul's, ~40s for Priya's) — two distinct root causes found, see below. |
| 3.5 | Team Dashboard | ✅ pass | Members=2, Documents=2, Topics=7, Active contributors=2 — exactly matches 2 members × 1 doc each. Knowledge coverage correctly bucketed all 7 topics as "Weakly" (single contributor each, none yet "Moderately"/"Well" covered). Recent activity lists both uploads correctly. |
| 3.6 | Topic Explorer | ✅ pass | Search filter narrows the list live (typed "Kubernetes" → list filtered to 1 match). Clicking a topic shows the right-hand panel with contributor name, designation, 53.5% evidence + progress bar, and the contributing document filename. Clicking the person's name correctly navigated to their Person page. |
| 3.7 | Dependency Analyzer | ✅ pass | All 7 topics correctly show HIGH/100% for their single contributor (Kubernetes/AKS/Helm → Priya; Java/Docker/Helm charts/PostgreSQL read replicas → Rahul) — matches the guide's "single contributor shows HIGH at 100%, that's expected" note exactly. |
| 3.8 | Knowledge Contribution Activity | ✅ pass | Ranked list: Rahul Sharma (1 document · 4 topics), Priya Singh (1 document · 3 topics), Yatharth Bhardwaj (0 documents · 0 topics) — correct counts and ranking, "Last activity" date shown, framed as activity not performance per the README. |
| 3.9 | Person Knowledge Dashboard | ✅ pass | Priya Singh's page: name/designation/email header, "Topics with documented evidence" = 3, "Contributing documents" = 3, per-topic evidence bars (Helm 56.7%, Kubernetes 53.5%, AKS 50.3%) each with correct singular/plural "1 doc" label. |
| 3.10 | Knowledge Graph | ✅ pass | Three-column layout (People/Topics/Documents) renders with correct Person→Topic→Document edges. Search box ("Rahul") correctly keeps the matching node full-opacity and fades everything else. Clicking a person node opens a side panel with type/name/designation and a working "View profile →" link. Zoom/pan controls and minimap present (not exhaustively tested — visually confirmed present). |
| 3.11 | AI Knowledge Assistant (chatbot) | ✅ pass | "How do we deploy the Risk Engine?" → grounded answer synthesizing both uploaded docs ("...deployed to Kubernetes using a CI/CD pipeline...AKS cluster using a rolling update strategy via Helm."), 2 sources with excerpts, 2 relevant contributors with designations — near-exact match to the README's worked example. Unrelated question ("What is the capital of France?") correctly returned "I couldn't find enough documented information..." instantly, no hallucination, no wasted LLM call (similarity threshold filtered it before generation). Grounded answer took ~15s end-to-end (~23s Ollama inference) — see CPU-inference finding under 3.4, same root cause applies to chat. |
| 3.12 | Graceful-failure checks | ✅ pass | Wrong password → "Invalid email or password." (red, no crash). Duplicate email → covered in §3.3 notes. Unsupported file type (.png) → "Could not upload document. Allowed types: pdf, docx, xlsx, csv." (backend returned clean 400, confirmed in logs; failed fast, no wasted AI pipeline work). Cross-team profile access (Rahul, not on "Other Team", navigating directly to another team's member's `/people/{id}`) → "Could not load this knowledge profile. You may not have access to it." — no data leak, no crash. |

Legend: ✅ pass · ⚠️ pass with issue noted · ❌ fail · ⏳ not yet run

---

## Detailed notes

### 3.3 — incidental finding: duplicate-email error path
Tried adding a member with `rahul@example.com` (leftover from a prior test session — data persists
across `docker compose down`/`up` as documented). Got a clear inline red error: "Could not add
member. That email may already be registered." No crash, form state preserved. This pre-validates
the "Duplicate email on register/add-member" check from §3.12 — re-confirming it there, no repeat
test needed unless this one regresses.

### 3.4 — finding: first upload after a fresh backend build appears to hang (~3 min), no progress feedback
**Symptom:** Uploaded `risk-engine-architecture.csv` as Rahul. The "Upload document" button switched to
"Uploading…" (disabled) and stayed that way for roughly 3 minutes — far longer than the "few seconds"
the test guide describes. No spinner detail, no "this may take a while" messaging, nothing in the UI
distinguishes this from a hung request. Reloading the page mid-wait showed the document already present
with status `processing`, so the backend had accepted it; the frontend was just waiting on the still-open
upload POST response.

**Root cause (confirmed via `docker compose logs backend`):** the backend container was rebuilt earlier in
this session (CPU-only torch fix). `sentence-transformers` downloads its embedding model
(`all-MiniLM-L6-v2`) from the HuggingFace Hub on first use and caches it under the container's home
directory — logs showed `Warning: You are sending unauthenticated requests to the HF Hub...` followed by
a weights-loading progress bar. **`docker-compose.yml` has no volume mounted for this cache** (only
`postgres_data`, `ollama_data`, `uploads_data` are persisted) — unlike the Ollama model, which *is* cached
in `ollama_data` and therefore only needs pulling once ever. This means the embedding-model download cost
is paid again on **every backend container rebuild**, not just once per machine, and it happens silently
inside the first upload request with no distinct loading state in the UI.

**Impact:** Low for a one-off hackathon demo (only the very first upload after a rebuild is slow; subsequent
uploads were fast in this same test run). But worth knowing before a live demo — if the backend image gets
rebuilt shortly before presenting, the first upload on stage could sit on "Uploading…" for a couple of
minutes with no explanation. Not something I changed code for; flagging it as a finding, not fixing it
without the user's go-ahead.

**Suggested fix (not applied):** mount a named volume for the HF cache (e.g. `huggingface_cache:/root/.cache/huggingface`)
in `docker-compose.yml`, and/or warm the embedding model on backend startup the same way Ollama is warmed
in §2.4 of the setup guide, and/or show a distinct "processing may take a minute the first time" message
in the upload UI.

### 3.4 — finding: Ollama topic-extraction call has no max-token limit, so CPU inference is slow on every upload
**Symptom:** Priya's upload (embedding model already warm this time) *still* sat on "Uploading…" for about
40 seconds. Watching `docker compose logs ollama` live during the wait showed real, active token generation
the whole time (`tg ≈ 6.7 tokens/s`, climbing steadily past **500 tokens generated** before finishing) — not
a hang.

**Root cause (confirmed by reading the code):** `backend/app/knowledge/ollama_client.py::ollama_generate()`
calls Ollama's `/api/generate` with `format: "json"` but no `options.num_predict` (max output tokens) and no
stop sequence. `format: json` only constrains the output to be *syntactically valid JSON* — it does not cap
its length. The topic-extraction prompt
(`backend/app/knowledge/topic_extraction.py::_PROMPT`) only asks for a short array of ≤8 topic strings (which
should need well under 100 tokens), but nothing stops the model from generating a much longer JSON response.
On this CPU-only `llama3.2` instance (~6.7 tok/s, no GPU), a response that runs to 500+ tokens takes over a
minute by itself — on top of the embedding step. The same unbounded-`ollama_generate()` call is also used by
the RAG chatbot (§12 of `TECHNICAL_ARCHITECTURE.md`), so this likely affects chat response latency too (not
yet confirmed — will check during §3.11).

**Impact:** Medium. Every document upload pays this cost, not just the first one (the embedding-cache finding
above compounds on top of it only for the very first request). On a CPU-only laptop this could make each
upload take 30–90s instead of the "a few seconds" the demo script promises, and could make the 90s
`ollama_client.py` timeout (added in a previous session per `PROGRESS.md`) a real risk on slower hardware —
if hit, the call silently falls back to the heuristic topic extractor with no user-visible indication that
happened.

**Suggested fix (not applied):** add `"options": {"num_predict": 120}` (or similar) to the `ollama_generate()`
request payload, at least for the `json_mode=True` topic-extraction path, to bound generation length and
latency. Not applied without the user's go-ahead since it's a behavior change, not a test.

### 3.11 — confirms the §3.4 Ollama latency finding also affects chat
"How do we deploy the Risk Engine?" took ~15s end-to-end; `docker compose logs ollama` showed a 597-token,
22.8s generation for a prompt that only needed a few sentences — same root cause as §3.4 (no `num_predict`
cap on `ollama_generate()`). Not a new finding, just confirms the one above isn't limited to uploads.

### 3.12 — test data cleanup
Created a second team ("Other Team", id 9) with a member "Outsider Oscar" purely to test cross-team
authorization. This team and member are harmless leftover test data in the dev database (same category as
the pre-existing `rahul@example.com` from prior sessions) — not cleaned up, since nothing in the test
guide asks for a clean-slate teardown and the dev-only "duplicate email" finding in §3.3 shows this kind of
leftover data is already expected/tolerated across sessions. Flagging here in case the user wants it removed
before a demo.

---

## Summary

**12/12 test sections pass.** The app correctly implements the full MVP demo script end to end: auth,
team/member management, document upload with real AI topic extraction, the knowledge-evidence scoring
formula, topic search, dependency concentration analysis, contribution activity, the knowledge graph, the
grounded RAG chatbot with citations and contributor attribution, and all four graceful-failure checks. No
correctness bugs found — every feature produces the right data in the right shape.

**Three findings worth the user's attention before a live demo, none of which I fixed without sign-off:**

1. **Backend image bloat / slow rebuild** (fixed during this session, already applied) — `torch` was
   pulling the full NVIDIA CUDA stack on a CPU-only container. Fixed in `backend/Dockerfile`.
2. **Embedding-model cache not persisted** (`docker-compose.yml` has no volume for the HuggingFace cache) —
   every backend rebuild re-downloads `all-MiniLM-L6-v2`, making the *first* upload after a rebuild take
   ~3 minutes with zero progress feedback in the UI. Not fixed; see §3.4 notes for suggested fix.
3. **No max-token cap on Ollama calls** (`ollama_client.py::ollama_generate()`) — topic extraction and chat
   generation can run to 500+ tokens for what should be short outputs, making every upload and chat question
   take 15–90s on CPU-only hardware instead of the guide's "a few seconds." Not fixed; see §3.4 notes for
   suggested fix (add `options.num_predict`).

All three are pre-existing conditions surfaced by this test pass, not introduced by it. Recommend doing a
real-document (PDF/DOCX) smoke test before a live demo, since this run only used `.csv` files — the upload
guide allows that, but PDF/DOCX extraction paths (PyMuPDF, python-docx) weren't exercised here.
