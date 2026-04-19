"""Firestore data-access module (legacy surface).

As of US-P.1 (#113) the user-scoped collections below are owned by the
``services/repositories/`` package. The functions here remain as the
public surface that handlers, services, and ``async_firebase`` already
import — they now delegate to the repository layer so the M8 Postgres
migration (#130) touches only the repo impls, not 40+ call sites.

In-scope (delegated to repos):
- ``users/{uid}`` profile
- ``users/{uid}/vocabulary``
- ``users/{uid}/quiz_history``
- ``users/{uid}/writing_history``
- ``users/{uid}/daily_words`` (DM-scoped)
- ``auth_mapping`` (web-auth linkage to ``users/``)

Out of scope (unchanged — stays on Firestore permanently):
- ``groups/`` and all subcollections (``daily_words``, ``challenges``,
  ``challenges/*/answers``)
- ``users/{uid}/quiz_sessions``, ``users/{uid}/daily_plans``,
  ``users/{uid}/listening_history``, ``users/{uid}/progress_snapshots``,
  ``users/{uid}/progress_recommendations``
- ``enriched_words`` cache
- ``auth_link_codes`` (DM/bot linking flow)

The ``_get_db()`` helper is preserved because the out-of-scope paths
still reach Firestore directly through this module.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from firebase_admin import firestore

import config
from services.repositories import (
    get_daily_words_repo,
    get_quiz_history_repo,
    get_user_repo,
    get_vocab_repo,
    get_writing_history_repo,
)
from services.repositories.firestore.user_repo import _get_db as _get_db  # noqa: F401

# ``_get_db`` is re-exported above so legacy call sites (api/auth.py,
# api/routes/auth.py, this module's out-of-scope group/plan/listening
# helpers) can keep importing ``firebase_service._get_db``. The single
# lazy-init lives in ``services.repositories.firestore.user_repo`` —
# there is exactly one Firebase app and one Firestore client per
# process.


# ─── User Operations (delegated to UserRepo) ───────────────────────

def get_user(telegram_id: int) -> Optional[dict]:
    user = get_user_repo().get(telegram_id)
    return user.model_dump() if user else None


def create_user(telegram_id: int, name: str, username: str = "",
                group_id: int = None, target_band: float = 7.0,
                topics: list = None) -> dict:
    user = get_user_repo().create(
        telegram_id,
        name,
        username=username,
        group_id=group_id,
        target_band=target_band,
        topics=topics,
    )
    return user.model_dump()


def update_user(telegram_id: int, data: dict):
    get_user_repo().update(telegram_id, data)


def get_all_users_in_group(group_id: int) -> list[dict]:
    return [u.model_dump() for u in get_user_repo().list_by_group(group_id)]


def get_all_users() -> list[dict]:
    """Return all registered users."""
    return [u.model_dump() for u in get_user_repo().list_all()]


def update_streak(telegram_id: int):
    get_user_repo().update_streak(telegram_id)


# ─── Vocabulary Operations (delegated to VocabRepo) ────────────────

def add_word_to_user(telegram_id: int, word_data: dict) -> str:
    return get_vocab_repo().add_word(telegram_id, word_data)


def add_word_if_not_exists(telegram_id, word_data: dict) -> tuple[str, bool]:
    """Atomically add a word to a user's vocabulary, deduped by lowercased `word`.

    Returns (word_id, created). `created` is False if a matching word already
    exists — in that case word_id is the existing doc's id and total_words is
    not incremented.
    """
    return get_vocab_repo().add_word_if_not_exists(telegram_id, word_data)


def get_user_vocabulary(telegram_id: int, limit: int = 50) -> list[dict]:
    return [
        v.model_dump() for v in get_vocab_repo().list_by_user(telegram_id, limit)
    ]


def get_user_word_list(telegram_id: int) -> list[str]:
    """Get just the word strings for deduplication."""
    return get_vocab_repo().list_word_strings(telegram_id)


def get_user_vocabulary_page(telegram_id, limit: int = 20,
                              after_added_at: Optional[datetime] = None) -> list[dict]:
    """Cursor-paginated vocabulary fetch ordered by added_at DESC.

    Cursor is the `added_at` timestamp of the last item from the previous page.
    """
    return [
        v.model_dump()
        for v in get_vocab_repo().list_page(telegram_id, limit, after_added_at)
    ]


def count_words_by_topic(telegram_id) -> dict[str, int]:
    """Return {topic_id: count} across the user's full vocabulary."""
    return get_vocab_repo().count_by_topic(telegram_id)


