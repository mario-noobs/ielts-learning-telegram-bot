# TASKS.md — IELTS Telegram Bot

> Shared context file for all agents. Each agent reads this before acting and updates it after completing work.
> You (the human) are the final approver before any section moves forward.

---

## Current Sprint Goal
Ship Q2 of the 2026 roadmap (Vocabulary depth): Q2-3 Smart Daily Greeting → Q2-1 `/word` Enrichment → Q2-2 `/topic` Clusters. Foundation for Q3 pronunciation features.

---

## Status Board

### In Progress
_(move stories here when implementation begins)_

### In Review
_(move stories here when review begins)_

### Done
- GH#3 — Cache-on-generate for AI vocab (Q2-1 follow-up) — https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/3
- GH#2 — /word Enrichment (Q2-1) — https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/2
- GH#1 — Smart Daily Greeting (Q2-3) — https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/1

---

## Backlog
_(PO writes stories here)_

---

## Architecture Decisions
_(Architect documents ADRs here)_

### ADR-1: Async-first architecture
**Status:** Accepted
**Context:** python-telegram-bot v20 is fully async; mixing sync/async causes deadlocks.
**Decision:** All handlers, services, and DB calls must be async. Use `asyncpg` or `aiosqlite`.
**Consequences:** Slightly steeper learning curve; eliminates entire class of concurrency bugs.

- GH#1 ADR — Inline `_pick_greeting_line()` helper in scheduler_service with 5-rule priority chain, 0 Gemini calls, ≤2 extra Firestore reads, no new fields
- GH#2 ADR — New `word_service.py` with Firestore `enriched_words/{word}` cache (top-level `ipa` for Q3-1), band-bucketed examples with partial regen, two prompt templates, drop-in replacement of freeform `/word`
- GH#3 ADR — Background `enrich_words_background()` in word_service.py, fired via `asyncio.create_task` from 4 entry points after daily message dispatch, sequential iteration with 4.5s sleep for Gemini rate-limit safety, cache pre-filter to skip enriched words, break-on-RateLimitError

---

## Open Questions
_(Any agent can add a question here; You resolve them)_

- [ ] Which LLM provider are we using in production? (OpenAI / Anthropic / other)
- [ ] Do we need multi-language support for the bot UI (Vietnamese + English)?
- [ ] Should speaking feedback include a simulated IELTS band score or just qualitative feedback?

---

## Agent Log
_(Each agent appends a one-line entry when they complete work)_

| Timestamp | Agent | Action |
|-----------|-------|--------|
| — | — | Project initialized |
| 2026-04-13 | Orchestrator | Sprint started: Q2 2026 roadmap (Q2-3 → Q2-1 → Q2-2) |
| 2026-04-13 | Architect | ADR-2 posted on GH#1: Smart Daily Greeting personalization architecture |
| 2026-04-13 | Reviewer | GH#1 APPROVED + closed |
| 2026-04-13 | Reviewer | GH#2 APPROVED + closed |
| 2026-04-13 | Reviewer | GH#3 APPROVED + closed |
