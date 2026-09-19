# Knowledge Retention Platform — Hackathon MVP

## 1. Idea

An AI-powered platform that converts team documents into structured knowledge and helps answer:

- What topics are documented by each person?
- Who else has knowledge on the same topic?
- How strong is the documented evidence?
- Which topics have high dependency on one person?
- Who should I contact for a topic?
- Can AI answer questions using team documents?

The platform measures **documented knowledge evidence**, not employee competence.

---

## 2. Users

### Manager
- Register/login
- Create multiple teams
- Add team members
- Upload documents
- View team dashboard
- View knowledge graph
- View dependency analysis
- Search knowledge
- Use AI assistant

### Team Member
- Login
- Upload documents
- View own knowledge profile
- Search topics/people/documents
- View knowledge graph
- Use AI assistant
- Find relevant contributors

---

## 3. User Profile

Collect:

- Name
- Email
- Designation
- Phone number
- Team

Example:

```text
Rahul Sharma
Senior Software Engineer
rahul@company.com
+91 XXXXX XXXXX
```

These details can be shown when the AI recommends a person.

---

# 4. Document Upload

Initial formats:

- PDF
- DOCX
- XLSX
- CSV

Flow:

```text
Upload
  ↓
Extract text/data
  ↓
Split into chunks
  ↓
Extract topics
  ↓
Generate embeddings
  ↓
Store knowledge
  ↓
Update graph + analytics
```

For Excel/CSV, initially process sheet names, columns and useful textual/structured data. Perfect spreadsheet understanding is not required for the hackathon.

---

# 5. AI Topic Extraction

Example:

```text
risk-engine.pdf

Topics:
- Risk Engine
- Java
- Spring Boot
- Kubernetes
- Deployment
- CI/CD
```

The uploader can verify/edit detected topics.

---

# 6. Knowledge Evidence Score

Do not say:

> Rahul knows Kubernetes 90%.

Say:

> Rahul — Kubernetes — 90% documented knowledge evidence.

The score represents evidence found in the platform, not actual human skill.

For the MVP, calculate it from:

```text
Topic relevance
+
Relevant content depth
+
Relevant document count
+
Freshness
```

Example:

```text
Kubernetes

Rahul      88%
Priya      64%
Amit       31%
```

Keep the formula simple and explainable.

---

# 7. Knowledge Overlap

For every topic show the people who have documented evidence.

```text
Deployment

Rahul      88%
Priya      64%
Amit       31%
Karan      12%
```

Clicking a person should show:

```text
Rahul
 ↓
Deployment
 ↓
deployment-guide.pdf
 ↓
Relevant evidence/text
```

---

# 8. Knowledge Graph

Create an interactive graph connecting:

```text
Person → Topic → Document
```

Example:

```text
             Kubernetes
            /     |              Rahul    Priya    Amit
          |       |         |
        88%     64%       31%
           \      |       /
             Deployment
```

Support:

- Search
- Zoom
- Click nodes
- View relationships
- Open supporting documents

For the hackathon, use a simple graph visualization. No need for a dedicated graph database.

---

# 9. Dependency Analyzer

Identify topics where documented knowledge is highly concentrated around one person.

Example:

```text
Risk Engine

Rahul       78%
Priya       12%
Amit         7%
Others       3%

Knowledge Concentration:
HIGH
```

Compare with:

```text
Kubernetes

Rahul       38%
Priya       34%
Amit        28%

Knowledge Concentration:
DISTRIBUTED
```

The warning belongs to **team knowledge distribution**, not to the person.

---

# 10. Team Dashboard

Show:

```text
Members: 12
Documents: 86
Topics: 42
Active Contributors: 9
```

Knowledge coverage:

```text
Well Covered: 24
Moderately Covered: 11
Weakly Covered: 7
```

High dependency topics:

```text
Risk Engine        Rahul 78%
Production Deploy  Priya 71%
Database Recovery  Amit 69%
```

Recent activity:

```text
Rahul uploaded risk-engine.pdf
Priya updated deployment.docx
Amit uploaded database.xlsx
```

---

# 11. Person Knowledge Dashboard

Example:

```text
Rahul Sharma
Senior Software Engineer

Documented Knowledge

Java             88%
Spring Boot      84%
Kubernetes       79%
Azure            67%
PostgreSQL       61%
CI/CD            58%
```

Also show:

- Documents
- Topics
- Key documented contributions
- Supporting evidence

Example AI summary:

```text
• Documented Risk Engine architecture
• Documented Kubernetes deployment
• Documented rollback procedure
```

Every important claim should link to its source document.

---

# 12. Topic Explorer

Search:

```text
Kubernetes
```

Show:

```text
People
Rahul       79%
Priya       64%
Amit        31%

Documents
deployment-guide.pdf
k8s-runbook.docx
production-notes.pdf

Related Topics
Docker
CI/CD
Helm
Deployment
Azure
```

---

# 13. AI Knowledge Assistant

The chatbot uses uploaded team documents as its knowledge base.

Example:

### User

```text
How do we deploy the Risk Engine?
```

### AI

```text
According to the team's documented knowledge,
the Risk Engine is deployed using Kubernetes
through the CI/CD pipeline.

Sources:
- risk-engine.pdf
- deployment-guide.docx

Relevant contributors:
- Rahul Sharma — Senior Software Engineer
- Priya Singh — DevOps Engineer
```

If evidence is insufficient:

```text
I couldn't find enough documented information
to answer this confidently.

Relevant contributors:
Rahul Sharma
Priya Singh
```

The AI must not invent company knowledge.

---

# 14. RAG Architecture

```text
User Question
      ↓
Embedding/search
      ↓
Retrieve relevant document chunks
      ↓
Send context to local LLM
      ↓
Generate grounded answer
      ↓
Show sources
      ↓
Show relevant people
```