# ─── Quiz Sessions (Web) ──────────────────────────────────────────
# Not migrated — quiz_sessions is a short-lived cache, not core user data.

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
    return [v.model_dump() for v in get_vocab_repo().get_mastered(telegram_id)]


def get_due_words(telegram_id: int, limit: int = 10) -> list[dict]:
    return [v.model_dump() for v in get_vocab_repo().get_due(telegram_id, limit)]


def update_word_srs(telegram_id: int, word_id: str, data: dict):
    get_vocab_repo().update_srs(telegram_id, word_id, data)


def get_word_by_id(telegram_id: int, word_id: str) -> Optional[dict]:
    v = get_vocab_repo().get_by_id(telegram_id, word_id)
    return v.model_dump() if v else None


# ─── Quiz History (delegated to QuizHistoryRepo) ───────────────────

def save_quiz_result(telegram_id: int, quiz_data: dict):
    get_quiz_history_repo().save_result(telegram_id, quiz_data)


def get_latest_quiz(telegram_id: int) -> Optional[dict]:
    """Return the most recent quiz_history doc, or None."""
    entry = get_quiz_history_repo().get_latest(telegram_id)
    return entry.model_dump() if entry else None


def get_quiz_stats(telegram_id: int) -> dict:
    return get_user_repo().get_quiz_stats(telegram_id).model_dump()


# ─── Writing History (delegated to WritingHistoryRepo) ─────────────

def save_writing(telegram_id: int, writing_data: dict):
    get_writing_history_repo().save(telegram_id, writing_data)


def save_writing_submission(telegram_id, writing_data: dict) -> str:
    return get_writing_history_repo().save_submission(telegram_id, writing_data)


def get_writing_submission(telegram_id, submission_id: str) -> Optional[dict]:
    entry = get_writing_history_repo().get_submission(telegram_id, submission_id)
    return entry.model_dump() if entry else None


def list_writing_submissions(telegram_id, limit: int = 50) -> list[dict]:
    return [
        e.model_dump()
        for e in get_writing_history_repo().list_submissions(telegram_id, limit)
    ]


# ─── Reading Sessions (US-M9.2) ───────────────────────────────────
# Kept on Firestore; will move behind the repositories Protocol if/when
# Reading grows enough state to justify it.

def save_reading_session(telegram_id, session_id: str, data: dict) -> None:
    (_get_db().collection("users").document(str(telegram_id))
     .collection("reading_sessions").document(session_id)
     .set({**data, "updated_at": datetime.now(timezone.utc)}))


def get_reading_session(telegram_id, session_id: str) -> Optional[dict]:
    doc = (_get_db().collection("users").document(str(telegram_id))
           .collection("reading_sessions").document(session_id).get())
    if not doc.exists:
        return None
    return {"id": doc.id, **(doc.to_dict() or {})}


def update_reading_session(telegram_id, session_id: str, data: dict) -> None:
    (_get_db().collection("users").document(str(telegram_id))
     .collection("reading_sessions").document(session_id)
     .update({**data, "updated_at": datetime.now(timezone.utc)}))


# Global (not user-scoped) cache for AI-generated question sets. Keyed
# by passage_id so the AI cost is one-time per passage (US-M9.3).

