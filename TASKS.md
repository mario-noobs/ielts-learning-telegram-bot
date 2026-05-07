# TASKS.md — IELTS Web App + Telegram Bot

> Shared context file for all agents. Each agent reads this before acting and updates it after completing work.
> You (the human) are the final approver before any section moves forward.

---

## Current Sprint Goal
**M6: Design System & Landing** — Ship MVP design system (tokens + 8 primitives) + conversion-focused landing page + reskin of M1–M5 screens. Drives trial signup. 5 plumbing stories (repositories, structlog, feature flags, Storybook, seed scripts) are M6 prerequisites.

---

## Roadmap (2026–2027)

| Milestone | Due | Epic | Status |
|-----------|-----|------|--------|
| M0: Foundation | 2026-05-15 | GH#9 | Done |
| M1: Vocabulary Universe | 2026-06-15 | GH#10 | Done |
| M2: Writing Lab | 2026-07-31 | GH#11 | Done |
| M3: Listening Gym | 2026-09-15 | GH#12 | Done |
| M4: Smart Daily Plan | 2026-10-15 | GH#13 | Done |
| M5: Band Progress Map | 2026-11-15 | GH#14 | Done |
| **M6: Design System & Landing** | **2026-12-15** | **GH#92** | **Active** |
| M7: i18n Foundation | 2027-01-15 | GH#93 | Backlog |
| M8: Data Platform Migration — Phase 1 | 2027-02-28 | GH#94 | Backlog |
| M9: Reading Lab | 2027-04-15 | GH#95 | Backlog |
| M10: Data Platform Migration — Phase 2 (Cutover) | 2027-05-31 | GH#96 | Backlog |

---

## Status Board

### M6: Design System & Landing — **Sprint active (started 2026-04-18)**

Epic: **GH#92** — [milestone board](https://github.com/mario-noobs/ielts-bot/milestone/8)
3-wave execution; status labels applied on each ticket for tracing.

**Wave 1 — In Progress (parallel, no deps)**
| # | Story | Size | Role | Status |
|---|-------|------|------|--------|
| GH#120 | US-M6.1: Design tokens + Tailwind preset | S | Designer+Dev | 🟢 in-progress |
| GH#113 | US-P.1: Repository Protocol layer extraction | S | Dev | 🟢 in-progress |
| GH#114 | US-P.2: structlog + request ID middleware | S | Dev | 🟢 in-progress |
| GH#116 | US-P.3: Feature flag service | S | Dev | 🟢 in-progress |
| GH#118 | US-P.4: Storybook 8 scaffold | S | Dev | 🟢 in-progress |
| GH#119 | US-P.5: Seed scripts + `make dev` | S | Dev | 🟢 in-progress |

**Wave 2 — Blocked (starts when Wave 1 lands)**
| # | Story | Size | Depends | Status |
|---|-------|------|---------|--------|
| GH#121 | US-M6.2: 8 primitives via shadcn + tokens | M | GH#120, GH#118 | 🔴 blocked |

