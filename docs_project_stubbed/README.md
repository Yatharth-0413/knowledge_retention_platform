# Stubbed Project Data — RISQ/MMG Demo Dataset

Generated from `Document_creation.md` (repo root). This folder is the authoritative record of what was
created in the live app: who, with what credentials, in which teams, and what documents were uploaded and
why. Read this before re-running or extending the dataset.

## Key design decision: staying logged in as one user throughout

The app normally attributes an uploaded document to whoever is logged in at upload time (see
`steps_to_start_this_platform.md` §3.4's "log out and log back in as each member" instruction). The user
running this pass asked to **create every user and never log out**, which conflicts with that default
behavior — so instead of switching sessions per upload, this dataset relies on the platform's existing
**row-level person-attribution mechanism** (`backend/app/knowledge/person_attribution.py`, built during the
2026-10-08 Phase 1 bug-fix pass — see `PROGRESS.md`):

> For an uploaded XLSX/CSV, if any cell in a row exactly matches a team member's full name (or email, or
> first name), that row's remaining content is credited to *them* via `DocumentTopic.subject_user_id` —
> not to whoever actually clicked "Upload."

Every stub document below is a one-row CSV: `Member,Details`, where `Member` is a team member's **exact
full name as added to the roster**. This means **all 8 documents are uploaded while logged in as the
manager (Ravi Agrawal)**, and the app still correctly attributes each document's knowledge to the named
functional/technical employee, not to Ravi. `Ravi.agrawal@sg-india.com` stays logged in for the entire
session, per the "don't logout" instruction.

## Manager

| Field | Value |
|---|---|
| Name | Ravi Agrawal |
| Designation | Senior Manager |
| Email | Ravi.agrawal@sg-india.com |
| Password | ravi@1234 |
| Phone | 9876500001 (generated) |

## Teams

| Team | Members/documents populated? |
|---|---|
| RISQ/NFR | No — created empty, per the spec ("Populate all members and documents only for RISQ/MMG") |
| **RISQ/MMG** | **Yes — all 8 members + their documents** |
| CounterParty Credit Risq (CCR) | No — created empty |

## Roster (all added to RISQ/MMG only)

Email format: `<firstname>.<lastname>@sg-india.com` (matching the manager's own `sg-india.com` domain).
Password format: `<firstname>@1234`, as specified. Phone numbers are sequential 10-digit dummy values.

### Functional roles (→ classified "Functional" by `backend/app/recommendations/classification.py`)

| Name | Designation | Email | Password | Phone |
|---|---|---|---|---|
| Sriram Srambickal | Consultant Analyst | sriram.srambickal@sg-india.com | sriram@1234 | 9876500002 |
| Yatharth Bhardwaj | Business Analyst | yatharth.bhardwaj@sg-india.com | yatharth@1234 | 9876500003 |
| Shivam Baghel | Agile Master | shivam.baghel@sg-india.com | shivam@1234 | 9876500004 |
| Kashmira Nigade | Product Owner | kashmira.nigade@sg-india.com | kashmira@1234 | 9876500005 |

### Technical roles (→ classified "Technical")

| Name | Designation | Email | Password | Phone |
|---|---|---|---|---|
| John Doe | Software Engineer | john.doe@sg-india.com | john@1234 | 9876500006 |
| Francois Paul | QA Engineer | francois.paul@sg-india.com | francois@1234 | 9876500007 |
| Jean Charles | DevOps Engineer | jean.charles@sg-india.com | jean@1234 | 9876500008 |
| Riadh Wallet | Solutions Architect | riadh.wallet@sg-india.com | riadh@1234 | 9876500009 |

## Documents (`documents/`) — RISQ term → role mapping

All 10 RISQ terms from `Document_creation.md` are used exactly once, each mapped to the role it's most
naturally relevant to. Where a role had no obvious RISQ-term match, one additional role-appropriate topic
was generated (marked *generated* below), per the spec's instruction. Every document is a single CSV row,
well under the 70-word limit, using plain explicit terminology so topic extraction (Ollama or the
heuristic fallback) reliably identifies each topic.

| File | Uploaded-for (via row attribution) | Role | Topics |
|---|---|---|---|
| `consultant_analyst_rcsa_concentration_risk.csv` | Sriram Srambickal | Consultant Analyst | RCSA, Concentration Risk |
| `business_analyst_ecb_incident_review.csv` | Yatharth Bhardwaj | Business Analyst | ECB, Incident Review |
| `agile_master_lod_risk_ceremony.csv` | Shivam Baghel | Agile Master | LoD, Risk Ceremony Facilitation *(generated)* |
| `product_owner_auditing_backlog_prioritization.csv` | Kashmira Nigade | Product Owner | Auditing, Risk Backlog Prioritization *(generated)* |
| `software_engineer_it_risk_secure_coding.csv` | John Doe | Software Engineer | IT Risk Management, Secure Coding Standards *(generated)* |
| `qa_engineer_check_challenge_automated_testing.csv` | Francois Paul | QA Engineer | Check and Challenge, Automated Risk Control Testing *(generated)* |
| `devops_engineer_dora_pipeline_resilience.csv` | Jean Charles | DevOps Engineer | DORA, CI/CD Pipeline Resilience *(generated)* |
| `solutions_architect_kri_data_architecture.csv` | Riadh Wallet | Solutions Architect | Key Risk Indicator (KRI), Risk Data Architecture Design *(generated)* |

**Mapping rationale:** RCSA/Concentration Risk (risk assessment work) → the risk-focused Consultant
Analyst; ECB/Incident Review (regulatory + business-process) → Business Analyst; LoD (governance/process)
→ Agile Master, paired with a generated agile-ceremony risk topic since LoD alone is a thin fit; Auditing
→ Product Owner (stakeholder/backlog accountability), paired with a generated backlog-prioritization
topic; IT Risk Management (control implementation) → Software Engineer; Check and Challenge (independent
verification) → QA Engineer, a natural fit since QA's whole job *is* checking and challenging; DORA
(digital operational resilience, infrastructure uptime) → DevOps Engineer; KRI (dashboards/metrics
aggregation) → Solutions Architect, who also gets a generated risk-data-architecture topic.

## Execution log

Created live in Chrome (manager registered once, never logged out afterward, per instruction):
1. Registered manager Ravi Agrawal.
2. Created all 3 teams (`RISQ/NFR`, `RISQ/MMG`, `CounterParty Credit Risq (CCR)`).
3. Added all 8 members to `RISQ/MMG` only.
4. Uploaded all 8 CSVs above to `RISQ/MMG` while still logged in as the manager — verified in-browser that
   each document's knowledge was credited to the *named* person (via row attribution), not to Ravi, and
   that the new Knowledge Recommendations section correctly split Functional vs Technical for these real
   role titles.