def get_cached_reading_questions(passage_id: str) -> Optional[dict]:
    doc = _get_db().collection("reading_questions").document(passage_id).get()
    if not doc.exists:
        return None
    return doc.to_dict()


def save_cached_reading_questions(passage_id: str, data: dict) -> None:
    (_get_db().collection("reading_questions").document(passage_id)
     .set({**data, "cached_at": datetime.now(timezone.utc)}))


# ─── Daily Plans (US-4.1) ─────────────────────────────────────────
# Not migrated — kept on Firestore for now, pending separate refinement.

def get_daily_plan(telegram_id, date_str: str) -> Optional[dict]:
    doc = (_get_db().collection("users").document(str(telegram_id))
           .collection("daily_plans").document(date_str).get())
    if not doc.exists:
        return None
    return doc.to_dict()


def save_daily_plan(telegram_id, date_str: str, plan: dict) -> None:
    now = datetime.now(timezone.utc)
    (_get_db().collection("users").document(str(telegram_id))
     .collection("daily_plans").document(date_str)
     .set({**plan, "generated_at": now}))


def update_daily_plan(telegram_id, date_str: str, data: dict) -> None:
    (_get_db().collection("users").document(str(telegram_id))
     .collection("daily_plans").document(date_str).update(data))


def complete_plan_activity(
    telegram_id, date_str: str, activity_id: str,
) -> Optional[dict]:
    """Atomically mark a plan activity completed.

    Returns the updated plan dict, None if no plan exists for the date,
    or the string "NOT_FOUND" if the activity id is not in the plan.
    The read/modify/write happens inside a Firestore transaction so
    concurrent completions of different activities cannot clobber each
    other.
    """
    db = _get_db()
    plan_ref = (db.collection("users").document(str(telegram_id))
                .collection("daily_plans").document(date_str))

    @firestore.transactional
    def _txn(txn):
        snapshot = plan_ref.get(transaction=txn)
        if not snapshot.exists:
            return None

        plan = snapshot.to_dict() or {}
        activities = list(plan.get("activities") or [])
        changed = False
        for i, a in enumerate(activities):
            if a.get("id") == activity_id and not a.get("completed"):
                activities[i] = {**a, "completed": True}
                changed = True
                break

        if not any(a.get("id") == activity_id for a in activities):
            return "NOT_FOUND"

        if not changed:
            # Already completed — idempotent no-op
            return plan

        completed_count = sum(1 for a in activities if a.get("completed"))
        txn.update(plan_ref, {
            "activities": activities,
            "completed_count": completed_count,
        })
        return {**plan, "activities": activities, "completed_count": completed_count}

    return _txn(db.transaction())


# ─── Listening Exercises ──────────────────────────────────────────
# Not migrated — listening_history is out of scope for US-P.1.

def save_listening_exercise(telegram_id, exercise_data: dict) -> str:
    now = datetime.now(timezone.utc)
    doc = {**exercise_data, "created_at": now}
    ref = (_get_db().collection("users").document(str(telegram_id))
           .collection("listening_history").document())
    ref.set(doc)
    return ref.id


def get_listening_exercise(telegram_id, exercise_id: str) -> Optional[dict]:
    doc = (_get_db().collection("users").document(str(telegram_id))
           .collection("listening_history").document(exercise_id).get())
    if not doc.exists:
        return None
    return {"id": doc.id, **doc.to_dict()}


def update_listening_exercise(telegram_id, exercise_id: str, data: dict) -> None:
    (_get_db().collection("users").document(str(telegram_id))
     .collection("listening_history").document(exercise_id).update(data))


def list_listening_exercises(telegram_id, limit: int = 50) -> list[dict]:
    docs = (_get_db().collection("users").document(str(telegram_id))
            .collection("listening_history")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream())
    return [{"id": d.id, **d.to_dict()} for d in docs]


# ─── Progress Snapshots (US-5.1) ──────────────────────────────────
# Not migrated — progress_snapshots are computed/cached views.

