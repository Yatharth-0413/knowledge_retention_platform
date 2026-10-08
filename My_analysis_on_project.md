# Knowledge Retention Platform
## Findings, Bugs & Enhancement Requirements

> **Purpose:**  
> This document contains findings from testing the current application, expected behavior, UI/UX improvements, knowledge-graph improvements, topic extraction requirements, and a critical multi-user knowledge retrieval issue.
>
> **Important:** Do not blindly implement assumptions. First inspect the existing codebase, understand the current architecture and data flow, identify the root cause of each issue, and then implement the fixes while preserving existing functionality.

---

# 1. Topic Extraction / Topic Creation Issues

## 1.1 Excel Topic Extraction Is Incorrect

### Test case

An Excel document was uploaded with the title:

`team_info`

The Excel content was:

| Member | Work | Impact |
|---|---|---|
| sriram | working on agile | low |
| shivam | working on devops | high |
| brian | working on software | medium |

### Current behavior

Instead of creating a topic such as:

`team_info`

the application creates:

`(sheet)`

This appears to happen because the workspace/sheet name is being used as the topic name instead of properly identifying the uploaded document/topic context.

### Expected behavior

The system should understand that:

- Document/topic context = `team_info`
- Members mentioned = Sriram, Shivam, Brian
- Knowledge/topics:
  - Agile
  - DevOps
  - Software

The exact topic extraction strategy should be based on semantic meaning rather than blindly using the sheet/workspace name.

### Required investigation

Inspect:

- Excel parsing
- Sheet/workspace name handling
- Document metadata extraction
- Topic extraction prompt
- Ollama/model response
- Topic normalization logic

Determine why `(sheet)` is being returned/generated.

---

# 2. PDF Topic Extraction Is Incorrect

## Test case

PDF title:

`devops info 2`

Content:

```text
Deployment Occurs every Friday
For deploymentapproval tag is necessary
working on java threads
java 8 is being used in all the repo
```

### Current behavior

The system creates topics such as:

- `occurs`
- `Deployment occurs`

These are not meaningful knowledge topics.

### Expected behavior

The system should identify meaningful concepts such as:

- `Deployment`
- `DevOps`
- `Java Threads`
- `Java 8`

Potentially the document title `devops info 2` should also provide useful semantic context.

### Main requirement

Topic extraction must be **semantic**, not based on random/common words from sentences.

For example:

```text
"Deployment occurs every Friday"
```

should produce:

`Deployment`

and NOT:

`occurs`

Similarly:

```text
"working on java threads"
```

should produce:

`Java Threads`

---

# 3. Investigate Whether the Ollama Model Is Causing Weak Topic Extraction

The current behavior raises the possibility that the local Ollama model is not sufficiently good at semantic topic extraction.

However:

**Do not assume the model is the root cause.**

First investigate the entire pipeline:

```text
Document
   ↓
Text Extraction
   ↓
Prompt
   ↓
Ollama Model
   ↓
Structured Response
   ↓
Topic Normalization
   ↓
Database
   ↓
UI
```

Determine where the incorrect topic is introduced.

### Specifically inspect

1. Raw extracted document text
2. Prompt sent to Ollama
3. Raw Ollama response
4. Parsed response
5. Topic normalization
6. Duplicate detection
7. Database persistence

If the model response is correct but the application stores the wrong topic, fix the application logic.

If the model itself produces poor topics, improve the prompt and/or add deterministic post-processing.

---

# 4. Topic Creation Must Be Global, Not Document-Based

This is a major functional issue.

### Current behavior

Each uploaded document appears to create its own topics independently.

Example:

Document 1:

```text
Deployment happens every Friday
```

creates:

`Deployment`

Document 2:

```text
Deployment approval process
```

may create:

`Deployment Approval`

Document 3:

```text
DevOps deployment pipeline
```

may create:

`DevOps Deployment`

This can result in many duplicate or semantically overlapping topics.

---

# 5. Required Topic Deduplication / Topic Matching

When a new document is uploaded, the system should first inspect existing topics.

The process should be:

```text
New Document
      ↓
Extract meaningful topics
      ↓
Fetch existing topics
      ↓
Compare new topics with existing topics
      ↓
Does a matching/related topic already exist?
      ↓
 ┌───────────────┴───────────────┐
 YES                             NO
 ↓                                ↓
Attach to existing topic          Create new topic
```

### Example

Existing topics:

```text
Deployment
Java
DevOps
Agile
```

New document contains:

