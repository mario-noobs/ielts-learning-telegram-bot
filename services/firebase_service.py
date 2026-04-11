import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
from typing import Optional

import config


_db = None


def _get_db():
    global _db
    if _db is None:
        cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
    return _db


# ─── User Operations ───────────────────────────────────────────────

def get_user(telegram_id: int) -> Optional[dict]:
    doc = _get_db().collection("users").document(str(telegram_id)).get()
    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None


def create_user(telegram_id: int, name: str, username: str = "",
                group_id: int = None, target_band: float = 7.0,
                topics: list = None) -> dict:
    now = datetime.now(timezone.utc)
    user_data = {
        "name": name,
        "username": username or "",
        "group_id": group_id,
        "target_band": target_band,
        "topics": topics or ["education", "environment", "technology"],
        "daily_time": config.DEFAULT_DAILY_TIME,
        "timezone": config.DEFAULT_TIMEZONE,
        "streak": 0,
        "last_active": now,
        "total_words": 0,
        "total_quizzes": 0,
        "total_correct": 0,
        "challenge_wins": 0,
        "created_at": now,
    }
    _get_db().collection("users").document(str(telegram_id)).set(user_data)
    return {"id": str(telegram_id), **user_data}


def update_user(telegram_id: int, data: dict):
    _get_db().collection("users").document(str(telegram_id)).update(data)


def get_all_users_in_group(group_id: int) -> list[dict]:
    docs = (_get_db().collection("users")
            .where("group_id", "==", group_id)
            .stream())
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def update_streak(telegram_id: int):
    user = get_user(telegram_id)
    if not user:
        return
    now = datetime.now(timezone.utc)
    last = user.get("last_active")
    if last:
        if hasattr(last, "timestamp"):
            last = last
        delta = (now.date() - last.date()).days if hasattr(last, "date") else 1
        if delta == 1:
            new_streak = user.get("streak", 0) + 1
        elif delta == 0:
            new_streak = user.get("streak", 0)
        else:
            new_streak = 1
    else:
        new_streak = 1
    update_user(telegram_id, {"streak": new_streak, "last_active": now})


# ─── Vocabulary Operations ─────────────────────────────────────────

def add_word_to_user(telegram_id: int, word_data: dict) -> str:
    now = datetime.now(timezone.utc)
    word_doc = {
        **word_data,
        "srs_interval": config.SRS_INITIAL_INTERVAL,
        "srs_ease": config.SRS_INITIAL_EASE,
        "srs_next_review": now,
        "srs_reps": 0,
        "times_correct": 0,
        "times_incorrect": 0,
        "added_at": now,
    }
    doc_ref = (_get_db().collection("users").document(str(telegram_id))
               .collection("vocabulary").document())
    doc_ref.set(word_doc)

    # Increment total_words
    user_ref = _get_db().collection("users").document(str(telegram_id))
    user_ref.update({"total_words": firestore.Increment(1)})

    return doc_ref.id


