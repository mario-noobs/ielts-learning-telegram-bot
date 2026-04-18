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


def _get_db():
    """Lazy-init the Firestore client.

    This mirrors the pre-existing ``services.firebase_service._get_db``
    pattern — one app, one client, shared across every repo.

    Emulator mode: when ``FIRESTORE_EMULATOR_HOST`` /
    ``FIREBASE_AUTH_EMULATOR_HOST`` are set in the environment,
    firebase-admin auto-routes all traffic to the local emulator and
    we skip real service-account credentials. Just initialize the app
    with an explicit projectId so collection paths resolve correctly.
    """
    global _db
    if _db is None:
        if getattr(config, "USE_FIREBASE_EMULATOR", False):
            if not firebase_admin._apps:
                firebase_admin.initialize_app(
                    options={"projectId": config.FIREBASE_EMULATOR_PROJECT_ID},
                )
            _db = firestore.client()
            return _db

        json_b64 = getattr(config, "FIREBASE_CREDENTIALS_JSON", None)
        if json_b64:
            cred_dict = json.loads(base64.b64decode(json_b64))
            cred = credentials.Certificate(cred_dict)
        else:
            cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
        if not firebase_admin._apps:
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


__all__ = ["FirestoreUserRepo", "_get_db"]
