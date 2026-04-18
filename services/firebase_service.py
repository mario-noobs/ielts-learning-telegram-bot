from datetime import datetime, timedelta, timezone
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

import config

_db = None


def _get_db():
    global _db
    if _db is None:
        json_b64 = getattr(config, 'FIREBASE_CREDENTIALS_JSON', None)
        if json_b64:
            import base64
            import json
            cred_dict = json.loads(base64.b64decode(json_b64))
            cred = credentials.Certificate(cred_dict)
        else:
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


def get_all_users() -> list[dict]:
    """Return all registered users."""
    docs = _get_db().collection("users").stream()
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


def get_user_vocabulary_page(telegram_id, limit: int = 20,
                              after_added_at: Optional[datetime] = None) -> list[dict]:
    """Cursor-paginated vocabulary fetch ordered by added_at DESC.

    Cursor is the `added_at` timestamp of the last item from the previous page.
    """
    query = (_get_db().collection("users").document(str(telegram_id))
             .collection("vocabulary")
             .order_by("added_at", direction=firestore.Query.DESCENDING))
    if after_added_at is not None:
        query = query.start_after({"added_at": after_added_at})
    docs = query.limit(limit).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def count_words_by_topic(telegram_id) -> dict[str, int]:
    """Return {topic_id: count} across the user's full vocabulary."""
    docs = (_get_db().collection("users").document(str(telegram_id))
            .collection("vocabulary")
            .stream())
    counts: dict[str, int] = {}
    for doc in docs:
        topic = doc.to_dict().get("topic") or ""
        if not topic:
            continue
        counts[topic] = counts.get(topic, 0) + 1
    return counts


# ─── Quiz Sessions (Web) ──────────────────────────────────────────

def save_quiz_session(telegram_id, session_id: str, questions: list[dict]) -> None:
    """Persist a quiz session with full (unsanitized) question docs."""
    doc = {
        "questions": questions,
        "answered_ids": [],
        "created_at": datetime.now(timezone.utc),
    }
    (_get_db().collection("users").document(str(telegram_id))
     .collection("quiz_sessions").document(session_id).set(doc))


def get_quiz_session(telegram_id, session_id: str) -> Optional[dict]:
    doc = (_get_db().collection("users").document(str(telegram_id))
           .collection("quiz_sessions").document(session_id).get())
    if doc.exists:
        return doc.to_dict()
    return None


def mark_session_question_answered(telegram_id, session_id: str,
                                    question_id: str) -> None:
    """Append question_id to the session's answered_ids array."""
    ref = (_get_db().collection("users").document(str(telegram_id))
           .collection("quiz_sessions").document(session_id))
    ref.update({"answered_ids": firestore.ArrayUnion([question_id])})


def get_mastered_words(telegram_id: int) -> list[dict]:
    """Return all vocabulary docs with srs_interval > 30 (mastered)."""
    docs = (_get_db().collection("users").document(str(telegram_id))
            .collection("vocabulary")
            .where("srs_interval", ">", 30)
            .stream())
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


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

    # Update user stats in a single atomic call
    user_ref = _get_db().collection("users").document(str(telegram_id))
    update_data = {"total_quizzes": firestore.Increment(1)}
    if quiz_data.get("is_correct"):
        update_data["total_correct"] = firestore.Increment(1)
    user_ref.update(update_data)


def get_latest_quiz(telegram_id: int) -> Optional[dict]:
    """Return the most recent quiz_history doc, or None."""
    docs = (_get_db().collection("users").document(str(telegram_id))
            .collection("quiz_history")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(1)
            .stream())
    results = [{"id": doc.id, **doc.to_dict()} for doc in docs]
    return results[0] if results else None


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
        "challenge_time": config.DEFAULT_CHALLENGE_TIME,
        "timezone": config.DEFAULT_TIMEZONE,
        "topics": ["education", "environment", "technology"],
        "default_band": config.DEFAULT_BAND_TARGET,
        "word_count": config.DEFAULT_WORD_COUNT,
        "challenge_question_count": config.DEFAULT_CHALLENGE_QUESTION_COUNT,
        "challenge_deadline_minutes": config.DEFAULT_CHALLENGE_DEADLINE_MINUTES,
        "created_at": datetime.now(timezone.utc),
    }
    if settings:
        default.update(settings)
    _get_db().collection("groups").document(str(group_id)).set(default)


def update_group_settings(group_id: int, data: dict):
    _get_db().collection("groups").document(str(group_id)).update(data)


def get_all_groups() -> list[dict]:
    """Return all registered groups."""
    docs = _get_db().collection("groups").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


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


# ─── User Daily Words (DM) ───────────────────────────────────────