```text
Deployment approval
DevOps deployment pipeline
Java 8 threads
```

The system should preferably associate the knowledge with:

```text
Deployment
DevOps
Java
```

instead of automatically creating:

```text
Deployment Approval
DevOps Deployment
Java 8 Threads
```

unless those are genuinely distinct concepts.

---

# 6. Topic Normalization

Topics should be normalized.

Examples:

```text
deployment
Deployment
DEPLOYMENT
deployment process
Deployment occurs
```

should be evaluated as potentially belonging to:

`Deployment`

Similarly:

```text
java 8
Java8
Java 8 programming
Java
```

should be semantically evaluated rather than blindly treated as different topics.

### Important

Do not over-merge unrelated topics.

For example:

```text
Java
JavaScript
```

must remain separate.

---

# 7. Topic Extraction Requirements

The extraction system should prefer:

### Good topics

- DevOps
- Deployment
- Java
- Java Threads
- Agile
- Kubernetes
- Spring Boot
- Database Optimization

### Bad topics

- occurs
- working
- every
- information
- this
- process
- is
- sheet
- document

The system should extract **domain concepts / areas of knowledge**, not arbitrary nouns or verbs.

---

# 8. Knowledge Graph UI Is Too Crowded

### Current graph

The graph currently contains:

```text
People
   |
Topics
   |
Documents
```

When there are many people/topics/documents, the graph becomes highly cluttered and difficult to understand.

---

# 9. Required Knowledge Graph Interaction

Implement an interactive focus mode.

### When the user selects a node

For example:

```text
Person: Sriram
```

The graph should:

1. Highlight Sriram
2. Highlight all directly connected nodes
3. Highlight topics Sriram knows
4. Highlight documents associated with those topics/knowledge
5. Dim or hide unrelated nodes
6. Smoothly animate the transition

Example:

```text
             Agile
               |
               |
          [ Sriram ]
          /        \
     team_info    agile.pdf
```

Everything directly related to Sriram should remain visible/highlighted.

Unrelated nodes should become:

- hidden, OR
- heavily dimmed

depending on what works best visually.

---

# 10. Graph Animation

The transition should feel smooth.

When selecting a node:

```text
Full graph
    ↓
Node selected
    ↓
Connected nodes identified
    ↓
Unrelated nodes fade/dim
    ↓
Connected subgraph becomes visually prominent
```

Avoid an abrupt re-render.

---

# 11. Graph Filtering / Navigation

Consider adding controls such as:

```text
Filter by:
[People ▼]
[Topics ▼]
[Documents ▼]
```

Potential filters:

- Person
- Topic
- Document
- Knowledge level
- Document type
- Recently added
- Old knowledge
- New knowledge

Do not overload the UI; prioritize the most useful filters.

---

# 12. Add Meaningful Analytics / Charts

The dashboard currently needs more useful visual analytics.

Add charts that provide actual insight into the team's knowledge.

Potential charts:

### Knowledge distribution by member

Example:

```text
Sriram   ███████████  70%
Shivam   █████████    60%
Brian    ██████       40%
```

### Knowledge distribution by topic

```text
DevOps       80%
Java         65%
Agile        50%
Deployment   45%
```

### Knowledge freshness

Show:

```text
Old
Medium
New
```

Possible visualization:

- Donut chart
- Bar chart
- Stacked bar chart

### Documents by type

Show important document types:

```text
PDF
DOC/DOCX
Excel
```

Do not give unnecessary importance to every file type.

---

# 13. Member Knowledge Detail View

When selecting a member, provide a meaningful knowledge summary.

For example:

## Sriram

### Documents uploaded

```text
team_info.xlsx
devops.pdf
java_threads.pdf
```

### Topics extracted

```text
Agile
DevOps
Deployment
Java Threads
```

### Knowledge

| Topic | Knowledge | Source |
|---|---|---|
| Agile | Medium | team_info.xlsx |
| DevOps | High | devops.pdf |
| Deployment | High | devops.pdf |
| Java Threads | Medium | java_threads.pdf |

### Knowledge freshness

```text
New
Medium
Old
```

This should be derived from the application's actual data model.

---

# 14. Important: Knowledge Level

The application should clearly represent knowledge level where applicable.

Possible values:

```text
Low
Medium
High
```

And knowledge freshness:

```text
New
Medium
Old
```

Do not confuse these two concepts.

### Knowledge level

How strongly the member is associated with / knowledgeable about a topic.

### Knowledge freshness

