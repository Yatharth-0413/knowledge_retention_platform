# How to Start, Test, and Stop This Platform

A complete, copy-paste guide for running the Knowledge Retention Platform locally, testing every feature in the UI, and shutting it down safely. Written so you can follow it without needing to know Docker.

Companion file: **`PROGRESS.md`** (repo root) tracks what's built and what's left — read that if you want project status, not setup steps.

---

## 1. Prerequisites (one-time check)

- **Docker Desktop** must be installed and **running** (you should see the whale icon in your system tray, and it should say "Docker Desktop is running").
  - If it's not running: open Docker Desktop from the Start menu and wait until it says "running" (can take 30–60 seconds).
  - If Docker Desktop won't start / hangs: close any IDE that might be holding a lock on it (this happened last time with PyCharm), then restart Docker Desktop. As a last resort, restart your computer.
- You are in the project folder in a terminal:
  ```
  cd D:\YI2026\knowledge-retention-platform
  ```
  All commands below assume you're in this folder.

---

## 2. Starting the platform

### 2.1 Bring everything up

```
docker compose up -d --build
```

**What this does:** starts 4 containers together —
| Container | What it is | Port |
|---|---|---|
| `postgres` | The database (stores users, teams, documents, topics, scores) | 5432 |
| `ollama` | The local AI engine (runs the LLM on your machine, no internet/API key needed) | 11434 |
| `backend` | The FastAPI server (all the app logic) | 8000 |
| `frontend` | The React web app (what you see in the browser) | 5173 |

`-d` means "detached" — it runs in the background instead of taking over your terminal. `--build` rebuilds the backend/frontend images if any code changed; it's safe to always include it (it's a no-op if nothing changed).

This takes anywhere from a few seconds (if images are already built) to a few minutes (first time, or after big dependency changes).

### 2.2 Check everything actually started

```
docker compose ps
```

