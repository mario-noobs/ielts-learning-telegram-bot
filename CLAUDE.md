# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

An IELTS exam-prep platform with three surfaces sharing one Python core:

- **Web app** (`/web/`) — React + Vite + TypeScript + Tailwind. **The primary surface — active development happens here.** Vocab, daily words, flashcard review (SRS), quizzes, writing feedback, listening, reading lab, progress dashboard.
- **Web API** (`/api/`) — FastAPI backend the web app talks to. Auth via Firebase ID tokens.
- **Telegram bot** (`/bot/`, `main.py`) — Original surface, now in **maintenance mode**. Only touch bot code when explicitly asked.

All three call into shared `/services/` and `/prompts/` layers. External services are still free tier (Gemini, Firestore, gTTS).

## Running Locally

One-command dev (Firebase emulators + seed + API + web in parallel):

```bash
make install        # venv + pip + npm install
make dev            # web at :5173 (login demo@ielts.test / demo1234)
                    # API at :8000, emulator UI at :4000
make test           # pytest
make bot            # optional, requires real TELEGRAM_BOT_TOKEN
```

`make help` lists all targets. Seeds in `seeds/` are deterministic — re-running `make seed` overwrites in place.

Env (`.env`): `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN` (bot only). `firebase_credentials.json` is required for production but not for `make dev` (emulators).

## Architecture

### Web (`/web/`)

- React 18 + Vite + TypeScript + Tailwind, Radix UI primitives. Design system in `web/src/design-system/` and `web/design-system/`.
- Routing in `web/src/App.tsx`. Public: `/`, `/login`, `/pricing`, `/privacy`, `/terms`. Protected (Firebase auth): `/vocab`, `/review`, `/daily`, `/write`, `/listening`, `/reading`, `/progress`, `/settings`.
- Auth via `web/src/contexts/AuthContext.tsx` (Firebase Web SDK).
- i18n: `react-i18next` + ICU. **Default locale is EN; VN is the selectable alternate.** Bot stays VN-first. Bundles in `web/public/locales/{en,vi}/`. `npm run lint:locales` checks key parity.
- Storybook (`npm run storybook`); Vitest (`npm run test`).

### API (`/api/`)

- `api/main.py` — FastAPI factory. Routers: `health`, `auth`, `vocabulary`, `words`, `topics`, `quiz`, `review`, `audio`, `writing`, `listening`, `plan`, `progress`, `reading`.
- `api/auth.py` — `get_current_user` dependency verifies Firebase Bearer ID tokens via `firebase_admin.auth.verify_id_token`.
- `api/errors.py` — **Error-code API contract (US-M7.3).** Every error response is `{error: {code, params, http_status}}`. Codes are dotted strings (`reading.passage.not_found`) registered in the `ERR` registry. Frontend localizes via `errors.json` bundles — server never ships prose `detail`. Legacy `HTTPException` routes are bridged to provisional codes by status; new code should `raise ApiError(ERR.foo, **params)`.
- `api/middleware.py` — `RequestIDMiddleware` for correlated logs; `api/logging_config.py` configures structlog.
- `api/models/` — Pydantic schemas, one file per feature.

### Shared services (`/services/`)

- `ai_service.py` — Central Gemini wrapper. `generate()` runs via `asyncio.to_thread`; `generate_json()` strips markdown fences + parses JSON. 429 raises `RateLimitError` immediately (no retry); other errors retry with backoff. Surfaced through API as 429 in the contract shape.
- `firebase_service.py` — Single Firestore data-access layer with lazy `_db` singleton. Collections: `users` (subcollections `vocabulary`, `quiz_history`, `writing_history`, `daily_words`), `groups` (subcollections `daily_words`, `challenges`).
- `repositories/` — Newer DTO + protocol-based repository layer (`firestore/` impls). Prefer this for new code over touching `firebase_service` directly.
- `async_firebase.py` — Async wrappers for hot paths.
- `feature_flag_service.py` — Firestore-backed flags with 60s in-memory cache. Eval order: missing→False, kill-switch→False, `uid_allowlist`→True, no uid→`enabled`, else `sha256("{flag}:{uid}") % 100 < rollout_pct`. Admin via `scripts/flags.py`. No redeploy to toggle. Planned flags: `design_system_v2`, `reading_lab`. (Postgres dual-write flags removed — M8 pivoted to a pre-launch one-shot cutover, see ADR-M8-3.)
- Domain services: `vocab_service`, `quiz_service`, `srs_service` (SM-2), `writing_service`, `listening_service`, `reading_service`, `coaching_service`, `plan_service`, `progress_service`, `weakness_service`, `word_service`, `tts_service`, `leaderboard_service`, `challenge_service`, `scheduler_service`, `rate_limit_service`.

### Bot (`/bot/`, `main.py`) — maintenance mode

`main.py` registers `python-telegram-bot` handlers, starts APScheduler, polls. Per-group cron jobs for daily vocab + challenge; global 07:00 Vietnam-time DM greeting. `bot/utils.py:safe_send()` handles Markdown fallback + 4096-char splitting. `/start` is a `ConversationHandler` for onboarding. Group band (`default_band`) and user band (`target_band`) are separate. `rate_limit_service` enforces in-memory per-user limits (5/min, 30/hour) for AI-heavy DM commands.

### Tests

- Pytest in `tests/` (per-feature `test_api_*.py`, `test_*_service.py`). Run with `make test` or `pytest -q`.
- Web tests in `web/src/**/*.test.tsx` via Vitest.
- `scripts/validate_reading.py` validates the reading corpus.
- `scripts/gen_error_docs.py` generates docs from the `ERR` registry.

## External Services

| Service | SDK | Free tier |
|---------|-----|-----------|
| Telegram Bot API | `python-telegram-bot` 21+ | Unlimited |
| Google Gemini (`gemini-2.5-flash`) | `google-generativeai` | 15 RPM, 1500 req/day |
| Firebase Auth + Firestore | `firebase-admin`, `firebase` (web) | 50K reads + 20K writes/day |
| Google TTS | `gTTS` | No hard limit |

## Config

`config.py` loads from `.env` via `python-dotenv`. SRS params, quiz types, challenge settings, rate-limit constants, `CORS_ORIGINS` are hardcoded there — not env vars.

## Deployment

Manual. Production host sits on a private LAN (`192.168.x.x`) so GitHub runners can't reach it; push-triggered auto-deploy is disabled. `.github/workflows/deploy.yml` is `workflow_dispatch` only.

To deploy: `ssh ielts@<host>`, then `cd /home/ielts/ielts-bot && git pull origin main && ./venv/bin/pip install -r requirements.txt --quiet && sudo systemctl restart ielts-bot`.

For server setup, rollback, troubleshooting: `.claude/skills/deploy/SKILL.md`.


## Behavioral guidelines
Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.