def save_progress_snapshot(telegram_id, date_str: str, snapshot: dict) -> None:
    """Upsert a progress snapshot for the given local date."""
    now = datetime.now(timezone.utc)
    (_get_db().collection("users").document(str(telegram_id))
     .collection("progress_snapshots").document(date_str)
     .set({**snapshot, "date": date_str, "generated_at": now}))


def get_progress_snapshot(telegram_id, date_str: str) -> Optional[dict]:
    doc = (_get_db().collection("users").document(str(telegram_id))
           .collection("progress_snapshots").document(date_str).get())
    if not doc.exists:
        return None
    return doc.to_dict()


def list_progress_snapshots(telegram_id, date_strs: list[str]) -> list[dict]:
    """Return snapshots whose document id is in `date_strs` (skips missing).

    Uses a single Firestore `get_all` batch call rather than N sequential
    `document().get()` round-trips.
    """
    if not date_strs:
        return []
    db = _get_db()
    col = (db.collection("users").document(str(telegram_id))
           .collection("progress_snapshots"))
    refs = [col.document(d) for d in date_strs]
    snapshots = db.get_all(refs)
    return [s.to_dict() for s in snapshots if s.exists]


# ─── Progress Recommendations (US-5.3) ───────────────────────────

def get_progress_recommendations(telegram_id, week_key: str) -> Optional[dict]:
    doc = (_get_db().collection("users").document(str(telegram_id))
           .collection("progress_recommendations").document(week_key).get())
    if not doc.exists:
        return None
    return doc.to_dict()


def save_progress_recommendations(
    telegram_id, week_key: str, data: dict,
) -> None:
    now = datetime.now(timezone.utc)
    (_get_db().collection("users").document(str(telegram_id))
     .collection("progress_recommendations").document(week_key)
     .set({**data, "week_key": week_key, "generated_at": now}))


# ─── Group Operations ─────────────────────────────────────────────
# OUT OF SCOPE for US-P.1 — groups stay on Firestore permanently.

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
# OUT OF SCOPE — group daily words stay on Firestore.

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


# ─── User Daily Words (DM — delegated to DailyWordsRepo) ─────────

def save_user_daily_words(telegram_id: int, date_str: str, words: list, topic: str):
    """Save personal daily words for a user (DM feature)."""
    get_daily_words_repo().save(telegram_id, date_str, words, topic)


def get_user_daily_words(telegram_id: int, date_str: str) -> Optional[dict]:
    """Get personal daily words for a user."""
    dto = get_daily_words_repo().get(telegram_id, date_str)
    if not dto:
        return None
    # Legacy callers expect the raw doc body without the id; the date_str
    # is always known at the call site.
    return dto.model_dump(exclude={"id"})


# ─── Challenge (Group) ────────────────────────────────────────────
# OUT OF SCOPE — group challenges stay on Firestore.

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
# OUT OF SCOPE — group data stays on Firestore.

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
# Not migrated — shared cache, not per-user data.

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


# ─── Web Auth Operations (delegated to UserRepo) ─────────────────

def get_user_by_auth_uid(auth_uid: str) -> Optional[dict]:
    """Find user by Firebase Auth UID (stored in auth_mapping collection)."""
    user = get_user_repo().get_by_auth_uid(auth_uid)
    return user.model_dump() if user else None


def create_web_user(auth_uid: str, email: str, name: str,
                    target_band: float = 7.0, topics: list = None) -> dict:
    """Create a user from web registration (no telegram_id)."""
    user = get_user_repo().create_web_user(
        auth_uid, email, name, target_band=target_band, topics=topics,
    )
    return user.model_dump()


def link_telegram_to_auth(telegram_id: int, auth_uid: str):
    """Link an existing Telegram user to a Firebase Auth account."""
    get_user_repo().link_telegram_to_auth(telegram_id, auth_uid)


# ─── Link Code Operations (US-1.7) ────────────────────────────
# Not migrated — short-lived auth tokens, not core user data.

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
