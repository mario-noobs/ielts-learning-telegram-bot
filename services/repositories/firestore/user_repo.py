"""Firestore implementation of ``UserRepo``."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

import config

from ..dtos import QuizStats, UserDoc
from ..protocols import UserId

# ─── Lazy Firestore client (single source of truth) ─────────────────

_db = None


def _resolve_credential():
    """Return a ``credentials.Certificate`` from the base64 env var or
    the on-disk path, or ``None`` if neither is available.

    Surfaces both the FIREBASE_CREDENTIALS_JSON (containerized deploys)
    and the FIREBASE_CREDENTIALS_PATH file (local dev) without raising
    when the file is missing — callers decide what to do with ``None``.
    """
    import os

    json_b64 = getattr(config, "FIREBASE_CREDENTIALS_JSON", None)
    if json_b64:
        cred_dict = json.loads(base64.b64decode(json_b64))
        return credentials.Certificate(cred_dict)
    path = getattr(config, "FIREBASE_CREDENTIALS_PATH", None)
    if path and os.path.exists(path):
        return credentials.Certificate(path)
    return None


def _get_db():
    """Lazy-init the Firestore client.

    One app, one client, shared across every repo (mirrors the
    ``services.firebase_service._get_db`` pattern).

    Emulator mode: when ``FIRESTORE_EMULATOR_HOST`` /
    ``FIREBASE_AUTH_EMULATOR_HOST`` are set, ``firestore.client()``
    routes traffic to the local emulator regardless of which credential
    we passed at init time. We still try to load real credentials —
    ``firebase_admin.initialize_app`` requires *some* credential or it
    falls through to ``google.auth.default()`` (Application Default
    Credentials), which raises ``DefaultCredentialsError`` when ADC is
    not configured (CI, fresh dev, or a setup that mixes
    ``make bot`` emulator env vars with real Firebase usage).
    """
    global _db
    if _db is None:
        if not firebase_admin._apps:
            cred = _resolve_credential()
            if getattr(config, "USE_FIREBASE_EMULATOR", False):
                opts = {"projectId": config.FIREBASE_EMULATOR_PROJECT_ID}
                if cred is not None:
                    firebase_admin.initialize_app(cred, options=opts)
                else:
                    firebase_admin.initialize_app(options=opts)
            else:
                if cred is None:
                    raise RuntimeError(
                        "Firebase credentials not found. Set "
                        "FIREBASE_CREDENTIALS_JSON (base64) or place a "
                        "service-account JSON at "
                        f"{getattr(config, 'FIREBASE_CREDENTIALS_PATH', '<unset>')!r}.",
                    )
                firebase_admin.initialize_app(cred)
        _db = firestore.client()
    return _db


def _users_col():
    return _get_db().collection("users")


def _auth_mapping_col():
    return _get_db().collection("auth_mapping")


class FirestoreUserRepo:
    """Firestore-backed ``UserRepo``.

    Thin wrapper around ``firebase_admin``; no business logic beyond
    normalizing DTO shape and preserving the current write semantics
    (counter initialization, timestamp defaults).
    """

    def get(self, user_id: UserId) -> Optional[UserDoc]:
        doc = _users_col().document(str(user_id)).get()
        if not doc.exists:
            return None
        return UserDoc.from_snapshot(doc)

    def create(
        self,
        telegram_id: int,
        name: str,
        username: str = "",
        group_id: Optional[int] = None,
        target_band: float = 7.0,
        topics: Optional[list[str]] = None,
    ) -> UserDoc:
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
        _users_col().document(str(telegram_id)).set(user_data)
        return UserDoc.from_dict(str(telegram_id), user_data)

    def update(self, user_id: UserId, data: dict) -> None:
        _users_col().document(str(user_id)).update(data)

    def list_by_group(self, group_id: int) -> list[UserDoc]:
        docs = _users_col().where("group_id", "==", group_id).stream()
        return [UserDoc.from_snapshot(d) for d in docs]

    def list_all(self) -> list[UserDoc]:
        docs = _users_col().stream()
        return [UserDoc.from_snapshot(d) for d in docs]

    def increment_counters(self, user_id: UserId, **deltas: int) -> None:
        if not deltas:
            return
        updates = {field: firestore.Increment(delta) for field, delta in deltas.items()}
        _users_col().document(str(user_id)).update(updates)

    def update_streak(self, user_id: UserId) -> None:
        user = self.get(user_id)
        if not user:
            return
        now = datetime.now(timezone.utc)
        last = user.last_active
        if last is not None:
            # DatetimeWithNanoseconds inherits from datetime, so .date() works
            delta = (now.date() - last.date()).days if hasattr(last, "date") else 1
            if delta == 1:
                new_streak = (user.streak or 0) + 1
            elif delta == 0:
                new_streak = user.streak or 0
            else:
                new_streak = 1
        else:
            new_streak = 1
        self.update(user_id, {"streak": new_streak, "last_active": now})

    def get_quiz_stats(self, user_id: UserId) -> QuizStats:
        user = self.get(user_id)
        if not user:
            return QuizStats(total=0, correct=0, accuracy=0.0)
        total = user.total_quizzes or 0
        correct = user.total_correct or 0
        accuracy = round((correct / total * 100), 1) if total > 0 else 0.0
        return QuizStats(total=total, correct=correct, accuracy=accuracy)

    # ── Web auth ──────────────────────────────────────────────────

    def get_by_auth_uid(self, auth_uid: str) -> Optional[UserDoc]:
        mapping_doc = _auth_mapping_col().document(auth_uid).get()
        if not mapping_doc.exists:
            return None
        user_id = (mapping_doc.to_dict() or {}).get("user_id")
        if not user_id:
            return None
        # user_id may be a numeric telegram_id or a web_<hex> string
        try:
            return self.get(int(user_id))
        except (ValueError, TypeError):
            doc = _users_col().document(user_id).get()
            if doc.exists:
                return UserDoc.from_snapshot(doc)
            return None

    def create_web_user(
        self,
        auth_uid: str,
        email: str,
        name: str,
        target_band: float = 7.0,
        topics: Optional[list[str]] = None,
    ) -> UserDoc:
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
        _users_col().document(user_id).set(user_data)
        _auth_mapping_col().document(auth_uid).set({"user_id": user_id})
        return UserDoc.from_dict(user_id, user_data)

    def link_telegram_to_auth(self, telegram_id: int, auth_uid: str) -> None:
        _auth_mapping_col().document(auth_uid).set({"user_id": str(telegram_id)})
        self.update(telegram_id, {"auth_uid": auth_uid})

    # ── Identity merge subcollection copy (US-M12.1) ──────────────────

    def copy_subcollections(
        self,
        source_id: str,
        target_id: str,
    ) -> dict[str, int]:
        """Copy in-scope subcollection docs from ``source_id`` to ``target_id``.

        Per US-M12.1 business rules:
        - vocabulary: dedupe by lowercased word, keep entry with greater
          ``srs_reps`` (further-along SRS state); tie-break to target
        - quiz_history: append-only union, no dedupe
        - writing_history: append-only union, no dedupe
        - daily_words: keyed by date_str; on conflict, target (Telegram) wins

        Returns counts dict for structlog/audit:
        ``{"vocab_merged", "vocab_dropped", "quiz_merged",
        "writing_merged", "daily_merged", "daily_skipped"}``.

        OOS subcollections (listening_history, reading_sessions,
        daily_plans, progress_snapshots, progress_recommendations,
        quiz_sessions) are intentionally not copied — see docs/postgres.md.
        """
        db = _get_db()
        source_root = db.collection("users").document(source_id)
        target_root = db.collection("users").document(target_id)
        counts = {
            "vocab_merged": 0,
            "vocab_dropped": 0,
            "quiz_merged": 0,
            "writing_merged": 0,
            "daily_merged": 0,
            "daily_skipped": 0,
        }

        # ── vocabulary: dedupe by lowercased word ─────────────────────
        target_vocab = list(target_root.collection("vocabulary").stream())
        target_by_word: dict[str, tuple[str, dict]] = {}
        for doc in target_vocab:
            data = doc.to_dict() or {}
            word = str(data.get("word", "")).strip().lower()
            if word:
                target_by_word[word] = (doc.id, data)
        for doc in source_root.collection("vocabulary").stream():
            data = doc.to_dict() or {}
            word = str(data.get("word", "")).strip().lower()
            if not word:
                continue
            if word in target_by_word:
                target_doc_id, target_data = target_by_word[word]
                source_reps = int(data.get("srs_reps") or 0)
                target_reps = int(target_data.get("srs_reps") or 0)
                if source_reps > target_reps:
                    target_root.collection("vocabulary").document(target_doc_id).set(
                        data,
                    )
                    counts["vocab_merged"] += 1
                else:
                    counts["vocab_dropped"] += 1
            else:
                target_root.collection("vocabulary").document(doc.id).set(data)
                target_by_word[word] = (doc.id, data)
                counts["vocab_merged"] += 1

        # ── quiz_history: append-only union ───────────────────────────
        for doc in source_root.collection("quiz_history").stream():
            target_root.collection("quiz_history").document(doc.id).set(
                doc.to_dict() or {},
            )
            counts["quiz_merged"] += 1

        # ── writing_history: append-only union ────────────────────────
        for doc in source_root.collection("writing_history").stream():
            target_root.collection("writing_history").document(doc.id).set(
                doc.to_dict() or {},
            )
            counts["writing_merged"] += 1

        # ── daily_words: target wins on date conflict ─────────────────
        for doc in source_root.collection("daily_words").stream():
            existing = target_root.collection("daily_words").document(doc.id).get()
            if existing.exists:
                counts["daily_skipped"] += 1
                continue
            target_root.collection("daily_words").document(doc.id).set(
                doc.to_dict() or {},
            )
            counts["daily_merged"] += 1

        return counts

    def vocabulary_count(self, user_id: UserId) -> int:
        """Count vocabulary docs at ``users/{user_id}/vocabulary``.

        Used by the merge orchestrator to recompute ``total_words`` after
        dedupe so the counter doesn't drift from the actual subcollection
        size.
        """
        return sum(
            1 for _ in _users_col().document(str(user_id))
            .collection("vocabulary").stream()
        )


__all__ = ["FirestoreUserRepo", "_get_db"]
