# TASKS.md — IELTS Telegram Bot

> Shared context file for all agents. Each agent reads this before acting and updates it after completing work.
> You (the human) are the final approver before any section moves forward.

---

## Current Sprint Goal
_Define your sprint goal here — e.g. "Ship the vocabulary handler end-to-end"_

---

## Status Board

### In Progress
_(move stories here when work starts)_

### In Review
_(move stories here when code is written, awaiting Reviewer)_

### Done
_(move stories here after Reviewer approves)_

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