**Wave 3 — Blocked (parallel, starts when #121 lands)**
| # | Story | Size | Depends | Status |
|---|-------|------|---------|--------|
| GH#122 | US-M6.3: Landing hero + trial CTA | M | GH#121 | 🔴 blocked |
| GH#123 | US-M6.4: Pricing + testimonials + FAQ | S | GH#121 | 🔴 blocked |
| GH#124 | US-M6.5: Reskin M1–M5 via tokens | M | GH#121 | 🔴 blocked |
| GH#125 | US-M6.6: Empty states + illustrations | S | GH#121 | 🔴 blocked |

**Supporting work (in-progress alongside Wave 1)**
| # | Item | Owner | Drives |
|---|------|-------|--------|
| GH#97 | ADR-M6-1 Design System & Token Strategy | Architect | Gates US-M6.1 |
| GH#98 | ADR-M6-2 shadcn/ui adoption | Architect | Gates US-M6.2 |
| GH#100 | UX-M6 Design System + Landing spec | Designer | Gates US-M6.3/.6 |
| GH#103 | QA-M6 Visual & A11y test plan | QA | CI hooks into US-P.4, gates US-M6.2/.5 |

### Done (previous sprints)
- GH#1–GH#8 — Bot features (Q2 2026): Smart Daily Greeting, /word enrichment, AI caching, RPD/RPM bugfixes, deployment skill, daily challenge Firestore redesign
- GH#9–GH#59 — Web app M0–M5 (Foundation → Band Progress Map): FastAPI + Auth + Tests + Deploy, Vocab Universe, Writing Lab, Listening Gym, Smart Daily Plan, Band Progress Map. 51 issues across 6 milestones.
- GH#60–GH#91 — Follow-ups from M0–M5 (reviewer rework, docs fixes)

---

## Backlog

### M7: i18n Foundation (GH#93)
| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#126 | US-M7.1: react-i18next + VN/EN bundles | M | M6 DS in place |
| GH#127 | US-M7.2: Language switcher + persistence | S | US-M7.1 |
| GH#128 | US-M7.3: Error-code API contract refactor | M | US-M7.1 |
| GH#129 | US-M7.4: Localized AI prompts + translation cache | M | US-M7.1 |

### M8: Data Platform Migration — Phase 1 (GH#94)
**Revised 2026-05-07**: Self-hosted Postgres on the existing VPS. User core doc (`users/{uid}`) + `auth_mapping` only — subcollections stay in Firestore. Pre-launch one-shot cutover (no shadow-write). Backups to S3 free tier. ADRs M8-1 / M8-3 / M8-4 amended; M8-2 unchanged. M10 stories (canary/rollout/cutover) are likely redundant under this scope — review needed.

| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#130 | US-M8.1: Self-hosted Postgres + Alembic baseline (users + auth_mapping) | M | — |
| GH#131 | US-M8.2: Postgres user_repo (authoritative) + one-shot backfill | M | US-M8.1 |
| ~~GH#132~~ | ~~US-M8.3: Dual-write flag~~ — closed (pre-launch one-shot cutover) | — | — |
| ~~GH#133~~ | ~~US-M8.4: Shadow-read diff job~~ — closed (verification in M8.2) | — | — |
| GH#134 | US-M8.5: Backup pipeline (pg_dump → S3 free tier) | S | US-M8.1 |

### M9: Reading Lab (GH#95)
| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#135 | US-M9.1: Seed 30 Cambridge-style passages + copyright | M | — |
| GH#136 | US-M9.2: Reading API (list/detail/session) | M | US-M9.1 |
| GH#137 | US-M9.3: AI question generation + grading | M | US-M9.2 |
| GH#138 | US-M9.4: Reading Lab frontend | M | US-M9.3, M6 DS |
| GH#139 | US-M9.5: Integration (Daily Plan routing + Band Map axis) | S | US-M9.4 |

### M10: Data Platform Migration — Phase 2 Cutover (GH#96) — **Closed 2026-05-07**
Folded entirely into M8 under the pre-launch one-shot cutover pivot. M10 milestone, epic, ADR-M10-1, QA-M10, and all 4 stories closed. Future post-launch migrations of any other data will need a fresh M-series epic with a real shadow-write strategy.

| # | Story | Status | Absorbed by |
|---|-------|--------|-------------|
| ~~GH#140~~ | ~~US-M10.1: Canary read flip (1%)~~ | closed | N/A pre-launch |
| ~~GH#141~~ | ~~US-M10.2: Graduated rollout 10/50/100%~~ | closed | N/A pre-launch |
| ~~GH#142~~ | ~~US-M10.3: Retire Firestore writes~~ | closed | US-M8.2 cutover PR |
| ~~GH#143~~ | ~~US-M10.4: DR drill + runbook~~ | closed | US-M8.5 monthly drill |
| ~~GH#117~~ | ~~ADR-M10-1: Feature-Flag Cutover Plan~~ | closed | superseded by ADR-M8-3 revised |
| ~~GH#115~~ | ~~QA-M10: Cutover Rollback Drill & Soak~~ | closed | QA-M8 revised |
| ~~GH#96~~ | ~~Epic: M10~~ | closed | — |

### M11: Admin Console & RBAC (GH#13)
Admin console for platform operations: roles (user/team_admin/org_admin/platform_admin), Team and Org entities, plan management (admin-assigned, no payment rail yet), per-user AI quota enforcement, audit log, DAU/MAU dashboard, feature-flag UI. Postgres-backed for new admin tables; Firestore stays source of truth for activity subcollections. Foundation rides on M8.1.

| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#171 | US-M11.1: Admin schema migration on top of M8.1 (plans/teams/orgs/audit/ai_usage/metrics + repos) | M | US-M8.1 |
| GH#172 | US-M11.2: RBAC + AI quotas + audit log | L | US-M11.1 |
| GH#173 | US-M11.3: Admin Console MVP — Users + Plans + Flags UI | L | US-M11.2 |
| GH#174 | US-M11.4: Teams + Orgs entities (API + UI) | L | US-M11.3 |
| GH#175 | US-M11.5: Platform Dashboard + Audit Log Viewer | L | US-M11.3 |

---

## Architecture Decisions

### M0: Foundation ADRs (6) — complete
See GH#15–GH#20 (ADR-M0-1 through ADR-M0-6).

### M6–M10 ADRs (10)
| # | ADR | Status |
|---|-----|--------|
| GH#97 | ADR-M6-1: Design System & Token Strategy | Proposed |
| GH#98 | ADR-M6-2: Adopt shadcn/ui — copy-in, customize via tokens | Proposed |
| GH#99 | ADR-M7-1: i18n Stack — react-i18next + ICU + error-code API | Proposed |
| GH#101 | ADR-M7-2: AI Content Localization & Translation Cache | Proposed |
| GH#102 | ADR-M8-1: Adopt Postgres (Supabase) as primary user-data store | Proposed |
| GH#105 | ADR-M8-2: Repository Pattern for Data Access | Proposed |
| GH#108 | ADR-M8-3: Shadow-Write Migration Strategy | Proposed |
| GH#110 | ADR-M8-4: Backup & Disaster Recovery (pg_dump + B2, RPO 24h / RTO 2h) | Proposed |
| GH#112 | ADR-M9-1: Reading Content Pipeline — Real Passages + AI Questions | Proposed |
| GH#117 | ADR-M10-1: Feature-Flag Cutover & Firestore Sunset Plan | Proposed |

---

## UX Specs
| # | Spec | Milestone |
|---|------|-----------|
| GH#21 | UX-GLOBAL: App Shell, Navigation, Onboarding | M0 |
| GH#22 | UX-M1: Vocabulary Universe Screens | M1 |
| GH#23 | UX-M2: Writing Lab Screens | M2 |
| GH#24 | UX-M3: Listening Gym Screens | M3 |
| GH#25 | UX-M4: Smart Daily Plan Screens | M4 |
| GH#26 | UX-M5: Band Progress Map Screens | M5 |
| GH#100 | UX-M6: Design System Foundation + Landing Page | M6 |
| GH#104 | UX-M7: i18n UX Patterns | M7 |
| GH#107 | UX-M9: Reading Lab Screens | M9 |

---

## QA Test Plans
| # | Plan | Milestone |
|---|------|-----------|
| GH#27 | QA-M0: Foundation | M0 |
| GH#28 | QA-M1: Vocabulary Universe | M1 |
| GH#29 | QA-M2: Writing Lab | M2 |
| GH#30 | QA-M3: Listening Gym | M3 |
| GH#31 | QA-M4: Smart Daily Plan | M4 |
| GH#32 | QA-M5: Band Progress Map | M5 |
| GH#103 | QA-M6: Design System Visual & A11y | M6 |
| GH#106 | QA-M7: i18n Pseudo-Loc & Overflow | M7 |
| GH#109 | QA-M8: Shadow-Write Verification + SRS Golden Replay | M8 |
| GH#111 | QA-M9: Reading Grounding + Copyright Compliance | M9 |
| GH#115 | QA-M10: Cutover Rollback Drill + Post-Cutover Soak | M10 |

---

## Open Questions
- [x] Which LLM provider? → Gemini (free tier), with paid Gemini as fallback
- [x] Multi-language? → Vietnamese-first, English inside vocab content; M7 adds UI VN/EN toggle
- [x] Post-M5 user feedback (UI/UX bland, Firebase durability, i18n, killer features) — decided 2026-04-18 refinement
- [x] Which new killer feature to prioritize? → Reading Lab only (Speaking/Mock/Predictor/Squads deferred)
- [x] DB migration target? → Postgres via Supabase; user data only; groups/challenges stay on Firestore
- [ ] Public VPS hosting move (needed for M10 DR drill on independent host) — deferred to M10 planning
- [ ] Payment rail / billing stack for Pro tier — unaddressed (freemium $5–8/month target from initial roadmap)
- [ ] When to upgrade from gTTS to Google Cloud TTS for listening exercises?
- [ ] Should speaking feedback include a simulated IELTS band score or just qualitative feedback? (parked — Speaking Coach deferred)

---

## Agent Log

| Timestamp | Agent | Action |
|-----------|-------|--------|
| — | — | Project initialized |
| 2026-04-13 | Orchestrator | Sprint started: Q2 2026 roadmap (Q2-3 → Q2-1 → Q2-2) |
| 2026-04-13-15 | Various | GH#1-8 completed (see Done section) |
| 2026-04-16 | PO + Designer + Architect + QA + TechLead + Developer | Refinement meeting: defined 5 killer features, 6 milestones (M0-M5), 51 GitHub issues created (#9-#59) |
| 2026-04-17 | Various | M0–M5 delivered (GH#9–#91) |
| 2026-04-18 | PO + Designer + Architect + QA + TechLead + Developer | Refinement meeting 2: post-M5 user feedback (UI/UX, DB durability, i18n). 5 new milestones M6–M10 defined; Reading Lab is the only new feature. 52 GitHub issues created (#92–#143): 5 Epics, 10 ADRs, 3 UX specs, 5 QA plans, 29 user stories. Other killer features (Speaking/Mock/Predictor/Squads) deferred. |
| 2026-04-18 | Orchestrator | M6 sprint kickoff: 3-wave plan posted on Epic #92; all 11 M6 tickets (5 plumbing + 6 stories) + 4 supporting docs (ADRs #97/#98, UX #100, QA #103) stamped with Sprint Kickoff comments, owner, deps, exit criteria. Wave 1 labeled `status:in-progress`; Waves 2–3 labeled `status:blocked`. |
