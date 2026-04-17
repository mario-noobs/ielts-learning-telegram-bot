import threading
import time
from collections import defaultdict

# Per-user command timestamps: {user_id: [timestamp, ...]}
_user_commands: dict[int, list[float]] = defaultdict(list)
_lock = threading.Lock()

# Limits
RATE_LIMIT_PER_MINUTE = 5
RATE_LIMIT_PER_HOUR = 30

# Commands that consume AI resources
AI_COMMANDS = {"mydaily", "quiz", "review", "write", "translate", "word"}


def check_rate_limit(user_id: int, command: str) -> tuple[bool, str]:
    """Check if a user is rate-limited for a given command.

    Returns:
        (allowed, message) — allowed=True means proceed,
        allowed=False means blocked with a friendly message.
    """
    if command not in AI_COMMANDS:
        return True, ""

    now = time.time()

    with _lock:
        # Clean entries older than 1 hour
        _user_commands[user_id] = [
            t for t in _user_commands[user_id] if now - t < 3600
        ]

        timestamps = _user_commands[user_id]

        # Check per-minute limit
        recent_minute = [t for t in timestamps if now - t < 60]
        if len(recent_minute) >= RATE_LIMIT_PER_MINUTE:
            wait = int(60 - (now - recent_minute[0]))
            return False, (
                f"\u23f3 Slow down! You've used {RATE_LIMIT_PER_MINUTE} AI commands "
                f"in the last minute.\n"
                f"Wait {wait}s before trying again.\n\n"
                f"Non-AI commands like /mywords, /progress, /settings still work!"
            )

        # Check per-hour limit
        if len(timestamps) >= RATE_LIMIT_PER_HOUR:
            wait = int(3600 - (now - timestamps[0]))
            minutes = wait // 60
            return False, (
                f"\u23f3 Hourly limit reached ({RATE_LIMIT_PER_HOUR} AI commands/hour).\n"
                f"Wait ~{minutes} min before trying again.\n\n"
                f"Non-AI commands like /mywords, /progress, /settings still work!"
            )

        # Record this command
        _user_commands[user_id].append(now)
        return True, ""
