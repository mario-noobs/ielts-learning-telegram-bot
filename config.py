import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-lite"

# Firebase
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")

# Support base64-encoded Firebase credentials for containerized deploys
FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON")

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


def local_date_str() -> str:
    """Return today's date in the configured timezone as YYYY-MM-DD."""
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")
