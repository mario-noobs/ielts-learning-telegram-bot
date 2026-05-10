"""Legacy data-access surface — now a thin delegation layer over PG repos.

Post-M8 cutover (#234) every collection moved to Postgres. This module
stays as the import surface (``firebase_service.X``) for the 50+ call
sites in handlers/services/api so the migration didn't have to touch
each one. Each function here forwards to a typed PG repo from
``services.repositories``.

The only Firebase product the app still depends on is **Identity
Platform / Auth** for ID-token verification. That init lives in
``services.firebase_auth`` and does NOT import Firestore. The
``_get_db`` shim is retained for backwards compatibility — it now just
boots Firebase Admin and returns ``None``.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import config
from services.repositories import (
    get_auth_link_codes_repo,
    get_daily_plans_repo,
    get_daily_words_repo,
    get_enriched_words_repo,
    get_group_challenge_answers_repo,
    get_group_challenges_repo,
    get_group_daily_words_repo,
    get_groups_repo,
    get_listening_history_repo,
    get_progress_recommendations_repo,
    get_progress_snapshots_repo,
    get_quiz_history_repo,
    get_quiz_sessions_repo,
    get_reading_questions_repo,
    get_reading_sessions_repo,
    get_user_repo,
    get_vocab_repo,
    get_writing_history_repo,
)
def _get_db():
    """Backwards-compat shim — returns None post-decommission (#234).

    Pre-cutover this returned a Firestore client. Code that still calls
    ``firebase_service._get_db()`` is either:
    1. Booting Firebase Admin SDK for Auth — switched to
       ``services.firebase_auth.ensure_admin_initialized``.
    2. Doing direct Firestore reads — none should remain post-PR #6.

    We boot Firebase Admin (cheap, idempotent) and return None so a
    caller that mistakenly chains ``.collection(...)`` fails loudly
    instead of silently re-reaching for Firestore.
    """
    from services.firebase_auth import ensure_admin_initialized
    ensure_admin_initialized()
    return None


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
    word_id = get_vocab_repo().add_word(telegram_id, word_data)
    invalidate_topic_mastery_cache(telegram_id)
    return word_id


def add_word_if_not_exists(telegram_id, word_data: dict) -> tuple[str, bool]:
    """Atomically add a word to a user's vocabulary, deduped by lowercased `word`.

    Returns (word_id, created). `created` is False if a matching word already
    exists — in that case word_id is the existing doc's id and total_words is
    not incremented.
    """
    word_id, created = get_vocab_repo().add_word_if_not_exists(telegram_id, word_data)
    if created:
        invalidate_topic_mastery_cache(telegram_id)
    return word_id, created


def get_user_vocabulary(telegram_id: int, limit: int = 50) -> list[dict]:
    return [
        v.model_dump() for v in get_vocab_repo().list_by_user(telegram_id, limit)
    ]


def get_user_word_list(telegram_id: int) -> list[str]:
    """Get just the word strings for deduplication."""
    return get_vocab_repo().list_word_strings(telegram_id)


def get_user_vocabulary_page(telegram_id, limit: int = 20,
                              after_added_at: Optional[datetime] = None,
                              topic: Optional[str] = None) -> list[dict]:
    """Cursor-paginated vocabulary fetch ordered by added_at DESC.

    Cursor is the `added_at` timestamp of the last item from the previous page.
    Optional `topic` narrows results to one topic slug.
    """
    return [
        v.model_dump()
        for v in get_vocab_repo().list_page(
            telegram_id, limit, after_added_at, topic,
        )
    ]


def count_words_by_topic(telegram_id) -> dict[str, int]:
    """Return {topic_id: count} across the user's full vocabulary."""
    return get_vocab_repo().count_by_topic(telegram_id)


# US-#231 — Firestore quota mitigation. The aggregate iterates every
# vocab doc, which on a hot page (/learn/vocab) blew through the 50K
# read/day Firestore free-tier ceiling after a few dozen reloads. A
# short in-memory cache absorbs reload bursts; we invalidate on word
# add / strength override so the numbers don't drift far behind.
import time as _time

_TOPIC_MASTERY_CACHE_TTL_S = 60
_topic_mastery_cache: dict[str, tuple[float, dict[str, dict[str, int]]]] = {}


def count_words_by_topic_with_mastery(telegram_id) -> dict[str, dict[str, int]]:
    """Per-topic ``{total, mastered}`` for /learn/vocab home cards (US-#231).

    Cached per-user with 60s TTL. Without the cache a single page reload
    spawned ``len(vocab)`` Firestore reads, hammering free-tier quota.
    """
    key = str(telegram_id)
    cached = _topic_mastery_cache.get(key)
    now = _time.monotonic()
    if cached is not None and (now - cached[0]) < _TOPIC_MASTERY_CACHE_TTL_S:
        return cached[1]
    result = get_vocab_repo().count_by_topic_with_mastery(telegram_id)
    _topic_mastery_cache[key] = (now, result)
    return result


def invalidate_topic_mastery_cache(telegram_id) -> None:
    """Drop the cached aggregate so the next read recomputes."""
    _topic_mastery_cache.pop(str(telegram_id), None)


# ─── Quiz Sessions (Web) ──────────────────────────────────────────
# M8 Block C (#234): now delegated to PostgresQuizSessionsRepo.

def save_quiz_session(telegram_id, session_id: str, questions: list[dict]) -> None:
    """Persist a quiz session with full (unsanitized) question docs."""
    get_quiz_sessions_repo().save(telegram_id, session_id, questions)


def get_quiz_session(telegram_id, session_id: str) -> Optional[dict]:
    return get_quiz_sessions_repo().get(telegram_id, session_id)


def mark_session_question_answered(telegram_id, session_id: str,
                                    question_id: str) -> None:
    """Append question_id to the session's answered_ids array (idempotent)."""
    get_quiz_sessions_repo().mark_question_answered(
        telegram_id, session_id, question_id,
    )


def get_mastered_words(telegram_id: int) -> list[dict]:
    """Return all vocabulary docs with srs_interval > 30 (mastered)."""
    return [v.model_dump() for v in get_vocab_repo().get_mastered(telegram_id)]


def get_due_words(telegram_id: int, limit: int = 10) -> list[dict]:
    return [v.model_dump() for v in get_vocab_repo().get_due(telegram_id, limit)]


def update_word_srs(telegram_id: int, word_id: str, data: dict):
    get_vocab_repo().update_srs(telegram_id, word_id, data)
    # SRS interval changes can shift a word into/out of "Mastered"
    # (interval > 30), so the cached topic aggregate is stale.
    invalidate_topic_mastery_cache(telegram_id)


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
# M8 Block C (#234): now delegated to PostgresReadingSessionsRepo.

def save_reading_session(telegram_id, session_id: str, data: dict) -> None:
    get_reading_sessions_repo().save(telegram_id, session_id, data)


def get_reading_session(telegram_id, session_id: str) -> Optional[dict]:
    return get_reading_sessions_repo().get(telegram_id, session_id)


def update_reading_session(telegram_id, session_id: str, data: dict) -> None:
    get_reading_sessions_repo().update(telegram_id, session_id, data)


def list_reading_sessions(telegram_id, limit: int = 10) -> list[dict]:
    """Return recent reading sessions newest-first, submitted + in-progress."""
    return get_reading_sessions_repo().list_for_user(telegram_id, limit)


# Global (not user-scoped) cache for AI-generated question sets. Keyed
# by passage_id so the AI cost is one-time per passage (US-M9.3).

def get_cached_reading_questions(passage_id: str) -> Optional[dict]:
    return get_reading_questions_repo().get(passage_id)


def save_cached_reading_questions(passage_id: str, data: dict) -> None:
    get_reading_questions_repo().save(passage_id, data)


# ─── Daily Plans (US-4.1) ─────────────────────────────────────────
# M8 Block D (#234): now delegated to PostgresDailyPlansRepo.

def get_daily_plan(telegram_id, date_str: str) -> Optional[dict]:
    return get_daily_plans_repo().get(telegram_id, date_str)


def save_daily_plan(telegram_id, date_str: str, plan: dict) -> None:
    get_daily_plans_repo().save(telegram_id, date_str, plan)


def update_daily_plan(telegram_id, date_str: str, data: dict) -> None:
    get_daily_plans_repo().update(telegram_id, date_str, data)


def complete_plan_activity(
    telegram_id, date_str: str, activity_id: str,
) -> Optional[dict]:
    """Atomically mark a plan activity completed.

    Returns the updated plan dict, ``None`` if no plan exists for the
    date, or ``"NOT_FOUND"`` if the activity_id is not in the plan.
    The read/modify/write happens inside a PG transaction with row lock
    so concurrent completions of different activities cannot clobber.
    """
    return get_daily_plans_repo().complete_activity(
        telegram_id, date_str, activity_id,
    )


# ─── Listening Exercises ──────────────────────────────────────────
# M8 cutover (#234): now delegated to PostgresListeningHistoryRepo.

def save_listening_exercise(telegram_id, exercise_data: dict) -> str:
    return get_listening_history_repo().save(telegram_id, exercise_data)


def get_listening_exercise(telegram_id, exercise_id: str) -> Optional[dict]:
    return get_listening_history_repo().get(telegram_id, exercise_id)


def update_listening_exercise(telegram_id, exercise_id: str, data: dict) -> None:
    get_listening_history_repo().update(telegram_id, exercise_id, data)


def list_listening_exercises(telegram_id, limit: int = 50) -> list[dict]:
    return get_listening_history_repo().list(telegram_id, limit)


# ─── Progress Snapshots (US-5.1) ──────────────────────────────────
# M8 Block D (#234): now delegated to PostgresProgressSnapshotsRepo.

def save_progress_snapshot(telegram_id, date_str: str, snapshot: dict) -> None:
    """Upsert a progress snapshot for the given local date."""
    get_progress_snapshots_repo().save(telegram_id, date_str, snapshot)


def get_progress_snapshot(telegram_id, date_str: str) -> Optional[dict]:
    return get_progress_snapshots_repo().get(telegram_id, date_str)


def list_progress_snapshots(telegram_id, date_strs: list[str]) -> list[dict]:
    """Return snapshots whose date is in `date_strs` (skips missing).

    Single SELECT WHERE date IN (...) — replaces the Firestore
    ``get_all`` batch call.
    """
    return get_progress_snapshots_repo().list_for_dates(telegram_id, date_strs)


# ─── Progress Recommendations (US-5.3) ───────────────────────────
# M8 Block D (#234): now delegated to PostgresProgressRecommendationsRepo.

def get_progress_recommendations(telegram_id, week_key: str) -> Optional[dict]:
    return get_progress_recommendations_repo().get(telegram_id, week_key)


def save_progress_recommendations(
    telegram_id, week_key: str, data: dict,
) -> None:
    get_progress_recommendations_repo().save(telegram_id, week_key, data)


# ─── Group Operations ─────────────────────────────────────────────
# OUT OF SCOPE for US-P.1 — groups stay on Firestore permanently.

# M8 Block B (#234): now delegated to PostgresGroupsRepo.

def get_group_settings(group_id: int) -> Optional[dict]:
    return get_groups_repo().get(group_id)


def create_group(group_id: int, settings: dict = None,
                  owner_telegram_id: Optional[int] = None):
    """Create a new group row with default settings.

    ``owner_telegram_id`` is stamped at creation so the web group-edit
    page (US-#227) can permission-gate the PATCH route. Idempotent —
    re-running the call on an existing group is a no-op (ON CONFLICT
    DO NOTHING).
    """
    get_groups_repo().create(group_id, settings, owner_telegram_id)


def update_group_settings(group_id: int, data: dict):
    get_groups_repo().update(group_id, data)


def get_all_groups() -> list[dict]:
    """Return all registered groups."""
    return get_groups_repo().list_all()


def list_groups_for_user(telegram_id: int) -> list[dict]:
    """Return groups this user is a member of (US-#227).

    Membership is the union of ``users.group_id`` (legacy /start-in-
    group flow) and ``group_members`` (M14 explicit ledger).
    """
    return get_groups_repo().list_for_user(telegram_id)


# ─── Daily Words (Group) ──────────────────────────────────────────
# M8 Block B (#234): now delegated to PostgresGroupDailyWordsRepo.

def save_daily_words(group_id: int, date_str: str, words: list, topic: str):
    get_group_daily_words_repo().save(group_id, date_str, words, topic)


def get_daily_words(group_id: int, date_str: str) -> Optional[dict]:
    return get_group_daily_words_repo().get(group_id, date_str)


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
# M8 Block B (#234): now delegated to PostgresGroupChallengesRepo.

def save_challenge(group_id: int, date_str: str, questions: list,
                    deadline_minutes: int = None):
    get_group_challenges_repo().save(group_id, date_str, questions, deadline_minutes)


def get_challenge(group_id: int, date_str: str) -> Optional[dict]:
    return get_group_challenges_repo().get(group_id, date_str)


def update_challenge_score(group_id: int, date_str: str,
                           user_id: int, score: int):
    get_group_challenges_repo().update_participant_score(
        group_id, date_str, user_id, score,
    )


# ─── Challenge Answers (per-user subcollection) ─────────────────
# M8 Block B (#234): now delegated to PostgresGroupChallengeAnswersRepo.

def save_challenge_answer(group_id: int, date_str: str, user_id: int,
                          q_idx: int, is_correct: bool,
                          display_name: Optional[str] = None):
    """Merge ``{q_idx: is_correct}`` into the user's answer row.

    ``display_name`` is the Telegram-side name captured at answer time.
    Used by the results post when the user has no PG profile row (e.g.
    they only clicked challenge buttons, never DM'd /start) — without
    this, results degraded to "🥇 Unknown — 2/10" (#228 follow-up).
    """
    get_group_challenge_answers_repo().upsert_response(
        group_id, date_str, user_id, q_idx, is_correct, display_name,
    )


def mark_challenge_answer_complete(group_id: int, date_str: str, user_id: int):
    get_group_challenge_answers_repo().mark_completed(group_id, date_str, user_id)


def get_user_challenge_answers(group_id: int, date_str: str,
                               user_id: int) -> Optional[dict]:
    return get_group_challenge_answers_repo().get(group_id, date_str, user_id)


def get_all_challenge_answers(group_id: int, date_str: str) -> list[dict]:
    return get_group_challenge_answers_repo().list_for_challenge(group_id, date_str)


def close_challenge_atomic(group_id: int, date_str: str) -> Optional[dict]:
    """Atomically close a challenge: compute scores, set winner, mark closed.

    PG transaction with row-level lock on the challenge row prevents
    double-close races. Idempotent — re-closing returns existing results.
    Winner's ``challenge_wins`` counter bumps in the same transaction.

    The returned dict surfaces ``display_names`` (uid → Telegram name)
    so result posts can render names without a second query, matching
    the legacy Firestore shape.
    """
    return get_group_challenges_repo().close_atomic(group_id, date_str)


def get_active_challenges() -> list[dict]:
    """Get all active challenges across all groups (for restart recovery)."""
    return get_group_challenges_repo().list_active()


# ─── Enriched Word Cache ──────────────────────────────────────────
# M8 Block E (#234): now delegated to PostgresEnrichedWordsRepo.

def get_enriched_word_doc(word: str) -> Optional[dict]:
    """Fetch cached enriched word document. Returns None on miss."""
    return get_enriched_words_repo().get(word)


def set_enriched_word_doc(word: str, data: dict):
    """Write full enriched word document to cache."""
    get_enriched_words_repo().save(word, data)


def update_enriched_word_example(word: str, band_tier: str, example: dict):
    """Merge ``examples_by_band[band_tier] = example`` race-safely."""
    get_enriched_words_repo().update_example(word, band_tier, example)


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

    # 2. Move PG subcollection rows source → target. Single transaction
    #    inside the helper; vocab dedupe by normalized_word, daily_words
    #    skip dates target already has.
    counts = _copy_subcollections_pg(str(web_id), str(telegram_id))

    # 3. After dedupe, total_words = sum - vocab_dropped.
    merged["total_words"] = (
        int(web_dict.get("total_words") or 0)
        + int(tg_dict.get("total_words") or 0)
        - int(counts.get("vocab_dropped", 0))
    )

    # 4. Atomic Postgres merge — DELETE source row + apply merged fields
    #    to target. Cascade fires on any leftover subcollection rows
    #    (defensive — step 2 already moved everything that should survive).
    repo.merge_into(str(web_id), str(telegram_id), merged=merged)

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


def _copy_subcollections_pg(source_id: str, target_id: str) -> dict:
    """Move user-scoped subcollection rows from source → target (M8 #234).

    Replaces the legacy Firestore ``copy_subcollections`` helper. Runs
    in a single PG transaction so a partial failure doesn't leave the
    merge in a half-applied state.

    Vocab dedupe rule: when source and target both have a row with the
    same ``normalized_word``, the target's row wins (we drop source).
    Other tables (quiz_history, writing_history, daily_words,
    listening_history) have no natural dedupe key — every row moves.

    Returns counts dict matching the legacy shape so callers can echo
    merge stats back to the user.
    """
    from sqlalchemy import text

    from services.db import get_sync_session

    counts = {
        "vocab_merged": 0,
        "vocab_dropped": 0,
        "quiz_merged": 0,
        "writing_merged": 0,
        "daily_merged": 0,
        "daily_skipped": 0,
        "listening_merged": 0,
    }
    with get_sync_session() as s, s.begin():
        # Vocab: dedupe by (target_user, normalized_word). Source rows
        # whose normalized_word already exists on target get dropped.
        dropped = s.execute(
            text(
                "DELETE FROM user_vocabulary AS src "
                "WHERE src.user_id = :s "
                "AND EXISTS ("
                "  SELECT 1 FROM user_vocabulary AS tgt "
                "  WHERE tgt.user_id = :t "
                "  AND tgt.normalized_word = src.normalized_word"
                ")"
            ),
            {"s": source_id, "t": target_id},
        ).rowcount or 0
        moved = s.execute(
            text(
                "UPDATE user_vocabulary SET user_id = :t WHERE user_id = :s"
            ),
            {"s": source_id, "t": target_id},
        ).rowcount or 0
        counts["vocab_dropped"] = dropped
        counts["vocab_merged"] = moved

        # Histories: simple bulk move — primary keys are row UUIDs so no
        # collision possible.
        for tbl, key in (
            ("quiz_history", "quiz_merged"),
            ("writing_history", "writing_merged"),
            ("listening_history", "listening_merged"),
        ):
            counts[key] = s.execute(
                text(f"UPDATE {tbl} SET user_id = :t WHERE user_id = :s"),
                {"s": source_id, "t": target_id},
            ).rowcount or 0

        # user_daily_words has composite PK (user_id, date). Skip dates
        # the target already covers; move the rest.
        skipped = s.execute(
            text(
                "DELETE FROM user_daily_words AS src "
                "WHERE src.user_id = :s "
                "AND EXISTS ("
                "  SELECT 1 FROM user_daily_words AS tgt "
                "  WHERE tgt.user_id = :t AND tgt.date = src.date"
                ")"
            ),
            {"s": source_id, "t": target_id},
        ).rowcount or 0
        moved = s.execute(
            text(
                "UPDATE user_daily_words SET user_id = :t WHERE user_id = :s"
            ),
            {"s": source_id, "t": target_id},
        ).rowcount or 0
        counts["daily_skipped"] = skipped
        counts["daily_merged"] = moved

    return counts


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

    repo = get_link_token_repo()
    # Validate direction BEFORE redeeming so a wrong-direction submission
    # doesn't atomically consume an otherwise-valid token. The peek can
    # race with another caller, but `redeem` itself stays atomic — so
    # the worst case is a redeem-after-peek that legitimately succeeds
    # for the right caller. Wrong direction never wastes a token.
    peek = repo.get(token)
    if peek is None:
        return {"status": "invalid"}
    if peek.direction != "tg_to_web":
        return {"status": "wrong_direction"}

    redeemed = repo.redeem(token, redeemed_by=auth_uid)
    if redeemed is None:
        return {"status": _classify_link_token_failure(token)}

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

    repo = get_link_token_repo()
    peek = repo.get(token)
    if peek is None:
        return {"status": "invalid"}
    if peek.direction != "web_to_tg":
        return {"status": "wrong_direction"}

    redeemed = repo.redeem(token, redeemed_by=str(telegram_id))
    if redeemed is None:
        return {"status": _classify_link_token_failure(token)}

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
    get_auth_link_codes_repo().create(
        code, telegram_id, now + timedelta(seconds=LINK_CODE_TTL_SECONDS),
    )


def get_link_code(code: str) -> Optional[dict]:
    return get_auth_link_codes_repo().get(code)


def delete_link_code(code: str) -> None:
    get_auth_link_codes_repo().delete(code)
