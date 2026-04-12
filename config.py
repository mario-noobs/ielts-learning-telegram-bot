import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Google Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

# Firebase
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")

# Bot defaults
DEFAULT_DAILY_TIME = os.getenv("DEFAULT_DAILY_TIME", "08:00")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Ho_Chi_Minh")
DEFAULT_BAND_TARGET = float(os.getenv("DEFAULT_BAND_TARGET", "7.0"))
DEFAULT_WORD_COUNT = int(os.getenv("DEFAULT_WORD_COUNT", "10"))

# Rate limiting
GEMINI_RPM_LIMIT = 15
GEMINI_RETRY_DELAY = 5  # seconds

# SRS defaults
SRS_INITIAL_INTERVAL = 1  # days
SRS_INITIAL_EASE = 2.5
SRS_MIN_EASE = 1.3
SRS_MAX_EASE = 3.0

# Quiz
QUIZ_TYPES = ["multiple_choice", "fill_blank", "synonym_antonym", "paraphrase"]
CHALLENGE_QUESTION_COUNT = 5
CHALLENGE_DEADLINE_MINUTES = 60


def local_date_str() -> str:
    """Return today's date in the configured timezone as YYYY-MM-DD."""
    tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")
