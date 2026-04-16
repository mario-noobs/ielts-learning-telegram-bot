# TASKS.md — IELTS Web App + Telegram Bot

> Shared context file for all agents. Each agent reads this before acting and updates it after completing work.
> You (the human) are the final approver before any section moves forward.

---

## Current Sprint Goal
**M0: Foundation** — Extract FastAPI API layer from existing bot, add Firebase Auth, tests, CI, and public deploy. Safety net before any new features.

---

## Roadmap (2026)

| Milestone | Due | Epic | Status |
|-----------|-----|------|--------|
| M0: Foundation | 2026-05-15 | GH#9 | **Active** |
| M1: Vocabulary Universe | 2026-06-15 | GH#10 | Backlog |
| M2: Writing Lab | 2026-07-31 | GH#11 | Backlog |
| M3: Listening Gym | 2026-09-15 | GH#12 | Backlog |
| M4: Smart Daily Plan | 2026-10-15 | GH#13 | Backlog |
| M5: Band Progress Map | 2026-11-15 | GH#14 | Backlog |

---

## Status Board

### M0: Foundation — In Progress

| # | Story | Size | Status | Depends |
|---|-------|------|--------|---------|
| GH#33 | US-0.1: Service layer tests | M | Ready | — |
| GH#34 | US-0.2: CI pipeline (ruff + pytest) | S | Ready | US-0.1 |
| GH#35 | US-0.3: FastAPI skeleton + health | S | Ready | — |
| GH#36 | US-0.4: Firebase Auth middleware | M | Ready | US-0.3 |
| GH#37 | US-0.5: Async Firestore wrapper | S | Ready | US-0.3 |
| GH#38 | US-0.6: Frontend scaffold (React+Vite) | M | Ready | US-0.4 |
| GH#39 | US-0.7: Docker + deploy | S | Ready | US-0.3, US-0.6 |

**Parallel tracks:**
- Track A: US-0.3 → US-0.4 → US-0.5 (API + Auth)
- Track B: US-0.1 → US-0.2 (Tests + CI)
- Track C: US-0.6 → US-0.7 (Frontend + Deploy, starts mid-sprint)

### Done (previous sprints)
- GH#8 — Daily challenge state lost on restart (Firestore-backed redesign)
- GH#7 — Deployment skill + auto-deploy on push to main
- GH#6 — Fold enrichment into vocab generation (10x Gemini cost cut)
- GH#5 — Bug: RPD exhaustion + background keeps retrying
- GH#4 — Bug: enrichment burns RPM quota
- GH#3 — Cache-on-generate for AI vocab (Q2-1 follow-up)
- GH#2 — /word Enrichment (Q2-1)
- GH#1 — Smart Daily Greeting (Q2-3)

---

## Backlog

### M1: Vocabulary Universe (GH#10)
| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#40 | US-1.1: Vocabulary API (daily, list, detail) | M | M0 |
| GH#41 | US-1.2: SRS review API | S | US-1.1 |
| GH#42 | US-1.3: Daily vocabulary page | M | US-1.1 |
| GH#43 | US-1.4: Flashcard review page | M | US-1.2 |
| GH#44 | US-1.5: Topic browser + vocab home | M | US-1.1 |
| GH#45 | US-1.6: Audio pronunciation | S | US-1.1 |

### M2: Writing Lab (GH#11)
| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#46 | US-2.1: IELTS 4-criteria scoring API | M | M1 |
| GH#47 | US-2.2: Essay editor + word count | M | US-2.1 |
| GH#48 | US-2.3: Score panel + annotations | M | US-2.2 |
| GH#49 | US-2.4: Revision workflow + history | M | US-2.3 |

### M3: Listening Gym (GH#12)
| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#50 | US-3.1: Audio content service + prompts | M | M2 |
| GH#51 | US-3.2: Listening API endpoints | M | US-3.1 |
| GH#52 | US-3.3: Audio player + dictation page | M | US-3.2 |
| GH#53 | US-3.4: Gap fill + comprehension pages | M | US-3.3 |

### M4: Smart Daily Plan (GH#13)
| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#54 | US-4.1: Weakness analysis + plan gen | M | M3 |
| GH#55 | US-4.2: Home screen + task routing | M | US-4.1 |
| GH#56 | US-4.3: Exam countdown + streak settings | S | US-4.2 |

### M5: Band Progress Map (GH#14)
| # | Story | Size | Depends |
|---|-------|------|---------|
| GH#57 | US-5.1: Band estimation + snapshots | M | M4 |
| GH#58 | US-5.2: Progress dashboard + charts | M | US-5.1 |
| GH#59 | US-5.3: AI coaching recommendations | S | US-5.1 |

---

## Architecture Decisions

### Existing (Telegram bot)
- ADR-1: Async-first architecture (accepted)
- GH#1-8 ADRs: See closed issues for details

### M0: Foundation ADRs
| # | ADR | Status |
|---|-----|--------|
| GH#15 | ADR-M0-1: API Framework — FastAPI | Proposed |
| GH#16 | ADR-M0-2: Auth — Firebase Auth + Telegram Bridge | Proposed |
| GH#17 | ADR-M0-3: Session Storage — Firestore subcollection | Proposed |
| GH#18 | ADR-M0-4: Service Layer — Transport-agnostic refactoring | Proposed |
| GH#19 | ADR-M0-5: Deployment — Docker + Railway | Proposed |
| GH#20 | ADR-M0-6: Rate Limiting — Firestore counters | Proposed |

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

---

## Open Questions
- [x] Which LLM provider? → Gemini (free tier), with paid Gemini as fallback
- [x] Multi-language? → Vietnamese-first, English only inside vocab content
- [ ] Should speaking feedback include a simulated IELTS band score or just qualitative feedback?
- [ ] Railway vs Fly.io vs DigitalOcean for hosting? (ADR-M0-5 proposes Railway)
- [ ] When to upgrade from gTTS to Google Cloud TTS for listening exercises?

---

## Agent Log

| Timestamp | Agent | Action |
|-----------|-------|--------|
| — | — | Project initialized |
| 2026-04-13 | Orchestrator | Sprint started: Q2 2026 roadmap (Q2-3 → Q2-1 → Q2-2) |
| 2026-04-13-15 | Various | GH#1-8 completed (see Done section) |
| 2026-04-16 | PO + Designer + Architect + QA + TechLead + Developer | Refinement meeting: defined 5 killer features, 6 milestones (M0-M5), 51 GitHub issues created (#9-#59) |