def get_user_vocabulary(telegram_id: int, limit: int = 50) -> list[dict]:
    docs = (_get_db().collection("users").document(str(telegram_id))
            .collection("vocabulary")
            .order_by("added_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream())
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def get_user_word_list(telegram_id: int) -> list[str]:
    """Get just the word strings for deduplication."""
    docs = (_get_db().collection("users").document(str(telegram_id))
            .collection("vocabulary")
            .stream())
    return [doc.to_dict().get("word", "") for doc in docs]


def get_due_words(telegram_id: int, limit: int = 10) -> list[dict]:
    now = datetime.now(timezone.utc)
    docs = (_get_db().collection("users").document(str(telegram_id))
            .collection("vocabulary")
            .where("srs_next_review", "<=", now)
            .limit(limit)
            .stream())
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def update_word_srs(telegram_id: int, word_id: str, data: dict):
    (_get_db().collection("users").document(str(telegram_id))
     .collection("vocabulary").document(word_id).update(data))


def get_word_by_id(telegram_id: int, word_id: str) -> Optional[dict]:
    doc = (_get_db().collection("users").document(str(telegram_id))
           .collection("vocabulary").document(word_id).get())
    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None


# ─── Quiz History ──────────────────────────────────────────────────

def save_quiz_result(telegram_id: int, quiz_data: dict):
    now = datetime.now(timezone.utc)
    doc = {**quiz_data, "created_at": now}
    (_get_db().collection("users").document(str(telegram_id))
     .collection("quiz_history").document().set(doc))

    # Update user stats
    user_ref = _get_db().collection("users").document(str(telegram_id))
    user_ref.update({"total_quizzes": firestore.Increment(1)})
    if quiz_data.get("is_correct"):
        user_ref.update({"total_correct": firestore.Increment(1)})


def get_quiz_stats(telegram_id: int) -> dict:
    user = get_user(telegram_id)
    if not user:
        return {"total": 0, "correct": 0, "accuracy": 0}
    total = user.get("total_quizzes", 0)
    correct = user.get("total_correct", 0)
    accuracy = round((correct / total * 100), 1) if total > 0 else 0
    return {"total": total, "correct": correct, "accuracy": accuracy}


# ─── Writing History ───────────────────────────────────────────────

def save_writing(telegram_id: int, writing_data: dict):
    now = datetime.now(timezone.utc)
    doc = {**writing_data, "created_at": now}
    (_get_db().collection("users").document(str(telegram_id))
     .collection("writing_history").document().set(doc))


# ─── Group Operations ─────────────────────────────────────────────

def get_group_settings(group_id: int) -> Optional[dict]:
    doc = _get_db().collection("groups").document(str(group_id)).get()
    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None


def create_group(group_id: int, settings: dict = None):
    default = {
        "daily_time": config.DEFAULT_DAILY_TIME,
        "timezone": config.DEFAULT_TIMEZONE,
        "topics": ["education", "environment", "technology"],
        "default_band": config.DEFAULT_BAND_TARGET,
        "created_at": datetime.now(timezone.utc),
    }
    if settings:
        default.update(settings)
    _get_db().collection("groups").document(str(group_id)).set(default)


def update_group_settings(group_id: int, data: dict):
    _get_db().collection("groups").document(str(group_id)).update(data)


# ─── Daily Words (Group) ──────────────────────────────────────────

def save_daily_words(group_id: int, date_str: str, words: list, topic: str):
    doc = {
        "words": words,
        "topic": topic,
        "generated_at": datetime.now(timezone.utc),
    }
    (_get_db().collection("groups").document(str(group_id))
     .collection("daily_words").document(date_str).set(doc))


def get_daily_words(group_id: int, date_str: str) -> Optional[dict]:
    doc = (_get_db().collection("groups").document(str(group_id))
           .collection("daily_words").document(date_str).get())
    if doc.exists:
        return doc.to_dict()
    return None


# ─── Challenge (Group) ────────────────────────────────────────────

def save_challenge(group_id: int, date_str: str, questions: list):
    doc = {
        "questions": questions,
        "participants": {},
        "status": "active",
        "created_at": datetime.now(timezone.utc),
    }
    (_get_db().collection("groups").document(str(group_id))
     .collection("challenges").document(date_str).set(doc))


def get_challenge(group_id: int, date_str: str) -> Optional[dict]:
    doc = (_get_db().collection("groups").document(str(group_id))
           .collection("challenges").document(date_str).get())
    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None


def update_challenge_score(group_id: int, date_str: str,
                           user_id: int, score: int):
    doc_ref = (_get_db().collection("groups").document(str(group_id))
               .collection("challenges").document(date_str))
    doc_ref.update({f"participants.{user_id}": score})


def close_challenge(group_id: int, date_str: str):
    doc_ref = (_get_db().collection("groups").document(str(group_id))
               .collection("challenges").document(date_str))
    doc_ref.update({"status": "closed"})


# ─── Leaderboard ──────────────────────────────────────────────────

def get_leaderboard(group_id: int) -> list[dict]:
    users = get_all_users_in_group(group_id)
    for user in users:
        stats = get_quiz_stats(int(user["id"]))
        user["accuracy"] = stats["accuracy"]
    return sorted(users, key=lambda u: u.get("total_words", 0), reverse=True)
