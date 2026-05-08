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


def list_reading_sessions(telegram_id, limit: int = 10) -> list[dict]:
    """Return recent reading sessions newest-first, submitted + in-progress."""
    docs = (_get_db().collection("users").document(str(telegram_id))
            .collection("reading_sessions")
            .order_by("updated_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream())
    return [{"id": d.id, **d.to_dict()} for d in docs]


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


# ─── Identity merge / unlink (US-M12.1) ───────────────────────────

DEFAULT_TARGET_BAND = 7.0


def _max_role(*roles: str) -> str:
    """Return the role with the highest privilege per
    ``api.permissions.ROLE_LEVELS``. Unknown roles fall to ``'user'``."""
    from api.permissions import ROLE_LEVELS
    best = "user"
    for r in roles:
        if ROLE_LEVELS.get(r, 0) > ROLE_LEVELS.get(best, 0):
            best = r
    return best


def _build_merged_fields(web: dict, tg: dict) -> dict:
    """Merge field rules per US-M12.1. The result is the patch applied
    to the surviving Telegram row. ``total_words`` is the **summed**
    counter; the orchestrator overrides it from the deduped vocab count
    after Firestore copy.
    """
    def pick_non_empty(a, b):
        if a not in (None, ""):
            return a
        return b

    def union_topics(a: list, b: list) -> list:
        seen, out = set(), []
        for topic in (a or []) + (b or []):
            t = (topic or "").strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out[:5]

    def cohort_from_created(created):
        if hasattr(created, "strftime"):
            return created.strftime("%Y-%m")
        return None

    merged_created_at = min(
        d for d in (web.get("created_at"), tg.get("created_at")) if d is not None
    ) if web.get("created_at") or tg.get("created_at") else None

    merged_last_active = max(
        d for d in (web.get("last_active"), tg.get("last_active")) if d is not None
    ) if web.get("last_active") or tg.get("last_active") else None

    web_target_band = web.get("target_band") or DEFAULT_TARGET_BAND
    tg_target_band = tg.get("target_band") or DEFAULT_TARGET_BAND
    target_band = (
        web_target_band if tg_target_band == DEFAULT_TARGET_BAND else tg_target_band
    )

    plan_field = (
        web.get("plan") if (web.get("plan") and web.get("plan") != "free")
        else tg.get("plan", "free")
    )
    plan_expires_at = (
        web.get("plan_expires_at") if (web.get("plan") and web.get("plan") != "free")
        else tg.get("plan_expires_at")
    )

    return {
        "auth_uid": web.get("auth_uid"),
        "email": pick_non_empty(web.get("email"), tg.get("email")) or "",
        "name": pick_non_empty(web.get("name"), tg.get("name")) or "",
        "username": pick_non_empty(tg.get("username"), web.get("username")) or "",
        "target_band": target_band,
        "topics": union_topics(web.get("topics", []), tg.get("topics", [])),
        "streak": max(int(web.get("streak") or 0), int(tg.get("streak") or 0)),
        "last_active": merged_last_active,
        "created_at": merged_created_at,
        "total_words": int(web.get("total_words") or 0)
                        + int(tg.get("total_words") or 0),
        "total_quizzes": int(web.get("total_quizzes") or 0)
                          + int(tg.get("total_quizzes") or 0),
        "total_correct": int(web.get("total_correct") or 0)
                          + int(tg.get("total_correct") or 0),
        "challenge_wins": int(web.get("challenge_wins") or 0)
                           + int(tg.get("challenge_wins") or 0),
        "role": _max_role(web.get("role", "user"), tg.get("role", "user")),
        "plan": plan_field,
        "plan_expires_at": plan_expires_at,
        "team_id": web.get("team_id") or tg.get("team_id"),
        "org_id": web.get("org_id") or tg.get("org_id"),
        "quota_override": (
            web.get("quota_override")
            if web.get("quota_override") is not None
            else tg.get("quota_override")
        ),
        "signup_cohort": cohort_from_created(merged_created_at),
        "last_active_date": (
            merged_last_active.date().isoformat()
            if hasattr(merged_last_active, "date") else None
        ),
    }


def merge_web_into_telegram(web_id: str, telegram_id: int) -> dict:
    """Merge ``web_id`` row into ``telegram_id`` row atomically.

    Order (US-M12.1):
      1. Read both Postgres rows (snapshot for the field merge).
      2. Copy in-scope Firestore subcollections from
         ``users/{web_id}/...`` into ``users/{telegram_id}/...`` per
         the dedupe/append rules.
      3. Recompute ``total_words`` from the deduped target vocab so
         the counter doesn't double-count.
      4. Postgres ``merge_into``: UPDATE target + DELETE source in one txn.
      5. Best-effort delete source Firestore subcollections.
      6. Audit + structlog.

    Returns the counts dict from ``copy_subcollections`` (vocab_merged,
    quiz_merged, ...) so the API can echo merge stats back to the web UI.
    """
    import structlog

    from services.admin import audit_service

    repo = get_user_repo()
    fs_repo = _firestore_user_repo_instance()

    web_row = repo.get(web_id)
    tg_row = repo.get(telegram_id)
    if web_row is None or tg_row is None:
        raise ValueError(
            f"merge_web_into_telegram: missing row(s) "
            f"web={web_id!r} tg={telegram_id!r} "
            f"(web_exists={web_row is not None}, tg_exists={tg_row is not None})",
        )

    web_dict = web_row.model_dump()
    tg_dict = tg_row.model_dump()

    # 1. Build merged field dict (counters summed; total_words rewritten in step 3).
    merged = _build_merged_fields(web_dict, tg_dict)

    # 2. Copy Firestore subcollections (vocab dedupe + others).
    counts = fs_repo.copy_subcollections(str(web_id), str(telegram_id))

    # 3. After dedupe, total_words = sum - vocab_dropped.
    merged["total_words"] = (
        int(web_dict.get("total_words") or 0)
        + int(tg_dict.get("total_words") or 0)
        - int(counts.get("vocab_dropped", 0))
    )

    # 4. Atomic Postgres merge.
    repo.merge_into(str(web_id), str(telegram_id), merged=merged)

    # 5. Best-effort cleanup: delete source Firestore subcollection docs.
    try:
        _delete_source_subcollections(str(web_id))
    except Exception as exc:  # noqa: BLE001 — best-effort
        structlog.get_logger("identity").warning(
            "merge.source_cleanup_failed", source_id=str(web_id), error=str(exc),
        )

    # 6. Audit + structlog.
    audit_before = {k: web_dict.get(k) for k in (
        "id", "auth_uid", "email", "role", "plan", "total_words",
        "total_quizzes", "total_correct",
    )}
    audit_after = {k: merged.get(k) for k in (
        "auth_uid", "email", "role", "plan", "total_words",
        "total_quizzes", "total_correct",
    )}
    audit_after["id"] = str(telegram_id)
    audit_service.log_event(
        actor_uid="system:merge",
        event_type="user.merged",
        target_kind="user",
        target_id=str(telegram_id),
        before=audit_before,
        after=audit_after,
    )
    structlog.get_logger("identity").info(
        "user.merged",
        user_id=str(telegram_id),
        source_id=str(web_id),
        **counts,
    )
    return counts


def _firestore_user_repo_instance():
    """Return a ``FirestoreUserRepo`` for subcollection ops regardless of
    which impl ``get_user_repo()`` returns. After US-M8.6 the factory
    yields ``PostgresUserRepo``, but Firestore subcollections still need
    Firestore-side helpers (`copy_subcollections`).
    """
    from services.repositories.firestore.user_repo import FirestoreUserRepo
    return FirestoreUserRepo()


def _delete_source_subcollections(source_id: str) -> None:
    """Best-effort delete of all docs under ``users/{source_id}/<sub>``
    for the 4 in-scope subcollections. Does NOT delete the
    ``users/{source_id}`` root doc — that's handled by Postgres
    ``merge_into`` deleting the row."""
    db = _get_db()
    root = db.collection("users").document(source_id)
    for sub in ("vocabulary", "quiz_history", "writing_history", "daily_words"):
        for doc in root.collection(sub).stream():
            doc.reference.delete()


def unlink_telegram(telegram_id: int, *, surface: str) -> bool:
    """Clear the ``auth_uid`` linkage on the Telegram-side user row.

    ``surface`` is ``"web"`` or ``"bot"`` for audit attribution.
    Returns ``True`` on a real unlink (audit row written),
    ``False`` on a no-op (already unlinked or row missing).
    """
    import structlog

    from services.admin import audit_service

    previous = get_user_repo().unlink_auth(telegram_id)
    if previous is None:
        return False
    audit_service.log_event(
        actor_uid=f"self:{surface}",
        event_type="user.unlinked",
        target_kind="user",
        target_id=str(telegram_id),
        before={"auth_uid": previous},
        after={"auth_uid": None},
    )
    structlog.get_logger("identity").info(
        "user.unlinked", user_id=str(telegram_id), surface=surface,
    )
    return True


# ─── Link tokens (US-M12.2) ───────────────────────────────────────

LINK_TOKEN_TTL_SECONDS = 15 * 60


def create_link_token_for_telegram(telegram_id: int) -> dict:
    """Mint a single-use ``tg_to_web`` token + return the web deep-link URL.

    Used by the bot ``/link`` command (replaces the 6-digit code flow).
    """
    from services.repositories import get_link_token_repo
    doc = get_link_token_repo().create(
        direction="tg_to_web",
        telegram_id=telegram_id,
        ttl_seconds=LINK_TOKEN_TTL_SECONDS,
    )
    return {
        "token": doc.token,
        "url": f"{config.WEB_BASE_URL.rstrip('/')}/link?token={doc.token}",
        "expires_at": doc.expires_at,
    }


def create_link_token_for_auth(auth_uid: str) -> dict:
    """Mint a single-use ``web_to_tg`` token + return the bot deep-link URL.

    Used by the web "Link Telegram" CTA (US-M12.3 wires the UI).
    """
    from services.repositories import get_link_token_repo
    if not config.BOT_USERNAME:
        raise RuntimeError(
            "BOT_USERNAME is not configured; cannot mint web→TG deep-links",
        )
    doc = get_link_token_repo().create(
        direction="web_to_tg",
        auth_uid=auth_uid,
        ttl_seconds=LINK_TOKEN_TTL_SECONDS,
    )
    return {
        "token": doc.token,
        "bot_deep_link": f"https://t.me/{config.BOT_USERNAME}?start=link_{doc.token}",
        "expires_at": doc.expires_at,
    }


def _classify_link_token_failure(token: str) -> str:
    """Return one of ``"invalid"``, ``"expired"``, ``"already_used"``
    when the token cannot be redeemed. The route uses this to pick a
    specific error code instead of a generic one.
    """
    from datetime import datetime as _dt, timezone as _tz

    from services.repositories import get_link_token_repo
    doc = get_link_token_repo().get(token)
    if doc is None:
        return "invalid"
    if doc.redeemed_at is not None:
        return "already_used"
    if doc.expires_at and doc.expires_at < _dt.now(_tz.utc):
        return "expired"
    return "invalid"


def redeem_link_token_web(
    token: str,
    auth_uid: str,
    email: str = "",
    name: str = "",
) -> dict:
    """Redeem a ``tg_to_web`` token from the web side.

    Returns a dict with ``status`` plus sub-case data:

    - ``{"status": "linked", "telegram_id": int}`` — sub-case A: brand-new
      web identity; ``auth_uid`` stamped onto the Telegram row.
    - ``{"status": "merged", "telegram_id": int, "counts": {...}}`` —
      sub-case B: merged ``web_xxx`` into the Telegram row via
      ``merge_web_into_telegram``.
    - ``{"status": "already_linked", "telegram_id": int}`` — sub-case C.
    - ``{"status": "<failure>"}`` for token validation failures
      (``invalid`` / ``expired`` / ``already_used`` / ``wrong_direction``
      / ``conflict`` / ``telegram_user_missing``).
    """
    from services.repositories import get_link_token_repo

    redeemed = get_link_token_repo().redeem(token, redeemed_by=auth_uid)
    if redeemed is None:
        return {"status": _classify_link_token_failure(token)}
    if redeemed.direction != "tg_to_web":
        return {"status": "wrong_direction"}

    telegram_id = redeemed.telegram_id
    if telegram_id is None:
        return {"status": "invalid"}  # malformed token — direction mismatch

    existing = get_user_by_auth_uid(auth_uid)
    tg_user = get_user(int(telegram_id))
    if not tg_user:
        return {"status": "telegram_user_missing"}

    if existing:
        existing_id = str(existing.get("id"))
        if existing_id == str(telegram_id):
            return {
                "status": "already_linked",
                "telegram_id": int(telegram_id),
            }
        if existing_id.startswith("web_"):
            counts = merge_web_into_telegram(existing_id, int(telegram_id))
            return {
                "status": "merged",
                "telegram_id": int(telegram_id),
                "counts": counts,
            }
        return {"status": "conflict"}

    # Sub-case A: stamp auth_uid + (optional) email/name fill-in.
    if tg_user.get("auth_uid") and tg_user["auth_uid"] != auth_uid:
        return {"status": "conflict"}
    link_telegram_to_auth(int(telegram_id), auth_uid)
    updates: dict = {}
    if email and not tg_user.get("email"):
        updates["email"] = email
    if name and not tg_user.get("name"):
        updates["name"] = name
    if updates:
        update_user(int(telegram_id), updates)
    return {"status": "linked", "telegram_id": int(telegram_id)}


def redeem_link_token_bot(token: str, telegram_id: int) -> dict:
    """Redeem a ``web_to_tg`` token from the bot side.

    Three sub-cases:

    - **A — TG user new:** create a Telegram row from the web row's
      ``target_band``/``topics`` (the user already configured them on
      web) and merge the web_xxx into it via
      ``merge_web_into_telegram``.
    - **B — TG user exists, auth_uid=NULL:** if the auth_uid has a
      ``web_xxx`` row, merge it; otherwise stamp ``auth_uid`` directly.
    - **C — already linked:** no-op.

    Mirrors the result shape of ``redeem_link_token_web``.
    """
    from services.repositories import get_link_token_repo

    redeemed = get_link_token_repo().redeem(token, redeemed_by=str(telegram_id))
    if redeemed is None:
        return {"status": _classify_link_token_failure(token)}
    if redeemed.direction != "web_to_tg":
        return {"status": "wrong_direction"}

    auth_uid = redeemed.auth_uid
    if not auth_uid:
        return {"status": "invalid"}

    web_user = get_user_by_auth_uid(auth_uid)
    tg_user = get_user(telegram_id)

    # Sub-case A — TG row doesn't exist yet.
    if tg_user is None:
        if web_user is None:
            return {"status": "telegram_user_missing"}
        # Create the Telegram row from the web row's onboarding choices.
        target_band = float(web_user.get("target_band") or 7.0)
        topics = list(web_user.get("topics") or [])
        name = web_user.get("name") or ""
        create_user(
            telegram_id=telegram_id,
            name=name,
            username="",
            target_band=target_band,
            topics=topics,
        )
        if str(web_user.get("id", "")).startswith("web_"):
            counts = merge_web_into_telegram(str(web_user["id"]), telegram_id)
            return {
                "status": "merged",
                "telegram_id": telegram_id,
                "counts": counts,
            }
        # web row isn't web_xxx (defensive — shouldn't happen): stamp.
        link_telegram_to_auth(telegram_id, auth_uid)
        return {"status": "linked", "telegram_id": telegram_id}

    # Sub-case C — already linked.
    if tg_user.get("auth_uid") == auth_uid:
        return {"status": "already_linked", "telegram_id": telegram_id}
    if tg_user.get("auth_uid"):
        return {"status": "conflict"}

    # Sub-case B — TG row exists, auth_uid is NULL.
    if web_user and str(web_user.get("id", "")).startswith("web_"):
        counts = merge_web_into_telegram(str(web_user["id"]), telegram_id)
        return {
            "status": "merged",
            "telegram_id": telegram_id,
            "counts": counts,
        }
    link_telegram_to_auth(telegram_id, auth_uid)
    return {"status": "linked", "telegram_id": telegram_id}


# ─── Link Code Operations (US-1.7, deprecated by US-M12.2) ────────────────
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