**Expected result:** 4 rows, all showing `Up` (postgres should say `Up ... (healthy)`). If any row is missing or says `Exited`, see [Troubleshooting](#6-troubleshooting) below.

### 2.3 Check the AI model is loaded (only needs doing once ever, see note)

```
docker compose exec ollama ollama list
```

**Expected result:**
```
NAME               ID              SIZE      MODIFIED
llama3.2:latest    a80c4f17acd5    2.0 GB    ...
```

If this list is **empty**, the AI features (topic extraction from documents, and the chat assistant) will silently fall back to weaker, non-AI behavior — the app won't show an error, it'll just quietly work worse. Fix it by running:

```
docker compose exec ollama ollama pull llama3.2
```

This downloads ~2GB and takes a couple of minutes. **You should only ever need to do this once** — the model is saved in a Docker volume that survives restarts (see section 4). You'd only need to re-pull it if you specifically wipe that volume (`docker compose down -v`, which section 4 tells you not to do casually).

### 2.4 (Recommended before a live demo) Warm up the AI model

The very first AI request after Ollama has been idle for a while is slow (~20–30 seconds, it's loading the model into memory) — every request after that is fast (well under a second). If you're about to demo this to someone, run one throwaway request first so the first real question in front of them is fast:

```
curl -s http://localhost:11434/api/generate -d "{\"model\":\"llama3.2\",\"prompt\":\"Say OK\",\"stream\":false}"
```

You can ignore the output — you're just waking the model up.

### 2.5 Open the app

- **Frontend (the actual app):** http://localhost:5173
- **Backend API docs (Swagger UI, optional — for poking at the API directly):** http://localhost:8000/docs

---

## 3. Testing every feature, step by step

This walks through the whole product story. Budget about 15–20 minutes to go through all of it once.

> **Important quirk to understand first:** documents you upload, and the "knowledge evidence" that gets calculated, are attributed to **whoever is logged in at the time of upload** — not to a name you type somewhere. To properly test "Rahul uploaded X, Priya uploaded Y" like the product story describes, you actually need to **log out and log back in as each member** before their upload. Instructions below call this out at the right point.

### 3.1 Register as a Manager

1. Go to http://localhost:5173 — it should redirect you to `/login`.
2. Click **Register**.
3. Fill in Name, Email, Password (min 8 characters), Designation (optional), Phone (optional).
4. Click **Create manager account**.

**Check:** you should land on the "Your teams" dashboard, logged in, with your name and "manager" shown in the top-right corner.

> Only managers can self-register. Team members are created *by* a manager (next step) and log in with the password the manager sets for them — there's no separate "member sign-up" page, by design.

### 3.2 Create a team

1. On the dashboard, type a team name (e.g. `CCR Risk Engine Team`) into the box and click **Create team**.

**Check:** the team appears in the list below with a "View team →" link.

2. Click **View team →**.

**Check:** you land on the team page. Stats at the top all read 0 (Members, Documents, Topics, Active contributors) — that's expected, it's empty so far.

### 3.3 Add team members

Scroll to the **"Add a member"** section at the bottom (only managers see this).

Add 2–3 members one at a time, e.g.:
- Name: `Rahul Sharma`, Email: `rahul@example.com`, Password: `Password123!`, Designation: `Senior Software Engineer`
- Name: `Priya Singh`, Email: `priya@example.com`, Password: `Password123!`, Designation: `DevOps Engineer`

**Check:** each new member appears in the **"Members"** list higher up on the page, showing name, designation, and email. The "Members" stat tile at the top updates.

### 3.4 Upload documents as each member (this is the "log out and back in" step)

For each member you want to attribute a document to:

1. Click **Log out** (top right).
2. Log in as that member (the email/password you just set for them).
3. Navigate back to the team (you can use the browser back button, or go to http://localhost:5173 and you should see the team you're now a member of).
4. Click **Upload document**, pick a file. **Supported formats: PDF, DOCX, XLSX, CSV.**
5. Wait a few seconds — the document briefly shows status **"processing"**, then automatically flips to **"ready"** (the page polls for this, you don't need to refresh manually).

Do this for 2–3 members with different documents so you have something interesting to explore. If you don't have real files handy, even a `.csv` or `.docx` with a few paragraphs of made-up "technical documentation" text works fine — the AI extracts topics from whatever text is in the file.

**Check after each upload:** the document appears in the **Documents** list with status "ready" (not stuck on "processing" — if it stays on "processing" for more than ~30 seconds, see [Troubleshooting](#6-troubleshooting)).

6. Log out and log back in as the **manager** to continue testing the rest (managers can see everything; members can only see their own team).

### 3.5 Team Dashboard

At the top of the team page:

- **Members / Documents / Topics / Active contributors** — simple counts.
- **Knowledge coverage** bar — how many topics are "well/moderately/weakly covered" (covered = how many different people have documented evidence on that topic; more people covering a topic = healthier, less single-point-of-failure).
- **Recent activity** — last few uploads, who did them.

**Check:** these numbers match what you just uploaded (e.g. if 2 members uploaded 1 doc each, Documents = 2, Active contributors = 2).

### 3.6 Topic Explorer

Scroll to **"Topic explorer."**

1. Type in the search box to filter topics by name.
2. Click any topic in the list.

**Check:** the right-hand panel shows **who has documented knowledge evidence** on that topic (name, designation, a percentage score, and a progress bar) and **which documents** contributed to it. Click a person's name — it should take you to their **Person Knowledge Dashboard** (see 3.9).

### 3.7 Dependency Analyzer

Scroll to **"Dependency analyzer."**

**Check:** each topic shows a horizontal bar split between contributors, and a badge:
- **HIGH** (red) = one person accounts for ≥60% of the documented evidence on that topic — a single-point-of-failure risk.
- **DISTRIBUTED** (green) = knowledge is spread across multiple people.

If only one member uploaded on a given topic, it'll correctly show HIGH at 100% for that person — that's expected, not a bug.

### 3.8 Knowledge Contribution Activity

Scroll to **"Knowledge contribution activity."**

**Check:** a ranked list, most documents first, showing each person's document count, distinct topic count, and last activity date. Click a name — goes to their Person page.

### 3.9 Person Knowledge Dashboard

Reachable by clicking any person's name anywhere in the app (Members list, Topic Explorer, Dependency Analyzer, Contribution Activity, or the Knowledge Graph's side panel).

**Check:** shows their name/designation/email/phone, then a **"Documented knowledge"** list — every topic they have evidence on, with a percentage and progress bar. This is per-person evidence, not a team-wide view.

### 3.10 Knowledge Graph

Click **"View knowledge graph →"** near the top of the team page.

**Check:**
- Three colored columns: **People** (indigo), **Topics** (amber), **Documents** (green), connected by lines showing Person → Topic → Document relationships.
- **Search box** (top right): type a name — matching nodes stay full-opacity, everything else fades, so you can visually trace what one person or topic connects to.
- **Click any node** — a side panel on the right shows its details; for a person node, it includes a **"View profile →"** link to their Person page.
- **Pan/zoom**: drag the canvas to pan, use the **+ / −** buttons (bottom-left) or your mouse scroll wheel to zoom, and the small square button resets to fit everything in view. There's also a minimap in the bottom-right.

### 3.11 AI Knowledge Assistant (the chatbot)

On the team page, find **"AI knowledge assistant"** near the top.

1. Type a question about something in the documents you uploaded — e.g. if you uploaded something about deployment, try: `How do we deploy this?`
2. Click **Ask** (or press Enter).

**Check:**
- After a few seconds ("Thinking…"), you get a written answer.
- Below it: **Sources** — the actual document(s) and excerpt(s) the answer was built from.
- Below that: **Relevant contributors** — the people who uploaded those source documents, with their designation, so you know who to actually go talk to.
- If you ask something totally unrelated to anything uploaded, it should honestly say it couldn't find enough documented information, rather than making something up — that's intentional (the AI is only allowed to answer from your documents, never invent things).

### 3.12 A few "does it fail gracefully" checks (optional but good to know)

- **Wrong password on login** → clear red error message, no crash.
- **Duplicate email on register/add-member** → clear red error message.
- **Upload an unsupported file type** (e.g. a `.png`) → clear red error message, no crash.
- **View a person's profile you're not authorized to see** (different team) → a plain "could not load" message, not a crash or leaked data.

---

## 4. Stopping the platform

### Short answer for your second question

**Yes — you can absolutely close everything and it will work correctly again tomorrow**, as long as you stop it the right way (below). All your data — the database, uploaded documents, and the downloaded AI model — is saved to disk in Docker volumes that survive a stop/restart. Nothing is lost by shutting down normally.

### The right way to stop it

When you're done for the day, run:

```
docker compose down
```

**What this does:** stops and removes the 4 containers, but **keeps your data** — the database, uploaded files, and the Ollama model live in named volumes (`postgres_data`, `uploads_data`, `ollama_data`) that this command does **not** touch.

Then tomorrow, to start again, just repeat **section 2** (`docker compose up -d --build`) — everything (your users, teams, documents, topics, scores, and the AI model) will be exactly as you left it.

### What NOT to run casually

```
docker compose down -v      ← DON'T run this unless you want to wipe everything
```

The `-v` flag deletes the volumes too — this erases the entire database (all users/teams/documents) **and** the 2GB Ollama model, meaning you'd need to `ollama pull llama3.2` again next time. Only use this if you deliberately want a clean-slate reset.

### Other ways to stop, and whether they're safe

| What you do | Is your data safe? | What to do tomorrow |
|---|---|---|
| `docker compose down` (recommended) | ✅ Yes | `docker compose up -d --build` |
| `docker compose stop` (lighter — keeps containers, just pauses them) | ✅ Yes | `docker compose start` (faster, skips rebuild) |
| Just quit Docker Desktop from the tray icon | ✅ Yes | Reopen Docker Desktop, then `docker compose up -d --build` |
| Shut down / restart your computer without stopping containers first | ✅ Yes, Docker Desktop stops them cleanly as your machine shuts down | Reopen Docker Desktop, then `docker compose up -d --build` |
| `docker compose down -v` | ❌ No — wipes database + uploaded files + the AI model | `docker compose up -d --build`, then re-pull the model (section 2.3), then everything starts empty |

In short: **anything except `down -v` (or manually deleting the volumes) is safe.** `docker compose down` is the tidy, recommended way to end a session.

---

## 5. Quick reference — the commands you'll actually use day to day

```
# Start everything (run this each time you sit down to work)
docker compose up -d --build

# Check it's all running
docker compose ps

# Watch logs live if something looks wrong (Ctrl+C to stop watching, doesn't stop the app)
docker compose logs -f backend
docker compose logs -f frontend

# Stop everything for the day (keeps all your data)
docker compose down
```

---

## 6. Troubleshooting

**A container shows `Exited` in `docker compose ps`:**
```
docker compose logs <service-name>
```
(e.g. `docker compose logs backend`) — read the last lines for the actual error, then re-run `docker compose up -d --build`.

**Frontend loads but looks broken / changes you made aren't showing up:**
```
docker compose logs frontend
```
Look for `[vite] hmr update` lines when you save a file — if you don't see them after editing, restart the frontend: `docker compose restart frontend`.

**A document stays stuck on "processing" for a long time:**
This usually means Ollama is doing a slow cold-start (see section 2.4). Give it up to a minute, then refresh the page. If it's still stuck after that, check:
```
docker compose logs backend
```

**Chat answers are generic and don't mention your documents, or say "AI generation isn't available":**
Ollama likely doesn't have the model loaded — re-check section 2.3.

**Docker Desktop itself won't start:**
Close any IDE/tool that might be holding a lock on it, restart Docker Desktop, and if that fails, restart your computer — this resolved it previously.
