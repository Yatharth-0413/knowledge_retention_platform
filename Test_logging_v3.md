# Test Logging v3 — Knowledge Recommendation System

End-to-end test of the new "Knowledge Recommendations" feature (Functional vs Technical knowledge
classification + per-topic gap candidates), built on branch `feature/recoomendation_model`. Goal: confirm
the feature works correctly against the user's own described scenario (a Business Analyst uploading
CCR/risk content, a DevOps engineer uploading Java/deployment content, the platform recommending who's
missing that knowledge by role category) and that it doesn't regress anything existing or leak data
across teams.

**Date:** 2026-10-08
**Tester:** Claude Code (browser automation)

## Pre-test setup

1. Implemented per the approved plan (`C:\Users\Pavilion\.claude\plans\typed-soaring-moth.md`):
   new backend package `backend/app/recommendations/` (`classification.py`, `schemas.py`, `router.py`),
   registered in `main.py`; new frontend `KnowledgeRecommendations.tsx` + `RecommendationsCharts.tsx` +
   `api/recommendations.ts`, wired into `TeamPage.tsx` as an inline section after Contribution Activity.
2. Backend hot-reloaded cleanly (`docker compose logs backend` — no import errors, `/teams/{id}/recommendations`
   returning 200 immediately after each reload).
3. `docker compose exec frontend npm run build` (`tsc -b && vite build`) — clean, no type errors. Only the
   pre-existing >500kB chunk-size warning (documented in `PROGRESS.md`, not a regression).
4. Registered a fresh test manager (`reco-test-manager@example.com`, designation "Engineering Manager" —
   deliberately chosen to exercise the functional/technical tie-break rule) to keep this test data isolated
   from existing teams.

## Test data

**Team A — "Recommendation Test Team"** (team id 16):
| Member | Designation | Expected category |
|---|---|---|
| Priya Analyst | Business Analyst | Functional |
| David DevOps | DevOps Engineer | Technical |
| Carla Consultant | Consultant Analyst | Functional |
| Sam Softwarengg | Software Engineer | Technical |
| Ivan Intern | Intern | Unclassified |
| Reco Test Manager (owner) | Engineering Manager | Functional (tie-break) |