How recently the knowledge was added/updated.

---

# 15. Document Type Information

For member/document analytics, show important document types in separate categories/columns where appropriate.

For example:

| Member | PDF | DOC/DOCX | Excel | Important Topics |
|---|---|---|---|---|
| Sriram | ✓ | — | ✓ | Agile, DevOps |
| Shivam | ✓ | ✓ | — | DevOps, Kubernetes |

Do not display unnecessary metadata.

---

# 16. CRITICAL BUG: Multi-User Knowledge Retrieval

This is currently one of the most important functional bugs.

## Test case

Manager uploads:

`team_info`

Content:

```text
sriram    working on agile      impact: low
shivam    working on devops     impact: high
brian     working on software    impact: medium
```

### Expected behavior

When Sriram logs in and asks:

```text
What does Sriram know?
```

The system should answer correctly.

When Shivam logs in and asks:

```text
What does Shivam know?
```

the system should answer:

```text
Shivam is working on DevOps.
Knowledge/impact: High.
Source: team_info.
```

When Brian logs in and asks:

```text
What does Brian know?
```

the system should answer:

```text
Brian is working on Software.
Knowledge/impact: Medium.
Source: team_info.
```

---

# 17. Current Bug

Currently:

### Sriram

```text
"What does Sriram know?"
→ Works
```

### Shivam

```text
"What does Shivam know?"
→ "I don't have information"
```

### Brian

```text
"What does Brian know?"
→ "I don't have information"
```

This indicates that knowledge extracted from the Excel document is likely being associated incorrectly.

---

# 18. Investigate the Root Cause of Multi-User Knowledge Bug

Inspect the entire flow:

```text
Excel
 ↓
Rows
 ↓
Member extraction
 ↓
Topic extraction
 ↓
Knowledge creation
 ↓
Member association
 ↓
Database
 ↓
Authentication / current user
 ↓
Question processing
 ↓
Knowledge retrieval
 ↓
LLM answer
```

Specifically verify:

### A. Excel row parsing

Each row must be interpreted independently:

```text
Sriram → Agile → Low
Shivam → DevOps → High
Brian  → Software → Medium
```

### B. Database records

Verify that all three members actually have knowledge records.

Expected conceptual records:

```text
(Sriram, Agile, Low)
(Shivam, DevOps, High)
(Brian, Software, Medium)
```

### C. Member identity mapping

Verify that:

```text
sriram
shivam
brian
```

are correctly mapped to application users/members.

### D. Retrieval logic

When the logged-in user asks about themselves, ensure the query uses the correct authenticated member.

### E. RAG / LLM context

Ensure the retrieved context contains the correct member-specific knowledge before sending it to the LLM.

---

# 19. Important Security / Data Isolation Requirement

Do not solve the multi-user issue by simply returning the entire team's knowledge to every user.

The application should distinguish between:

```text
Current logged-in user
```

and:

```text
Other team members
```

The system should intentionally decide what information is accessible based on the application's existing permissions/business rules.

For example:

```text
User = Shivam

Question:
"What do I know?"

→ Retrieve Shivam's knowledge.

Question:
"What does Sriram know?"

→ Retrieve Sriram's knowledge only if the application's permissions allow this.
```

---

# 20. AI / RAG Quality Requirements

The answer generation should be grounded in stored knowledge.

Do not allow the LLM to invent information.

If the database contains:

```text
Shivam → DevOps → High
```

the answer should be based on that record.

If no relevant information exists:

```text
I don't have enough information about Shivam's knowledge.
```

is acceptable.

But the system must first verify the database/retrieval layer before claiming information is unavailable.

---

# 21. Recommended Architecture for Topic Processing

A better pipeline would be:

```text
                 ┌─────────────────────┐
                 │   Upload Document   │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Extract raw content │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Extract candidates  │
                 │     using LLM       │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Normalize topics    │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Fetch existing      │
                 │ topics              │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │ Semantic matching   │
                 └──────────┬──────────┘
                            ↓
                    ┌───────┴───────┐
                    ↓               ↓
              Existing topic     New topic
                    ↓               ↓
                 Reuse           Create
                    └───────┬───────┘
                            ↓
                 ┌─────────────────────┐
                 │ Associate members  │
                 │ + knowledge        │
                 └─────────────────────┘
```

---

# 22. Implementation Priorities

Implement in this order.

## P0 — Critical Bugs

### 1. Multi-user knowledge retrieval

Fix:

