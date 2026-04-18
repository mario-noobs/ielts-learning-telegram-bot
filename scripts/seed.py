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

Also creates Firebase Auth users in the emulator via the emulator's
identitytoolkit REST endpoint. These dependencies are stdlib-only aside from
firebase-admin and requests.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import firebase_admin
import requests
from firebase_admin import firestore

ROOT = Path(__file__).resolve().parent.parent
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
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": PROJECT_ID})
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
    """Upsert demo users in the Firebase Auth emulator via REST.

    The Auth emulator's identitytoolkit endpoints accept any bearer token;
    we pass 'owner' as the standard emulator admin token. Calls are idempotent:
    if the user already exists we delete-then-create to keep a known password.
    """
    base = f"http://{AUTH_HOST}/identitytoolkit.googleapis.com/v1"
    admin_base = (
        f"http://{AUTH_HOST}/emulator/v1/projects/{PROJECT_ID}/accounts"
    )
    headers = {"Authorization": "Bearer owner"}

    # Wipe existing accounts to keep seed deterministic. This only affects the
    # local emulator — it has no effect on any real Firebase project.
    try:
        requests.delete(admin_base, headers=headers, timeout=5)
    except requests.RequestException as exc:
        print(f"WARN: could not clear emulator accounts: {exc}", file=sys.stderr)

    for user in DEMO_AUTH_USERS:
        payload = {
            "localId": user["uid"],
            "email": user["email"],
            "password": user["password"],
            "displayName": user["displayName"],
            "emailVerified": True,
        }
        url = f"{base}/accounts:signUp?key=fake-api-key"
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code >= 400:
            # Already exists — that's fine in the idempotent case.
            body = r.text
            if "EMAIL_EXISTS" in body or "DUPLICATE_LOCAL_ID" in body:
                print(f"  auth: {user['email']} already exists (ok)")
                continue
            _die(f"auth seed failed for {user['email']}: {body}")
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

    print("Done.")
    print()
    print("Demo credentials:")
    for u in DEMO_AUTH_USERS:
        print(f"  {u['email']}  /  {u['password']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
