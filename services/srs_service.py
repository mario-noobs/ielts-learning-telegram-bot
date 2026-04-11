from datetime import datetime, timedelta, timezone

import config


def calculate_next_review(word_data: dict, is_correct: bool) -> dict:
    """Calculate next review date using SM-2 algorithm.

    Args:
        word_data: Current word data with srs_interval, srs_ease, srs_reps
        is_correct: Whether the user answered correctly

    Returns:
        Dict with updated SRS fields to save to Firestore
    """
    interval = word_data.get("srs_interval", config.SRS_INITIAL_INTERVAL)
    ease = word_data.get("srs_ease", config.SRS_INITIAL_EASE)
    reps = word_data.get("srs_reps", 0)
    times_correct = word_data.get("times_correct", 0)
    times_incorrect = word_data.get("times_incorrect", 0)

    if is_correct:
        reps += 1
        times_correct += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 3
        else:
            interval = round(interval * ease)
        ease = min(ease + 0.1, config.SRS_MAX_EASE)
    else:
        reps = 0
        times_incorrect += 1
        interval = 1
        ease = max(ease - 0.2, config.SRS_MIN_EASE)

    next_review = datetime.now(timezone.utc) + timedelta(days=interval)

    return {
        "srs_interval": interval,
        "srs_ease": round(ease, 2),
        "srs_next_review": next_review,
        "srs_reps": reps,
        "times_correct": times_correct,
        "times_incorrect": times_incorrect,
    }


def get_word_strength(word_data: dict) -> str:
    """Return a human-readable strength label for a word."""
    reps = word_data.get("srs_reps", 0)
    interval = word_data.get("srs_interval", 1)

    if reps == 0:
        return "New"
    elif interval <= 1:
        return "Weak"
    elif interval <= 7:
        return "Learning"
    elif interval <= 30:
        return "Good"
    else:
        return "Mastered"


def get_strength_emoji(strength: str) -> str:
    emojis = {
        "New": "\U0001f195",       # NEW
        "Weak": "\U0001f534",      # red circle
        "Learning": "\U0001f7e1",  # yellow circle
        "Good": "\U0001f7e2",      # green circle
        "Mastered": "\u2b50",      # star
    }
    return emojis.get(strength, "\u26aa")
