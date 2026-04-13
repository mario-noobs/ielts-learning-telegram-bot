# TASKS.md — IELTS Telegram Bot

> Shared context file for all agents. Each agent reads this before acting and updates it after completing work.
> You (the human) are the final approver before any section moves forward.

---

## Current Sprint Goal
Ship Q2 of the 2026 roadmap (Vocabulary depth): Q2-3 Smart Daily Greeting → Q2-1 `/word` Enrichment → Q2-2 `/topic` Clusters. Foundation for Q3 pronunciation features.

---

## Status Board

### In Progress
_(move stories here when development begins)_

### In Review
_(move stories here when code is ready for review)_

### Done
- GH#6 — Fold enrichment into vocab generation (10x Gemini cost cut) — https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/6
- GH#5 — Bug: RPD exhaustion + background keeps retrying — https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/5
- GH#4 — Bug: enrichment burns RPM quota — https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/4
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
- GH#4 ADR — Process-wide `GeminiGate` in ai_service.py: sliding-window token bucket with priority kwarg, background capped at 2 RPM / 30s sleep, foreground unrestricted up to 15 RPM, asyncio.Lock-guarded
- GH#5 ADR — RPD-aware circuit breaker: daily-spend counter (80% cap for background), RPD 429 disables background until midnight UTC, new `BackgroundDisabled` exception for clean caller signaling
- GH#6 ADR — Expand GENERATE_VOCABULARY prompt to return all 11 enrichment fields per word, write to enriched_words cache inline via new `persist_generated_words()` helper, remove 3 background enrichment call sites (11 Gemini calls → 1)

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
| 2026-04-13 | Reviewer | GH#4 APPROVED + closed |
| 2026-04-13 | Reviewer | GH#5 APPROVED + closed |
| 2026-04-13 | Reviewer | GH#6 APPROVED + closed |
