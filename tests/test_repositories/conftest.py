"""Fixtures for the repositories test suite.

Builds a hand-rolled fake Firestore client that supports the narrow
subset of the SDK actually used by the repository implementations:
- ``collection(name).document(id).get()``
- ``.set(body)``, ``.update(data)``, ``.delete()``
- ``.collection(sub).document(id?)`` for subcollections
- ``.where(...)``, ``.order_by(...)``, ``.limit(n)``, ``.stream()``
- ``.start_after(cursor_dict)``
- ``firestore.Increment(n)`` and ``firestore.ArrayUnion(items)``
- ``firestore.Query.DESCENDING`` / ``ASCENDING``
- ``@firestore.transactional`` (executes the function eagerly,
  passing an object that has ``.get()``/``.set()``/``.update()`` which
  delegate to the underlying docs — good enough to prove control flow).

The fake is deliberately minimal; it's not a production Firestore
emulator. Tests that need to exercise true server semantics (indexes,
rules, retries) belong in a higher-level integration test later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Optional
from unittest.mock import patch

import pytest

# ─── Sentinels ───────────────────────────────────────────────────────

class _Increment:
    """Stand-in for ``firebase_admin.firestore.Increment``."""

    def __init__(self, amount: int) -> None:
        self.amount = amount


class _ArrayUnion:
    def __init__(self, items: list) -> None:
        self.items = list(items)


# ─── Snapshot ────────────────────────────────────────────────────────

class FakeSnapshot:
    def __init__(self, doc_id: str, data: Optional[dict]) -> None:
        self.id = doc_id
        self._data = None if data is None else dict(data)

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> Optional[dict]:
        return None if self._data is None else dict(self._data)


# ─── Document ────────────────────────────────────────────────────────

class FakeDocument:
    def __init__(self, collection: "FakeCollection", doc_id: str) -> None:
        self._collection = collection
        self.id = doc_id

    # Read
    def get(self, transaction=None) -> FakeSnapshot:
        data = self._collection._docs.get(self.id)
        return FakeSnapshot(self.id, data)

    # Write
    def set(self, data: dict, merge: bool = False) -> None:
        if merge and self.id in self._collection._docs:
            existing = self._collection._docs[self.id]
            merged = dict(existing)
            for k, v in data.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k] = {**merged[k], **v}
                else:
                    merged[k] = v
            self._collection._docs[self.id] = merged
        else:
            self._collection._docs[self.id] = dict(data)

    def update(self, data: dict) -> None:
        if self.id not in self._collection._docs:
            raise KeyError(f"document {self.id!r} does not exist")
        current = self._collection._docs[self.id]
        for key, value in data.items():
            if isinstance(value, _Increment):
                current[key] = current.get(key, 0) + value.amount
            elif isinstance(value, _ArrayUnion):
                existing = list(current.get(key, []))
                for item in value.items:
                    if item not in existing:
                        existing.append(item)
                current[key] = existing
            elif "." in key:
                # nested path like "examples_by_band.B2"
                parts = key.split(".")
                cursor = current
                for part in parts[:-1]:
                    cursor = cursor.setdefault(part, {})
                cursor[parts[-1]] = value
            else:
                current[key] = value

    def delete(self) -> None:
        self._collection._docs.pop(self.id, None)

    # Subcollections
    def collection(self, name: str) -> "FakeCollection":
        key = (self._collection.path, self.id, name)
        store = self._collection._client._collections
        if key not in store:
            store[key] = FakeCollection(self._collection._client, name, parent=key)
        return store[key]


# ─── Collection / Query ──────────────────────────────────────────────

class FakeCollection:
    def __init__(
        self,
        client: "FakeFirestoreClient",
        name: str,
        parent: tuple = (),
    ) -> None:
        self._client = client
        self.name = name
        self.path = parent + (name,)
        self._docs: dict[str, dict] = {}
        self._auto_id_seq = 0

    def document(self, doc_id: Optional[str] = None) -> FakeDocument:
        if doc_id is None:
            self._auto_id_seq += 1
            doc_id = f"auto_{self._auto_id_seq:04d}"
        return FakeDocument(self, doc_id)

    def where(self, field: str, op: str, value: Any) -> "FakeQuery":
        return FakeQuery(self).where(field, op, value)

    def order_by(self, field: str, direction: str = "ASCENDING") -> "FakeQuery":
        return FakeQuery(self).order_by(field, direction)

    def limit(self, n: int) -> "FakeQuery":
        return FakeQuery(self).limit(n)

    def stream(self):
        return FakeQuery(self).stream()


class FakeQuery:
    DESCENDING = "DESCENDING"
    ASCENDING = "ASCENDING"

    def __init__(self, collection: FakeCollection) -> None:
        self._collection = collection
        self._filters: list[tuple[str, str, Any]] = []
        self._order_by: Optional[tuple[str, str]] = None
        self._limit: Optional[int] = None
        self._start_after: Optional[dict] = None

    def where(self, field: str, op: str, value: Any) -> "FakeQuery":
        self._filters.append((field, op, value))
        return self

    def order_by(self, field: str, direction: str = "ASCENDING") -> "FakeQuery":
        self._order_by = (field, direction)
        return self

    def limit(self, n: int) -> "FakeQuery":
        self._limit = n
        return self

    def start_after(self, cursor: dict) -> "FakeQuery":
        self._start_after = cursor
        return self

    def get(self, transaction=None) -> list[FakeSnapshot]:
        return list(self.stream())

    def stream(self):
        items = list(self._collection._docs.items())
        # Filter
        for field, op, value in self._filters:
            items = [
                (k, v) for k, v in items if _apply_op(v.get(field), op, value)
            ]
        # Order
        if self._order_by is not None:
            field, direction = self._order_by
            items.sort(
                key=lambda kv: _sort_key(kv[1].get(field)),
                reverse=(direction == "DESCENDING"),
            )
        # Cursor
        if self._start_after is not None and self._order_by is not None:
            field = self._order_by[0]
            direction = self._order_by[1]
            threshold = self._start_after.get(field)
            if direction == "DESCENDING":
                items = [
                    (k, v) for k, v in items
                    if _sort_key(v.get(field)) < _sort_key(threshold)
                ]
            else:
                items = [
                    (k, v) for k, v in items
                    if _sort_key(v.get(field)) > _sort_key(threshold)
                ]
        # Limit
        if self._limit is not None:
            items = items[: self._limit]
        for doc_id, data in items:
            yield FakeSnapshot(doc_id, data)


def _apply_op(field_value: Any, op: str, ref: Any) -> bool:
    if op == "==":
        return field_value == ref
    if op == "!=":
        return field_value != ref
    if op == ">":
        if field_value is None:
            return False
        return field_value > ref
    if op == ">=":
        if field_value is None:
            return False
        return field_value >= ref
    if op == "<":
        if field_value is None:
            return False
        return field_value < ref
    if op == "<=":
        if field_value is None:
            return False
        return field_value <= ref
    raise ValueError(f"unsupported operator: {op!r}")


def _sort_key(value):
    # Treat None as "lowest" so it sorts before real values.
    if value is None:
        return (0, 0)
    return (1, value)


# ─── Transaction shim ────────────────────────────────────────────────

class FakeTransaction:
    """Records writes and applies them eagerly.

    Good enough to verify control flow (e.g., dedupe branches, atomic
    counter updates). It is NOT a real transaction — no isolation, no
    retry.
    """

    def __init__(self) -> None:
        self._pending: list[Callable[[], None]] = []

    def get(self, ref):
        # Both documents and queries support get(transaction=...).
        return ref.get()

    def set(self, ref: FakeDocument, data: dict, merge: bool = False) -> None:
        self._pending.append(lambda: ref.set(data, merge=merge))

    def update(self, ref: FakeDocument, data: dict) -> None:
        self._pending.append(lambda: ref.update(data))

    def _commit(self) -> None:
        for write in self._pending:
            write()
        self._pending.clear()


def _make_transactional(func):
    """Stand-in for ``@firestore.transactional``.

    Calls the wrapped function with a ``FakeTransaction``, commits on
    success, returns whatever the function returned.
    """
    def wrapper(txn):
        result = func(txn)
        txn._commit()
        return result
    return wrapper


# ─── Top-level client ────────────────────────────────────────────────

class FakeFirestoreClient:
    def __init__(self) -> None:
        # Collections keyed by (parent-path, doc-id, name) for
        # subcollections; top-level ones use (name,).
        self._collections: dict[tuple, FakeCollection] = {}

    def collection(self, name: str) -> FakeCollection:
        key = (name,)
        if key not in self._collections:
            self._collections[key] = FakeCollection(self, name)
        return self._collections[key]

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    def get_all(self, refs):
        for ref in refs:
            yield ref.get()


# ─── pytest fixture ──────────────────────────────────────────────────

@pytest.fixture
def fake_db():
    """Patch ``services.repositories.firestore.user_repo._get_db`` and
    the firestore sentinels so repositories write to an in-memory store.

    US-M8.6: ``get_user_repo()`` now returns ``PostgresUserRepo`` by
    default, but this suite tests the Firestore impls in isolation
    against the fake client. Seed the user-repo singleton with a
    ``FirestoreUserRepo()`` so subcollection repos that call
    ``get_user_repo().increment_counters(...)`` route the counter
    bumps back into the same fake Firestore client. The Postgres
    factory is exercised by ``test_postgres_user_repo.py``.
    """
    from services import repositories as repositories_mod
    from services.repositories import _reset_singletons_for_tests
    from services.repositories.firestore import (
        FirestoreUserRepo,
        daily_words_repo as daily_words_repo_mod,
    )
    from services.repositories.firestore import (
        quiz_history_repo as quiz_history_repo_mod,
    )
    from services.repositories.firestore import (
        user_repo as user_repo_mod,
    )
    from services.repositories.firestore import (
        vocab_repo as vocab_repo_mod,
    )
    from services.repositories.firestore import (
        writing_history_repo as writing_history_repo_mod,
    )

    _reset_singletons_for_tests()
    repositories_mod._user_repo = FirestoreUserRepo()
    client = FakeFirestoreClient()

    # Each repo module has its own ``_get_db`` binding (imported from
    # ``user_repo``). Patch them all. Also patch the ``firestore.*``
    # symbols the repos import at module scope so Increment /
    # ArrayUnion / transactional / Query don't touch the real SDK.
    with patch.object(user_repo_mod, "_get_db", return_value=client), \
         patch.object(vocab_repo_mod, "_get_db", return_value=client), \
         patch.object(quiz_history_repo_mod, "_get_db", return_value=client), \
         patch.object(writing_history_repo_mod, "_get_db", return_value=client), \
         patch.object(daily_words_repo_mod, "_get_db", return_value=client), \
         patch(
             "services.repositories.firestore.vocab_repo.firestore.Increment",
             _Increment,
         ), \
         patch(
             "services.repositories.firestore.vocab_repo.firestore.transactional",
             _make_transactional,
         ), \
         patch(
             "services.repositories.firestore.vocab_repo.firestore.Query",
             FakeQuery,
         ), \
         patch(
             "services.repositories.firestore.quiz_history_repo.firestore.Increment",
             _Increment,
         ), \
         patch(
             "services.repositories.firestore.quiz_history_repo.firestore.Query",
             FakeQuery,
         ), \
         patch(
             "services.repositories.firestore.writing_history_repo.firestore.Query",
             FakeQuery,
         ):
        yield client

    _reset_singletons_for_tests()


@pytest.fixture
def frozen_now():
    """Freeze ``datetime.now(timezone.utc)`` inside the Firestore repo
    modules to a single deterministic timestamp.
    """
    fixed = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed.astimezone(tz) if tz else fixed

    with patch(
        "services.repositories.firestore.user_repo.datetime",
        _FrozenDatetime,
    ), patch(
        "services.repositories.firestore.vocab_repo.datetime",
        _FrozenDatetime,
    ), patch(
        "services.repositories.firestore.quiz_history_repo.datetime",
        _FrozenDatetime,
    ), patch(
        "services.repositories.firestore.writing_history_repo.datetime",
        _FrozenDatetime,
    ), patch(
        "services.repositories.firestore.daily_words_repo.datetime",
        _FrozenDatetime,
    ):
        yield fixed
