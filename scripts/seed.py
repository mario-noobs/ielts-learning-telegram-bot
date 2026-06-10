"""Seed the local Firebase emulators with deterministic demo data.

Run via `make seed`, which exports FIRESTORE_EMULATOR_HOST and
FIREBASE_AUTH_EMULATOR_HOST before invoking this script. All seed docs use
deterministic IDs so running this twice does NOT create duplicates — the
second run simply overwrites the existing docs.

Data sources:
  - seeds/users.json           (3 demo users)
  - seeds/vocabulary.json      ({uid -> list of word docs})
  - seeds/quiz_history.json    ({uid -> list of quiz docs})
  - seeds/writing_history.json ({uid -> list of writing docs})
  - seeds/groups.json          (1 demo group)
  - seeds/challenges.json      ({group_id -> list of challenge docs})

Also creates Firebase Auth users in the emulator via firebase-admin.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin import firestore
from google.auth.credentials import AnonymousCredentials

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SEEDS_DIR = ROOT / "seeds"

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "ielts-bot-dev")
FIRESTORE_HOST = os.environ.get("FIRESTORE_EMULATOR_HOST", "localhost:8080")
AUTH_HOST = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")

DEMO_AUTH_USERS = [
    {"uid": "demo-student-auth", "email": "demo@ielts.test", "password": "demo1234",
     "displayName": "Demo Student"},
    {"uid": "demo-advanced-auth", "email": "advanced@ielts.test",
     "password": "demo1234", "displayName": "Demo Advanced"},
    {"uid": "demo-teacher-auth", "email": "teacher@ielts.test",
     "password": "demo1234", "displayName": "Demo Teacher"},
]


class _EmulatorCredential(credentials.Base):
    def get_credential(self):
        return AnonymousCredentials()


def _ensure_admin_app() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            _EmulatorCredential(), options={"projectId": PROJECT_ID}
        )


def _die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _load(name: str) -> Any:
    path = SEEDS_DIR / name
    if not path.exists():
        _die(f"missing seed file {path}")
    with path.open() as f:
        return json.load(f)


def _init_firestore():
    """Initialize firebase-admin pointing at the emulator."""
    if "FIRESTORE_EMULATOR_HOST" not in os.environ:
        _die(
            "FIRESTORE_EMULATOR_HOST is not set. Run via `make seed` or export "
            "FIRESTORE_EMULATOR_HOST=localhost:8080 first."
        )
    _ensure_admin_app()
    return firestore.client()


def _parse_dt(value: Any) -> Any:
    """Convert ISO-8601 strings to datetime; leave everything else unchanged."""
    if isinstance(value, str) and value.endswith("Z") and "T" in value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if isinstance(value, dict):
        return {k: _parse_dt(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_parse_dt(v) for v in value]
    return value


def seed_auth() -> None:
    """Create deterministic demo users in the Firebase Auth emulator."""
    if "FIREBASE_AUTH_EMULATOR_HOST" not in os.environ:
        _die(
            "FIREBASE_AUTH_EMULATOR_HOST is not set. Run via `make seed` or export "
            "FIREBASE_AUTH_EMULATOR_HOST=localhost:9099 first."
        )
    _ensure_admin_app()

    # Wipe existing accounts to keep seed deterministic. This only affects the
    # local emulator — it has no effect on any real Firebase project.
    for page in auth.list_users().iterate_all():
        auth.delete_user(page.uid)

    for user in DEMO_AUTH_USERS:
        auth.create_user(
            uid=user["uid"],
            email=user["email"],
            password=user["password"],
            display_name=user["displayName"],
            email_verified=True,
        )
        print(f"  auth: created {user['email']} (uid={user['uid']})")


def seed_users(db) -> None:
    users = _load("users.json")
    for user in users:
        uid = user["id"]
        data = {k: _parse_dt(v) for k, v in user.items() if k != "id"}
        db.collection("users").document(uid).set(data)
        # auth mapping so get_user_by_auth_uid works
        if auth_uid := user.get("auth_uid"):
            db.collection("auth_mapping").document(auth_uid).set({"user_id": uid})
        print(f"  users: {uid}")


def seed_postgres_users() -> None:
    from services import local_auth_service
    from services.db import get_sync_session
    from services.db.models.user import User

    auth_by_email = {user["email"]: user for user in DEMO_AUTH_USERS}
    users = _load("users.json")

    with get_sync_session() as session, session.begin():
        for user in users:
            auth_user = auth_by_email.get(user["email"])
            password_hash = (
                local_auth_service.hash_password(auth_user["password"])
                if auth_user else None
            )
            values = {
                "name": user.get("name", ""),
                "username": user.get("username", ""),
                "email": user.get("email"),
                "auth_uid": user.get("auth_uid"),
                "group_id": user.get("group_id"),
                "target_band": user.get("target_band", 7.0),
                "topics": user.get("topics", []),
                "daily_time": user.get("daily_time"),
                "timezone": user.get("timezone"),
                "streak": user.get("streak", 0),
                "last_active": _parse_dt(user.get("last_active")),
                "total_words": user.get("total_words", 0),
                "total_quizzes": user.get("total_quizzes", 0),
                "total_correct": user.get("total_correct", 0),
                "challenge_wins": user.get("challenge_wins", 0),
                "created_at": _parse_dt(user.get("created_at")),
                "password_hash": password_hash,
                "local_auth": auth_user is not None,
                "email_verified": auth_user is not None,
            }

            row = session.get(User, user["id"])
            if row is None:
                session.add(User(id=user["id"], **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)

            print(f"  postgres users: {user['id']}")


def seed_vocabulary(db) -> None:
    vocab = _load("vocabulary.json")
    now = datetime.now(timezone.utc)
    total = 0
    for uid, words in vocab.items():
        total_for_user = 0
        for word in words:
            word_id = word["id"]
            data = {k: _parse_dt(v) for k, v in word.items() if k != "id"}
            data.setdefault("added_at", now)
            data.setdefault("srs_next_review", now)
            (db.collection("users").document(uid)
             .collection("vocabulary").document(word_id).set(data))
            total_for_user += 1
        # Keep total_words in sync with seeded docs (idempotent-safe: set, not increment)
        db.collection("users").document(uid).update({"total_words": total_for_user})
        total += total_for_user
    print(f"  vocabulary: {total} words across {len(vocab)} users")


def seed_quiz_history(db) -> None:
    data = _load("quiz_history.json")
    total = 0
    for uid, quizzes in data.items():
        for quiz in quizzes:
            qid = quiz["id"]
            doc = {k: _parse_dt(v) for k, v in quiz.items() if k != "id"}
            (db.collection("users").document(uid)
             .collection("quiz_history").document(qid).set(doc))
            total += 1
    print(f"  quiz_history: {total} entries")


def seed_writing_history(db) -> None:
    data = _load("writing_history.json")
    total = 0
    for uid, essays in data.items():
        for essay in essays:
            wid = essay["id"]
            doc = {k: _parse_dt(v) for k, v in essay.items() if k != "id"}
            (db.collection("users").document(uid)
             .collection("writing_history").document(wid).set(doc))
            total += 1
    print(f"  writing_history: {total} essays")


def seed_groups(db) -> None:
    groups = _load("groups.json")
    for group in groups:
        gid = group["id"]
        data = {k: _parse_dt(v) for k, v in group.items() if k != "id"}
        db.collection("groups").document(gid).set(data)
        print(f"  groups: {gid}")


def seed_challenges(db) -> None:
    data = _load("challenges.json")
    total = 0
    for gid, challenges in data.items():
        for challenge in challenges:
            cid = challenge["id"]
            doc = {k: _parse_dt(v) for k, v in challenge.items() if k != "id"}
            (db.collection("groups").document(gid)
             .collection("challenges").document(cid).set(doc))
            total += 1
    print(f"  challenges: {total} challenges")


def main() -> int:
    print(f"Seeding Firebase emulator at {FIRESTORE_HOST} (project={PROJECT_ID})")
    print("→ Firebase Auth emulator")
    seed_auth()

    db = _init_firestore()
    print("→ Firestore")
    seed_users(db)
    seed_vocabulary(db)
    seed_quiz_history(db)
    seed_writing_history(db)
    seed_groups(db)
    seed_challenges(db)
    print("→ Postgres")
    seed_postgres_users()

    print("Done.")
    print()
    print("Demo credentials:")
    for u in DEMO_AUTH_USERS:
        print(f"  {u['email']}  /  {u['password']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