def save_user_daily_words(telegram_id: int, date_str: str, words: list, topic: str):
    """Save personal daily words for a user (DM feature)."""
    doc = {
        "words": words,
        "topic": topic,
        "generated_at": datetime.now(timezone.utc),
    }
    (_get_db().collection("users").document(str(telegram_id))
     .collection("daily_words").document(date_str).set(doc))


def get_user_daily_words(telegram_id: int, date_str: str) -> Optional[dict]:
    """Get personal daily words for a user."""
    doc = (_get_db().collection("users").document(str(telegram_id))
           .collection("daily_words").document(date_str).get())
    if doc.exists:
        return doc.to_dict()
    return None


# ─── Challenge (Group) ────────────────────────────────────────────

def save_challenge(group_id: int, date_str: str, questions: list,
                    deadline_minutes: int = None):
    now = datetime.now(timezone.utc)
    if deadline_minutes is None:
        deadline_minutes = config.CHALLENGE_DEADLINE_MINUTES
    doc = {
        "questions": questions,
        "participants": {},
        "status": "active",
        "created_at": now,
        "expires_at": now + timedelta(minutes=deadline_minutes),
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


# ─── Challenge Answers (per-user subcollection) ─────────────────

def save_challenge_answer(group_id: int, date_str: str, user_id: int,
                          q_idx: int, is_correct: bool):
    """Persist a single answer for a user in the challenge answers subcollection.

    Creates the answer doc on first call; merges subsequent answers.
    """
    doc_ref = (_get_db().collection("groups").document(str(group_id))
               .collection("challenges").document(date_str)
               .collection("answers").document(str(user_id)))

    now = datetime.now(timezone.utc)
    doc_ref.set({
        "responses": {str(q_idx): is_correct},
        "started_at": now,
        "completed_at": None,
    }, merge=True)


def mark_challenge_answer_complete(group_id: int, date_str: str, user_id: int):
    """Set completed_at timestamp on a user's answer doc."""
    doc_ref = (_get_db().collection("groups").document(str(group_id))
               .collection("challenges").document(date_str)
               .collection("answers").document(str(user_id)))
    doc_ref.update({"completed_at": datetime.now(timezone.utc)})


def get_user_challenge_answers(group_id: int, date_str: str,
                               user_id: int) -> Optional[dict]:
    """Get a single user's answer doc from the challenge answers subcollection."""
    doc = (_get_db().collection("groups").document(str(group_id))
           .collection("challenges").document(date_str)
           .collection("answers").document(str(user_id)).get())
    if doc.exists:
        return {"id": doc.id, **doc.to_dict()}
    return None


def get_all_challenge_answers(group_id: int, date_str: str) -> list[dict]:
    """Get all answer docs for a challenge (one per participant)."""
    docs = (_get_db().collection("groups").document(str(group_id))
            .collection("challenges").document(date_str)
            .collection("answers").stream())
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


def close_challenge_atomic(group_id: int, date_str: str) -> Optional[dict]:
    """Atomically close a challenge: compute scores, set winner, mark closed.

    Uses a Firestore transaction to prevent double-close races.
    Returns the challenge dict with final participants, or None if no challenge.
    """
    db = _get_db()
    challenge_ref = (db.collection("groups").document(str(group_id))
                     .collection("challenges").document(date_str))

    @firestore.transactional
    def _close_txn(txn):
        challenge_doc = challenge_ref.get(transaction=txn)
        if not challenge_doc.exists:
            return None

        challenge = challenge_doc.to_dict()
        if challenge.get("status") == "closed":
            # Already closed — return existing results (idempotent)
            return {"id": challenge_doc.id, **challenge}

        # Read all answer docs (outside transaction is fine — they're immutable at close time)
        answers = get_all_challenge_answers(group_id, date_str)

        participants = {}
        for ans in answers:
            uid = ans["id"]
            responses = ans.get("responses", {})
            # D6 REVISED: score = count of correct answers regardless of completion
            score = sum(1 for v in responses.values() if v)
            participants[uid] = score

        # Determine winner (highest score; tie-break: earliest completed_at)
        winner_id = None
        if participants:
            def _sort_key(item):
                uid, score = item
                # Find completed_at for tie-breaking
                ans_doc = next((a for a in answers if a["id"] == uid), None)
                completed_at = None
                if ans_doc:
                    completed_at = ans_doc.get("completed_at")
                # Higher score first (negate), then earlier completion
                # If completed_at is None, sort last
                if completed_at is None:
                    # Use a far-future timestamp for incomplete users
                    completed_at = datetime(9999, 1, 1, tzinfo=timezone.utc)
                elif hasattr(completed_at, 'timestamp'):
                    pass  # already a datetime
                return (-score, completed_at)

            sorted_p = sorted(participants.items(), key=_sort_key)
            winner_id = int(sorted_p[0][0])

        # Write final scores and close
        txn.update(challenge_ref, {
            "participants": participants,
            "status": "closed",
        })

        # Increment winner's challenge_wins
        if winner_id is not None and participants.get(str(winner_id), 0) > 0:
            winner_ref = db.collection("users").document(str(winner_id))
            txn.update(winner_ref, {
                "challenge_wins": firestore.Increment(1),
            })

        result = {"id": challenge_doc.id, **challenge}
        result["participants"] = participants
        result["status"] = "closed"
        return result

    txn = db.transaction()
    return _close_txn(txn)


def get_active_challenges() -> list[dict]:
    """Get all active challenges across all groups (for restart recovery)."""
    results = []
    groups = get_all_groups()
    now = datetime.now(timezone.utc)
    for group in groups:
        group_id = group["id"]
        docs = (_get_db().collection("groups").document(str(group_id))
                .collection("challenges")
                .where("status", "==", "active")
                .stream())
        for doc in docs:
            data = doc.to_dict()
            expires_at = data.get("expires_at")
            if expires_at and hasattr(expires_at, 'timestamp'):
                if expires_at > now:
                    results.append({
                        "group_id": group_id,
                        "date_str": doc.id,
                        **data,
                    })
    return results


# ─── Enriched Word Cache ──────────────────────────────────────────

def get_enriched_word_doc(word: str) -> Optional[dict]:
    """Fetch cached enriched word document. Returns None on miss."""
    doc = _get_db().collection("enriched_words").document(word).get()
    return doc.to_dict() if doc.exists else None


def set_enriched_word_doc(word: str, data: dict):
    """Write full enriched word document to cache."""
    data["cached_at"] = datetime.now(timezone.utc)
    _get_db().collection("enriched_words").document(word).set(data)


def update_enriched_word_example(word: str, band_tier: str, example: dict):
    """Add a band-tier example to an existing enriched word doc."""
    _get_db().collection("enriched_words").document(word).update({
        f"examples_by_band.{band_tier}": example
    })


# ─── Leaderboard ──────────────────────────────────────────────────

def get_leaderboard(group_id: int) -> list[dict]:
    users = get_all_users_in_group(group_id)
    for user in users:
        stats = get_quiz_stats(int(user["id"]))
        user["accuracy"] = stats["accuracy"]
    return sorted(users, key=lambda u: u.get("total_words", 0), reverse=True)


# ─── Web Auth Operations ─────────────────────────────────────────

def get_user_by_auth_uid(auth_uid: str) -> Optional[dict]:
    """Find user by Firebase Auth UID (stored in auth_mapping collection)."""
    mapping_doc = _get_db().collection("auth_mapping").document(auth_uid).get()
    if mapping_doc.exists:
        user_id = mapping_doc.to_dict().get("user_id")
        if user_id:
            # user_id may be a numeric telegram_id or a web_* string
            try:
                return get_user(int(user_id))
            except (ValueError, TypeError):
                # Web user — fetch by string key directly
                doc = _get_db().collection("users").document(user_id).get()
                if doc.exists:
                    return {"id": doc.id, **doc.to_dict()}
    return None


def create_web_user(auth_uid: str, email: str, name: str,
                    target_band: float = 7.0, topics: list = None) -> dict:
    """Create a user from web registration (no telegram_id)."""
    import uuid
    user_id = f"web_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    user_data = {
        "name": name,
        "username": "",
        "email": email,
        "auth_uid": auth_uid,
        "group_id": None,
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
    _get_db().collection("users").document(user_id).set(user_data)
    # Create auth mapping
    _get_db().collection("auth_mapping").document(auth_uid).set({"user_id": user_id})
    return {"id": user_id, **user_data}


def link_telegram_to_auth(telegram_id: int, auth_uid: str):
    """Link an existing Telegram user to a Firebase Auth account."""
    _get_db().collection("auth_mapping").document(auth_uid).set(
        {"user_id": str(telegram_id)}
    )
    update_user(telegram_id, {"auth_uid": auth_uid})


# ─── Link Code Operations (US-1.7) ────────────────────────────

LINK_CODE_TTL_SECONDS = 5 * 60


def create_link_code(code: str, telegram_id: int) -> None:
    """Store a single-use link code that expires in LINK_CODE_TTL_SECONDS."""
    now = datetime.now(timezone.utc)
    _get_db().collection("auth_link_codes").document(code).set({
        "telegram_id": telegram_id,
        "created_at": now,
        "expires_at": now + timedelta(seconds=LINK_CODE_TTL_SECONDS),
    })


def get_link_code(code: str) -> Optional[dict]:
    doc = _get_db().collection("auth_link_codes").document(code).get()
    if not doc.exists:
        return None
    return doc.to_dict()


def delete_link_code(code: str) -> None:
    _get_db().collection("auth_link_codes").document(code).delete()