```text
Sriram works
Shivam fails
Brian fails
```

All valid members must have correct knowledge retrieval.

### 2. Topic extraction

Fix meaningless topics such as:

```text
occurs
Deployment occurs
(sheet)
```

### 3. Topic deduplication

New documents must reuse existing semantic topics when appropriate.

---

# 23. P1 — Knowledge Graph

Improve:

- Node selection
- Connected-node highlighting
- Unrelated-node fading/hiding
- Smooth animations
- Filtering
- Better graph layout

Goal:

> The graph should remain understandable even with many people, topics, and documents.

---

# 24. P1 — Analytics Dashboard

Add useful charts for:

- Knowledge by member
- Knowledge by topic
- Knowledge level
- Knowledge freshness
- Document contribution
- Important document types

---

# 25. P2 — General UI Improvements

Add dropdowns where appropriate.

Examples:

```text
Topic ▼
Member ▼
Knowledge Level ▼
Document Type ▼
```

Also add a **Back button** whenever navigation moves the user to another page/view and browser-back alone is not sufficient.

The back behavior should be consistent throughout the application.

---

# 26. Acceptance Criteria

The implementation should be considered successful only if the following work.

### Topic extraction

Uploading:

```text
devops info 2.pdf
```

with:

```text
Deployment occurs every Friday
For deployment approval tag is necessary
working on java threads
java 8 is being used in all the repo
```

should produce meaningful topics such as:

```text
Deployment
DevOps
Java Threads
Java
```

and must NOT produce meaningless topics such as:

```text
occurs
every
working
Deployment occurs
```

unless the system has a clear semantic reason.

---

### Topic reuse

If `Deployment` already exists and a new document discusses deployment, the system should reuse the existing topic rather than creating another duplicate/near-duplicate topic.

---

### Excel

For:

```text
team_info

sriram    working on agile      low
shivam    working on devops     high
brian     working on software   medium
```

the system must preserve all three member-to-knowledge relationships.

---

### Member retrieval

```text
Sriram → Agile → Low
Shivam → DevOps → High
Brian  → Software → Medium
```

All three must be retrievable correctly.

---

### Knowledge graph

Selecting:

```text
Shivam
```

should visually focus on:

```text
Shivam
   ↓
DevOps
   ↓
Relevant documents
```

while unrelated nodes become visually de-emphasized.

---

### Analytics

A member should have a useful detail view showing:

- Files uploaded
- Topics extracted
- Topics known
- Knowledge level
- Knowledge freshness
- Important document types

---

# 27. Development Instructions for Claude Code

Before modifying code:

1. Inspect the repository structure.
2. Identify backend and frontend architecture.
3. Identify document ingestion pipeline.
4. Identify Excel/PDF parsing implementations.
5. Identify Ollama integration.
6. Identify topic extraction prompts.
7. Identify topic database schema/entities.
8. Identify member/user schema and relationships.
9. Identify knowledge/RAG retrieval flow.
10. Identify graph implementation.
11. Identify dashboard/chart implementation.
12. Run the existing application/tests where possible.

For every bug:

```text
Reproduce
→ Find root cause
→ Explain root cause
→ Implement minimal correct fix
→ Add/update tests
→ Verify existing functionality
```

Do not simply patch the UI if the underlying data model or retrieval pipeline is incorrect.

---

# 28. Important Engineering Principle

The goal is **not** to make the demo look correct with hardcoded rules.

The system should correctly understand:

```text
Documents
   ↓
People
   ↓
Knowledge
   ↓
Topics
   ↓
Relationships
```

and persist those relationships in a way that supports:

- Search
- RAG
- Member-specific questions
- Knowledge graphs
- Analytics
- Topic deduplication
- Future document uploads

The implementation should remain generic and work for new documents and new team members without hardcoded names such as Sriram, Shivam, or Brian.

---

# 29. Final Expected User Experience

A manager uploads:

```text
team_info.xlsx
```

The platform should automatically understand:

```text
Sriram
 └── Agile
     └── Low

Shivam
 └── DevOps
     └── High

Brian
 └── Software
     └── Medium
```

If `DevOps` already exists in the platform, the new knowledge should attach to the existing `DevOps` topic.

The dashboard should then allow the manager to understand:

- Who knows what?
- How strong is their knowledge?
- How recent is that knowledge?
- Which documents contributed to it?
- Which topics have the highest coverage?
- Which areas have knowledge gaps?

And individual users should receive accurate answers based on the knowledge actually associated with them.