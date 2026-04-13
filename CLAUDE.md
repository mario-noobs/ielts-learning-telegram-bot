# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Telegram bot for IELTS exam preparation. Works in group chats (daily vocabulary, challenges, leaderboards) and private DMs (quizzes, SRS review, writing feedback, translation). All external services use free tiers.

## Running the Bot

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in keys
python main.py         # starts polling, no web server
```

Required environment variables: `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`. Also needs `firebase_credentials.json` in the project root.

There are no tests, no linter configuration, and no build step.

## Architecture

**Entry point**: `main.py` registers all Telegram command/callback/message handlers on the `python-telegram-bot` application, starts the APScheduler, then runs polling.

**Three-layer structure**:
- `bot/handlers/` — Telegram command handlers. Each file handles one feature area (start, vocabulary, quiz, challenge, review, writing, leaderboard, progress, settings). Handlers call into services and format responses for Telegram.
- `services/` — Business logic. `ai_service.py` is the central AI layer wrapping Google Gemini; all other services call it for generation. `firebase_service.py` is the single data access layer for Firestore. Other services: `vocab_service`, `quiz_service`, `challenge_service`, `leaderboard_service`, `srs_service` (SM-2 algorithm), `tts_service` (gTTS audio), `scheduler_service` (APScheduler cron jobs for daily posts).
- `prompts/` — Prompt templates as Python format strings, imported lazily by `ai_service.py`.

**Key patterns**:
- `ai_service.generate()` runs Gemini calls via `asyncio.to_thread`. `generate_json()` wraps it with markdown code block stripping and JSON parsing. On 429 errors, it raises `RateLimitError` immediately (no retry); other errors retry with backoff.
- `firebase_service` uses lazy-initialized module-level singletons (`_db`). Firestore collections: `users` (with subcollections `vocabulary`, `quiz_history`, `writing_history`, `daily_words`), `groups` (with subcollections `daily_words`, `challenges`).
- `bot/utils.py` provides `safe_send()` which sends Markdown and falls back to plain text on parse errors, plus message splitting for Telegram's 4096-char limit.
- The `/start` command uses `ConversationHandler` for a multi-step onboarding flow (band selection → topic selection → profile creation).
- Scheduler jobs are per-group: daily vocab posts at the configured time, daily challenge 30 minutes later. On startup, `restore_group_schedules()` re-registers all group jobs from Firebase. A global daily greeting job sends DM reminders at 07:00 Vietnam time.
- `rate_limit_service.py` provides in-memory per-user rate limiting (5/min, 30/hour) for AI-heavy DM commands. Non-AI commands are not limited.
- Group band (`default_band`) and user band (`target_band`) are separate. Group `/daily` uses group band; DM `/mydaily` uses user's personal band.

## External Services

| Service | SDK | Rate Limits |
|---------|-----|-------------|
| Telegram Bot API | `python-telegram-bot` 21+ | Unlimited |
| Google Gemini (`gemini-2.5-flash`) | `google-generativeai` | 15 RPM, 1500 req/day (free tier) |
| Firebase Firestore | `firebase-admin` | 50K reads + 20K writes/day (free tier) |
| Google TTS | `gTTS` | No hard limit |

## Config

All configuration lives in `config.py`, loaded from `.env` via `python-dotenv`. SRS parameters, quiz types, challenge settings, and rate limit constants are hardcoded there — not in env vars.

## Deployment

Pushing to `main` triggers `.github/workflows/deploy.yml`, which SSHes into the production VPS and runs `git pull` + `pip install` + `systemctl restart ielts-bot`. The workflow uses GitHub Actions secrets `SSH_HOST`, `SSH_USER`, and `SSH_PRIVATE_KEY` — no application secrets (Telegram token, Gemini key, Firebase credentials) ever leave the host.

For the full deploy recipe, initial server setup, rollback procedure, and troubleshooting guide, see `.claude/skills/deploy/SKILL.md`.

To deploy manually: `ssh ielts@<host>`, then `cd /home/ielts/ielts-bot && git pull origin main && ./venv/bin/pip install -r requirements.txt --quiet && sudo systemctl restart ielts-bot`.
