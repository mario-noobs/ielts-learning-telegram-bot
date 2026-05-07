"""Repo-factory wiring (US-M8.6).

After the cutover, ``get_user_repo()`` must return ``PostgresUserRepo``
by default — this is the contract every ``firebase_service`` shim and
every admin-tooling code path relies on.

This module deliberately does NOT use the ``fake_db`` fixture from
``conftest.py``: that fixture seeds the user-repo singleton with the
Firestore impl so subcollection tests keep working against the in-memory
fake. Here we want to assert the factory's *default* behavior, so we
clear singletons by hand.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset_singletons():
    from services.repositories import _reset_singletons_for_tests

    _reset_singletons_for_tests()
    yield
    _reset_singletons_for_tests()


def test_factory_returns_postgres_user_repo() -> None:
    from services.repositories import get_user_repo
    from services.repositories.postgres.user_repo import PostgresUserRepo

    assert isinstance(get_user_repo(), PostgresUserRepo)


def test_factory_returns_singleton() -> None:
    from services.repositories import get_user_repo

    assert get_user_repo() is get_user_repo()


def test_firebase_service_shims_delegate_through_factory(monkeypatch) -> None:
    """``firebase_service.get_user`` etc. must hit whatever
    ``get_user_repo()`` currently returns — verify by swapping the
    singleton and confirming the shim sees the swap."""
    from services import firebase_service
    from services import repositories as repositories_mod

    class _Sentinel:
        def __init__(self) -> None:
            self.calls: list[tuple] = []

        def get(self, user_id):
            self.calls.append(("get", user_id))
            return None

        def get_by_auth_uid(self, auth_uid):
            self.calls.append(("get_by_auth_uid", auth_uid))
            return None

    sentinel = _Sentinel()
    monkeypatch.setattr(repositories_mod, "_user_repo", sentinel)

    firebase_service.get_user(42)
    firebase_service.get_user_by_auth_uid("uid-x")

    assert sentinel.calls == [("get", 42), ("get_by_auth_uid", "uid-x")]