Uploads (each done after logging out/in as that member, per the app's upload-attribution design):
- Priya → `ccr_risk_overview.csv` (Counterparty Credit Risk, RISQ Framework, Collateral Management, etc.)
- David → `java_deployment_guide.csv` (Java Threads, Java 17 Upgrade, Kubernetes Rollout, CI/CD, etc.)
- Carla → `carla_mixed_topic.csv` — deliberately reuses the "Kubernetes Rollout" topic name with
  business/process framing, to force a topic with both functional and technical contributors (the "Mixed"
  category edge case)

**Team B — "Reco Test Team B"** (team id 17), owned by the same manager:
- Quinn QA (QA Engineer) uploads `kubernetes_qa_notes.csv`, which also produces a "Kubernetes Rollout"
  topic — deliberately colliding with Team A's topic name/id, to re-probe the known
  `KnowledgeEvidence`-has-no-`team_id` cross-team leak class this new endpoint is newly exposed to.

## Test matrix

| # | Area | Result | Notes |
|---|---|---|---|
| R1 | Functional classification + topic category | ✅ pass | All 7 of Priya's extracted topics (Counterparty Credit Risk, RISQ Framework, Collateral Management, Regulatory Capital, Exposure Monitoring, Basel III SA-CCR, Credit Exposure) correctly labeled "Functional". |
| R2 | Functional gap candidates | ✅ pass | Each functional topic's "Knowledge gap" correctly lists Reco Test Manager and Carla Consultant (both functional, no evidence yet) — David DevOps/Sam Softwarengg (technical) and Ivan Intern (unclassified) correctly never appear. |
| R3 | Technical classification + topic category | ✅ pass | All 8 of David's topics (Java Threads, Java 17 Upgrade, CI/CD, Kubernetes Rollout, Deployment Pipeline, Deployment Approval, Docker Image, Helm charts) correctly labeled "Technical". |
| R4 | Technical gap candidates | ✅ pass | Each technical topic's gap correctly lists only Sam Softwarengg — Priya/Carla/manager (functional) and Ivan (unclassified) correctly excluded. |
| R5 | Ambiguous-title tie-break ("Engineering Manager") | ✅ pass | The manager's own ambiguous designation ("Engineering Manager", matching both the "manager" and "engineer" tier-2 keywords) correctly resolved to Functional per the designed tie-break rule, confirmed by appearing in every functional topic's gap list and in the coverage chart's Functional member count (3: Priya, Carla, manager). |
| R6 | Unclassified designation ("Intern") | ✅ pass | Ivan Intern never appeared in any gap-candidate list across the whole test (functional, technical, or mixed topics) — confirmed the unclassified exclusion rule holds throughout. |
| R7 | Mixed-category topic + union gap pool | ✅ pass | After Carla (functional) uploaded content that merged into David's existing "Kubernetes Rollout" topic (confirmed first via Dependency Analyzer flipping to DISTRIBUTED 55%/45% Carla/David), the Recommendations section correctly moved that topic to "Mixed / unclassified topics" with category badge "Mixed", existing contributors David DevOps — 45% / Carla Consultant — 55%, and a 3-person gap list spanning both categories (Reco Test Manager, Priya Analyst — functional; Sam Softwarengg — technical) — exactly the union-pool design decision from the plan. |
| R8 | Coverage chart | ✅ pass | `Functional vs Technical Knowledge Coverage` bar chart rendered correctly at every stage, member/gap counts matching a hand-count of the topic cards each time (verified after Priya's upload, after David's upload, and after Carla's). |
| R9 | Empty states | ✅ pass | Before any upload: "Not enough documented evidence yet." After Priya only: "Technical knowledge — No technical topics yet." and "Mixed / unclassified topics — No mixed or unclassified topics." both correctly shown. |
| R10 | Cross-team isolation (Team A → Team B) | ✅ pass | Team B's "Kubernetes Rollout" card (same topic name/id as Team A's) showed only Quinn QA — 100% as existing contributor, "Fully covered" badge — zero leakage of David DevOps's Team A evidence. |
| R11 | Cross-team isolation (Team B → Team A) | ✅ pass | Re-checked Team A's "Kubernetes Rollout" card after Team B's upload — still showed only David DevOps (later Carla, after her own upload) — zero leakage of Quinn QA's Team B evidence into Team A's contributors or gap pool. |
| R12 | Existing features unaffected (regression) | ✅ pass | Team Dashboard stat tiles/charts, Topic Explorer, Dependency Analyzer, Knowledge Contribution Activity all continued to work correctly throughout — topic extraction quality was clean (no garbage topics like the old "(sheet)"/"occurs" bugs), confirming Phase 1's extraction-pipeline fixes still hold. |
| R13 | Console/network errors | ✅ pass | `read_console_messages` with `onlyErrors: true` after a full page reload on Team A returned no errors or exceptions at any point in the session. |

Legend: ✅ pass · ⚠️ pass with issue noted · ❌ fail

## Known pre-existing latency (not a regression, not addressed in this pass)

Each upload's Ollama topic-extraction call took 35–55 seconds (confirmed via `docker compose logs ollama`
— generations running to 200+ tokens at ~5–8 tokens/s on CPU-only `llama3.2`), consistent with the
already-documented "no `num_predict` cap" finding in `IMPROVEMENTS_NEEDED.md` §1.1. The very first upload
in this session also paid the known embedding-model cold-load cost (`IMPROVEMENTS_NEEDED.md` §1.2). Neither
is new or related to this feature — flagging only because this pass directly observed both again.

## Summary

**13/13 test sections pass.** The Knowledge Recommendation feature works correctly against the user's
exact described scenario: functional (business/process) vs technical knowledge is correctly derived from
job designation, each topic is correctly categorized by its contributors' roles, and per-topic "knowledge
gap" candidates are correctly restricted to team members in the matching role category who have no
documented evidence yet — including the deliberately-designed edge cases (an ambiguous "Engineering
Manager" title, an unclassifiable "Intern" title, and a topic with contributors spanning both categories).
The new `/teams/{id}/recommendations` endpoint correctly reuses this codebase's established
cross-team-leak-safe query pattern (`DocumentTopic`/`Document.team_id` scoping, never a bare
`KnowledgeEvidence.user_id`-in-roster filter) and was verified bidirectionally safe against a colliding
topic name on a second team. No regressions found in any existing feature; no console or network errors
observed.
