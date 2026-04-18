# IELTS Study Bot

Telegram group bot for IELTS exam preparation (target 7.0+). AI-powered vocabulary learning, quizzes, writing feedback, and translation — all free.

## Features

**Group chat:**
- `/daily` — 10 IELTS words with EN/VI definitions, examples, pronunciation
- `/audio <number>` — Hear word pronunciation
- `/challenge` — Daily 5-question challenge with leaderboard
- `/leaderboard` — Group rankings (words, accuracy, streak, wins)
- `/results` — Challenge results
- `/newdaily` — Force regenerate today's vocab
- `/groupsettings` — Change group band, topics, daily time

**Private DM:**
- `/quiz` — 5-question quiz (MC + fill-in-blank)
- `/review` — SRS spaced repetition review
- `/word <word>` — Look up any word with EN/VI explanation
- `/write <text>` — AI writing feedback (IELTS examiner style)
- `/translate <text>` — Auto-detect and translate EN/VI
- `/mywords` — Browse personal vocabulary
- `/progress` — Stats, streak, estimated band level
- `/settings` — Personal preferences

## Tech Stack (All Free)

| Component | Choice | Free Tier |
|-----------|--------|-----------|
| Bot | Telegram Bot API (python-telegram-bot) | Unlimited |
| AI | Google Gemini API (gemini-2.5-flash) | 15 RPM, 1,500 req/day |
| Database | Firebase Firestore | 50K reads + 20K writes/day |
| TTS | gTTS (Google Text-to-Speech) | Unlimited |
| Scheduler | APScheduler | - |

## Quickstart (local dev)

Spins up Firebase emulators + API + web with seeded demo data. macOS / Linux
only. Requires Docker, Python 3.11+, and Node 20+.

```bash
make install
make dev
# visit http://localhost:5173  (login demo@ielts.test / demo1234)
# emulator UI at http://localhost:4000
```

`make help` lists all targets. The Telegram bot is NOT started by `make dev`
because it needs a real bot token — run `make bot` explicitly if you want it.

Seeds live under `seeds/` and are deterministic — re-running `make seed`
overwrites docs in place, never duplicates.

## Setup (production / real Telegram bot)

### 1. Get API keys

- **Telegram Bot Token**: Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy token
- **Gemini API Key**: https://aistudio.google.com/apikey → "Create API key in new project"
- **Firebase**: https://console.firebase.google.com → Create project → Enable Firestore → Project Settings → Service Accounts → Generate private key → save as `firebase_credentials.json`

### 2. Install and run

```bash
git clone https://github.com/mario-noobs/ielts-bot.git
cd ielts-bot
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
python main.py
```

### 3. Add bot to Telegram group

1. Open your bot in Telegram
2. Add it to a group
3. Type `/start` to register

## Project Structure

```
ielts-bot/
├── main.py              # Bot entry point
├── config.py            # Environment config
├── bot/
│   ├── handlers/        # Command handlers
│   ├── callbacks/       # Inline button handlers
│   └── utils.py         # Safe send, message splitting
├── services/            # Business logic
│   ├── ai_service.py    # Gemini API
│   ├── firebase_service.py
│   ├── quiz_service.py
│   ├── srs_service.py   # SM-2 spaced repetition
│   └── scheduler_service.py
├── prompts/             # AI prompt templates
└── data/
    └── ielts_topics.json
```

## Notes

- Free Gemini tier: don't enable billing on the Google Cloud project
- If you hit rate limits, the bot shows which limit (RPM/RPD/TPM) and wait time
- Daily vocab and challenges auto-post at the scheduled time (default 08:00 Vietnam time)
- SRS uses the SM-2 algorithm (same as Anki)
