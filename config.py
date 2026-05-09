import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Public-facing bot username (no @, e.g. "ielts_bot"). Required for the
# US-M12.2 web→TG deep-link `https://t.me/<BOT_USERNAME>?start=link_<token>`.
BOT_USERNAME = os.getenv("BOT_USERNAME")
# Public web origin used by the US-M12.2 TG→web deep-link
# `${WEB_BASE_URL}/link?token=<token>`. Defaults to the local dev origin
# so emulator + dev-server flows work without extra config.
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "http://localhost:5173")

# Google Gemini — single-provider legacy, now wrapped by services/ai/.
# Kept for the bot's direct callers + last-resort fallback in the chain.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-lite"

# Groq — Phase 1 primary AI provider (US-#221). Free tier offers
# 1,000 RPD on llama-3.3-70b-versatile + 14,400 RPD on llama-3.1-8b
# and gemma2-9b-it on the same key — ~30K RPD total headroom.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# Default routing chains seeded into ai_routing_config on first startup.
# Admin can override per-plan via the table; the in-memory router cache
# refreshes every AI_ROUTING_CACHE_TTL_SECONDS (60s, mirroring the
# feature_flag_service pattern).
AI_ROUTING_CACHE_TTL_SECONDS = int(os.getenv("AI_ROUTING_CACHE_TTL_SECONDS", "60"))

# Firebase
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")

# Support base64-encoded Firebase credentials for containerized deploys
FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON")

# Firebase emulator mode (local dev only)
# When FIRESTORE_EMULATOR_HOST / FIREBASE_AUTH_EMULATOR_HOST are set in the
# environment, the firebase-admin SDK auto-routes to the emulator and we skip
# real credentials. See services/firebase_service._get_db().
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST")
FIREBASE_AUTH_EMULATOR_HOST = os.getenv("FIREBASE_AUTH_EMULATOR_HOST")
FIREBASE_EMULATOR_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "ielts-bot-dev")
USE_FIREBASE_EMULATOR = bool(FIRESTORE_EMULATOR_HOST or FIREBASE_AUTH_EMULATOR_HOST)

# Bot defaults
DEFAULT_DAILY_TIME = os.getenv("DEFAULT_DAILY_TIME", "08:00")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Ho_Chi_Minh")
DEFAULT_BAND_TARGET = float(os.getenv("DEFAULT_BAND_TARGET", "7.0"))
DEFAULT_WORD_COUNT = int(os.getenv("DEFAULT_WORD_COUNT", "10"))

# Rate limiting
GEMINI_RPM_LIMIT = 15
GEMINI_RETRY_DELAY = 5  # seconds

# Gemini gate — background enrichment budget
GEMINI_BACKGROUND_RPM = 2          # max background calls per 60 s window
GEMINI_BACKGROUND_SLEEP = 30       # seconds between background enrichment calls

# Gemini daily quota (free tier)
GEMINI_DAILY_QUOTA = 1500                  # informational — actual API limit
GEMINI_DAILY_BACKGROUND_CAP = 1200         # 80% — stop background to reserve for foreground

# SRS defaults
SRS_INITIAL_INTERVAL = 1  # days
SRS_INITIAL_EASE = 2.5
SRS_MIN_EASE = 1.3
SRS_MAX_EASE = 3.0

# Quiz
QUIZ_TYPES = ["multiple_choice", "fill_blank", "synonym_antonym", "paraphrase"]

# Challenge defaults (overridable per-group via /groupsettings)
DEFAULT_CHALLENGE_TIME = os.getenv("DEFAULT_CHALLENGE_TIME", "08:30")
DEFAULT_CHALLENGE_QUESTION_COUNT = int(os.getenv("DEFAULT_CHALLENGE_QUESTION_COUNT", "5"))
DEFAULT_CHALLENGE_DEADLINE_MINUTES = int(os.getenv("DEFAULT_CHALLENGE_DEADLINE_MINUTES", "60"))

# Legacy aliases (used by code that hasn't switched to per-group yet)
CHALLENGE_QUESTION_COUNT = DEFAULT_CHALLENGE_QUESTION_COUNT
CHALLENGE_DEADLINE_MINUTES = DEFAULT_CHALLENGE_DEADLINE_MINUTES


# Web API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# Feature flags — see services/feature_flag_service.py and scripts/flags.py.
# Tests may override this to 0 to force cache misses.
FEATURE_FLAG_CACHE_TTL_SECONDS = int(os.getenv("FEATURE_FLAG_CACHE_TTL_SECONDS", "60"))

# Observability
ENV = os.getenv("ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Postgres (self-hosted) — user core doc + admin tables.
# See services/db/__init__.py for the lazy-init engine + session factory.
DATABASE_URL = os.getenv("DATABASE_URL")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))


def local_date_str() -> str:
    """Return today's date in the configured timezone as YYYY-MM-DD."""
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")
