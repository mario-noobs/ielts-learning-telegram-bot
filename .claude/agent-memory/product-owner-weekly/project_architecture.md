---
name: Architecture Constraints
description: Hard limits and key patterns in the bot that all feature proposals must respect
type: project
---

**Why:** Free-tier ceilings are the primary product constraint. Every feature must be designed around them.

## Gemini (gemini-2.5-flash)
- 15 RPM hard limit, 1500 req/day
- Per-user rate limit: 5/min, 30/hour (enforced in rate_limit_service.py)
- On 429: RateLimitError raised immediately, no retry
- Expensive operations: vocab generation (~1 req), quiz batch (~1 req for 5 Qs), review batch (~1 req for 10 Qs), writing feedback (1 req), translate (2 req — detect + translate)
- translate_text() uses 2 Gemini calls (language detection + translation) — this is a known cost hotspot

## Firestore
- 50K reads/day, 20K writes/day
- Writes are the binding constraint
- Each word added = 2 writes (vocabulary doc + user total_words increment)
- Each quiz answer = 2 writes (quiz_history doc + user stats update)
- Daily greeting job reads ALL users every morning — grows with user count

## Architecture rules (must not violate)
- No web server — polling only (run_polling)
- All Gemini calls go through ai_service.py — never call genai directly from handlers
- Three-layer: handlers/ -> services/ -> prompts/
- Prompt templates are Python format strings in prompts/ directory
- safe_send() in bot/utils.py handles Markdown fallback and 4096-char splitting
- Session state lives in context.bot_data (group-scoped) or context.user_data (user-scoped) — NOT Firestore
- APScheduler (AsyncIOScheduler) for cron jobs, timezone Asia/Ho_Chi_Minh
- Scheduler jobs are per-group, restored from Firebase on startup via restore_group_schedules()

## Daily Gemini budget breakdown (estimated, 10 active users)
- Scheduled daily vocab: 1 req/group/day (batched for whole group)
- Scheduled daily challenge: 1 req/group/day
- Per-user mydaily: up to 10 req/day
- Per-user quiz: up to 10 req/day (1 batch per session)
- Per-user review: up to 10 req/day (1 batch per session)
- Per-user write/translate: variable, rate-limited
- Approximate baseline at 10 users: ~40-50 req/day — well within 1500
- At 200 users: ~400-600 req/day — still safe but approaching 40% of ceiling

**How to apply:** When proposing features, always calculate req/day at N=10, N=50, N=200 users. Flag if N=200 exceeds ~1000 req/day (leaves no headroom for bursts).