This is enough for the hackathon. Do not build a complicated multi-agent system.

---

# 15. Knowledge Freshness

Simple freshness indicator:

```text
Deployment Documentation

Last updated: 12 days ago
Status: Fresh
```

Suggested:

```text
0-30 days       Fresh
31-90 days      Aging
90+ days        Stale
```

---

# 16. Contribution Activity

Show knowledge contribution without treating it as employee performance.

Track:

- Documents uploaded
- Topics contributed
- Documents updated
- Last activity

Example:

```text
Rahul       24 documents
Priya       18 documents
Amit        11 documents
Karan        6 documents
```

Call this **Knowledge Contribution Activity**.

---

# 17. Optional Features

Only build these after the core flow works:

### Knowledge Gap

```text
Production Database Recovery
Documented contributors: 1
Coverage: LOW
```

### Duplicate Detection

```text
Possible duplicate found
Similarity: 91%
```

### Knowledge Conflict

```text
Potential conflict:
Document A → Java 17
Document B → Java 21
```

### Knowledge Handoff

If dependency is high:

```text
Risk Engine
Primary contributor: Rahul

Suggested action:
Create knowledge-transfer documentation
```

These are bonus features, not MVP requirements.

---

# 18. MVP — Must Have

Build these first:

1. Authentication
2. Manager creates multiple teams
3. Manager adds members
4. PDF/DOCX/XLSX/CSV upload
5. AI text/data extraction
6. Topic extraction
7. Embeddings
8. Person → topic knowledge evidence
9. Topic → people overlap
10. Interactive knowledge graph
11. Dependency analyzer
12. Team dashboard
13. Person dashboard
14. Topic search
15. RAG chatbot
16. Source citations
17. Relevant human contributor/contact information
18. Basic contribution activity

That is enough for a strong hackathon demo.

---

# 19. Recommended Tech Stack

## Frontend

```text
React
TypeScript
Vite
Tailwind CSS
Recharts
React Flow or Cytoscape.js
```

## Backend / AI

Because this is an AI-heavy project, **Python is the simplest choice**.

```text
Python
FastAPI
```

Python has strong libraries for:

- Document processing
- NLP
- Embeddings
- RAG
- AI
- Data processing

You do not need Java for this project.

---

# 20. No Paid LLM/API Requirement

Do **not** make the hackathon dependent on a paid LLM or paid API.

Use local/open-source components:

### Local LLM

```text
Ollama
```

Architecture:

```text
FastAPI
   ↓
Ollama
   ↓
Local LLM
```

Choose a local model based on the laptops available to the team.

### Embeddings

Use a local:

```text
sentence-transformers
```

### Database

```text
PostgreSQL + pgvector
```

### Document Processing

Use free/open-source libraries such as:

```text
PyMuPDF / pypdf
python-docx
openpyxl
pandas
```

No paid OpenAI/Anthropic/Gemini API is required.

---

# 21. Claude Code's Role

Your Claude Code subscription is for **building the application**, not necessarily for providing the runtime AI inside it.

Claude Code can help build:

- React frontend
- FastAPI backend
- Database models
- Document processing
- RAG pipeline
- Knowledge graph
- Dependency analytics
- Tests
- Docker setup
- Debugging

The final application can run its AI locally:

```text
Claude Code
     ↓
Builds application

Your Application
     ↓
Ollama + local LLM
     +
sentence-transformers
```

So the demo can avoid paid AI APIs.

---

# 22. Simple Architecture

```text
                 React Frontend
                       │
                       │ REST
                       ▼
                 FastAPI Backend
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
   PostgreSQL      Documents       AI / RAG
   + pgvector      Processing          │
        │              │               ▼
        │              │            Ollama
        │              │
        └──────────────┼───────────────┘
                       ▼
                Knowledge Graph
```

Use a **modular monolith**.

Do not build microservices, Kafka, Kubernetes, Redis clusters, Neo4j or separate vector databases for the hackathon.

---

# 23. Suggested Repository Structure

```text
knowledge-retention-platform/
│
├── frontend/
│   ├── src/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── auth/
│   │   ├── teams/
│   │   ├── users/
│   │   ├── documents/
│   │   ├── knowledge/
│   │   ├── analytics/
│   │   ├── graph/
│   │   └── chat/
│   │
│   ├── requirements.txt
│   └── main.py
│
├── database/
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# 24. Hackathon Demo

The complete demo should be:

```text
1. Manager logs in
2. Creates "CCR Risk Engine Team"
3. Adds Rahul, Priya and Amit
4. Rahul uploads risk-engine.pdf
5. Priya uploads deployment.docx
6. Amit uploads database.xlsx
7. AI processes documents
8. Dashboard shows topics + knowledge evidence
9. Open Knowledge Graph
10. Search "Kubernetes"
11. Show people + evidence percentages
12. Open Dependency Analyzer
13. Show Risk Engine has high concentration on Rahul
14. Ask:
    "How do we deploy the Risk Engine?"
15. AI answers from uploaded documents
16. Show citations
17. Show relevant contributor:
    Rahul Sharma
    Email
    Designation
```

---

# 25. Final Product Story

```text
Documents
    ↓
AI understands them
    ↓
Topics extracted
    ↓
People linked to topics
    ↓
Knowledge evidence calculated
    ↓
Knowledge graph created
    ↓
Dependencies become visible
    ↓
Users search knowledge
    ↓
AI answers questions
    ↓
Sources are shown
    ↓
Right human expert is identified
```

## One-line pitch

> **An AI-powered Knowledge Retention Platform that transforms team documents into a living knowledge graph, reveals knowledge dependencies, and connects employees to the right information and the right expert.**
