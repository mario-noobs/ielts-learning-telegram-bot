"""Tests for services/feature_flag_service.py.

Mocks Firestore via the `_fetch_flag` / `_get_db` seam and freezes
`time.monotonic` via the module-level `_now` hook so TTL expiry can be
exercised deterministically.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from services import feature_flag_service as ffs


@pytest.fixture(autouse=True)
def _reset_cache():
    ffs.clear_cache()
    yield
    ffs.clear_cache()


# ─── Fake Firestore plumbing ────────────────────────────────────────


class _FakeDoc:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None
        self.id = data.get("_name") if data else None

    def to_dict(self):
        # Strip private fields used by the fake only.
        if self._data is None:
            return {}
        return {k: v for k, v in self._data.items() if not k.startswith("_")}


class _FakeDocRef:
    def __init__(self, collection, name):
        self._collection = collection
        self._name = name

    def get(self):
        return _FakeDoc(self._collection._docs.get(self._name))

    def set(self, payload):
        self._collection._docs[self._name] = {"_name": self._name, **payload}
        self._collection._write_count += 1

    def delete(self):
        self._collection._docs.pop(self._name, None)


class _FakeCollection:
    def __init__(self):
        self._docs: dict[str, dict] = {}
        self._read_count = 0
        self._write_count = 0

    def document(self, name):
        return _FakeDocRef(self, name)

    def stream(self):
        for name, data in self._docs.items():
            yield _FakeDoc({"_name": name, **{k: v for k, v in data.items() if k != "_name"}})


class _FakeDB:
    def __init__(self):
        self._col = _FakeCollection()

    def collection(self, name):
        assert name == "feature_flags"
        self._col._read_count += 1  # counts collection accesses (set+get+stream)
        return self._col


@pytest.fixture
def fake_db():
    db = _FakeDB()
    # Patch the firebase_service._get_db seam. feature_flag_service imports
    # firebase_service lazily inside each function, so this works.
    with patch("services.firebase_service._get_db", return_value=db):
        yield db


# ─── Evaluation rules ────────────────────────────────────────────────


class TestIsEnabledRules:
    def test_missing_flag_is_false(self, fake_db):
        assert ffs.is_enabled("ghost", "user-1") is False

    def test_disabled_flag_is_false_even_for_allowlisted_uid(self, fake_db):
        ffs.set_flag(
            "f",
            enabled=False,
            rollout_pct=100,
            uid_allowlist=["vip"],
            description="off",
        )
        assert ffs.is_enabled("f", "vip") is False

    def test_pct_zero_is_false_for_non_allowlisted(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=0)
        # Try several uids — none should flip true.
        for uid in [f"u{i}" for i in range(20)]:
            assert ffs.is_enabled("f", uid) is False

    def test_pct_zero_allowlist_wins(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=0, uid_allowlist=["vip"])
        assert ffs.is_enabled("f", "vip") is True
        assert ffs.is_enabled("f", "regular") is False

    def test_pct_hundred_is_true_for_everyone(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=100)
        for uid in [f"u{i}" for i in range(20)]:
            assert ffs.is_enabled("f", uid) is True

    def test_uid_none_returns_enabled(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=50)
        assert ffs.is_enabled("f", None) is True
        ffs.set_flag("f", enabled=False, rollout_pct=100)
        assert ffs.is_enabled("f", None) is False

    def test_bucketing_is_stable_across_calls(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=50)
        # Call 100 times for the same uid — result must never flip.
        uid = "same-user"
        first = ffs.is_enabled("f", uid)
        for _ in range(100):
            assert ffs.is_enabled("f", uid) is first

    def test_bucketing_distribution_matches_pct(self, fake_db):
        # With pct=30 and 2000 uids, roughly 30% should be true. Allow ±5% slack.
        ffs.set_flag("f", enabled=True, rollout_pct=30)
        hits = sum(1 for i in range(2000) if ffs.is_enabled("f", f"u{i}"))
        assert 500 <= hits <= 700  # 25%–35% band

    def test_different_flags_decorrelate_for_same_user(self, fake_db):
        ffs.set_flag("flag_a", enabled=True, rollout_pct=50)
        ffs.set_flag("flag_b", enabled=True, rollout_pct=50)
        # Across many users, the two flags should not be perfectly correlated.
        a_hits = [ffs.is_enabled("flag_a", f"u{i}") for i in range(500)]
        b_hits = [ffs.is_enabled("flag_b", f"u{i}") for i in range(500)]
        # Agreement rate should be ~50% (both true or both false). If the
        # two flags shared a bucket they'd agree 100%. Any reasonable spread
        # will land in [30%, 70%].
        agree = sum(1 for a, b in zip(a_hits, b_hits) if a == b)
        assert 150 <= agree <= 350


# ─── Cache behavior ──────────────────────────────────────────────────


class TestCache:
    def test_cache_hits_avoid_firestore(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=100)
        # set_flag invalidates the cache, so next read is a miss.
        read_count = MagicMock(side_effect=ffs._fetch_flag)
        with patch("services.feature_flag_service._fetch_flag", read_count):
            for _ in range(10):
                assert ffs.is_enabled("f", "u") is True
            assert read_count.call_count == 1, "expected a single Firestore read"

    def test_cache_expiry_triggers_refetch(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=100)
        fake_now = [1000.0]

        def now():
            return fake_now[0]

        read_count = MagicMock(side_effect=ffs._fetch_flag)
        with patch("services.feature_flag_service._now", now), \
             patch("services.feature_flag_service._fetch_flag", read_count):
            assert ffs.is_enabled("f", "u") is True  # miss #1
            fake_now[0] += 30  # still within TTL
            assert ffs.is_enabled("f", "u") is True  # cache hit
            assert read_count.call_count == 1

            fake_now[0] += 31  # now 61s since first fetch -> expired
            assert ffs.is_enabled("f", "u") is True  # miss #2
            assert read_count.call_count == 2

    def test_missing_flag_is_cached_as_negative(self, fake_db):
        """Missing-flag lookups must not stampede Firestore."""
        read_count = MagicMock(side_effect=ffs._fetch_flag)
        with patch("services.feature_flag_service._fetch_flag", read_count):
            for _ in range(10):
                assert ffs.is_enabled("ghost", "u") is False
            assert read_count.call_count == 1

    def test_set_flag_invalidates_cache(self, fake_db):
        ffs.set_flag("f", enabled=False, rollout_pct=0)
        assert ffs.is_enabled("f", "u") is False
        ffs.set_flag("f", enabled=True, rollout_pct=100)
        # No stale False here — the upsert must evict.
        assert ffs.is_enabled("f", "u") is True

    def test_delete_flag_invalidates_cache(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=100)
        assert ffs.is_enabled("f", "u") is True
        ffs.delete_flag("f")
        assert ffs.is_enabled("f", "u") is False


# ─── DTO helpers ─────────────────────────────────────────────────────


class TestDTOAndAdmin:
    def test_get_flag_returns_dto(self, fake_db):
        ffs.set_flag(
            "f",
            enabled=True,
            rollout_pct=42,
            uid_allowlist=["a", "b"],
            description="hello",
        )
        flag = ffs.get_flag("f")
        assert flag is not None
        assert flag.name == "f"
        assert flag.enabled is True
        assert flag.rollout_pct == 42
        assert flag.uid_allowlist == ("a", "b")
        assert flag.description == "hello"

    def test_get_flag_missing_is_none(self, fake_db):
        assert ffs.get_flag("absent") is None

    def test_list_flags_sorted(self, fake_db):
        ffs.set_flag("zeta", enabled=True)
        ffs.set_flag("alpha", enabled=False)
        ffs.set_flag("mid", enabled=True, rollout_pct=50)
        names = [f.name for f in ffs.list_flags()]
        assert names == ["alpha", "mid", "zeta"]

    def test_set_flag_clamps_pct(self, fake_db):
        hi = ffs.set_flag("f", enabled=True, rollout_pct=250)
        assert hi.rollout_pct == 100
        lo = ffs.set_flag("f", enabled=True, rollout_pct=-5)
        assert lo.rollout_pct == 0

    def test_to_dict_is_json_friendly(self, fake_db):
        ffs.set_flag("f", enabled=True, rollout_pct=10, uid_allowlist=["x"])
        flag = ffs.get_flag("f")
        d = flag.to_dict()
        assert d["name"] == "f"
        assert d["uid_allowlist"] == ["x"]


# ─── Fail-closed behavior ────────────────────────────────────────────


class TestFailClosed:
    def test_firestore_exception_returns_false(self):
        # No fake_db fixture — we raise from _get_db directly.
        broken = MagicMock(side_effect=RuntimeError("firestore down"))
        with patch("services.firebase_service._get_db", broken):
            assert ffs.is_enabled("any_flag", "u") is False
            # list_flags should swallow and return empty, not raise.
            assert ffs.list_flags() == []


# ─── Bucketing primitive ─────────────────────────────────────────────


class TestBucket:
    def test_bucket_is_in_range(self):
        for i in range(200):
            b = ffs._bucket("flag", f"u{i}")
            assert 0 <= b < 100

    def test_bucket_is_deterministic(self):
        assert ffs._bucket("f", "u") == ffs._bucket("f", "u")

    def test_bucket_differs_per_flag(self):
        # Should differ for at least one uid across a sample; collisions
        # on any single pair are fine, full agreement would be a bug.
        diffs = sum(
            1
            for i in range(100)
            if ffs._bucket("flag_a", f"u{i}") != ffs._bucket("flag_b", f"u{i}")
        )
        assert diffs > 50


# ─── Sanity: no accidental hash() usage ──────────────────────────────


def test_bucket_stable_across_simulated_process_restart(fake_db):
    """Built-in hash() is salted per-process; sha256 is not. Simulating a
    restart via importlib.reload would re-seed hash() and break bucketing
    if we regressed to hash(). sha256 gives byte-identical output.
    """
    import hashlib

    expected = int.from_bytes(
        hashlib.sha256(b"mf:user-42").digest()[:8], "big"
    ) % 100
    assert ffs._bucket("mf", "user-42") == expected


# Make `SimpleNamespace` import actually used (silences linters on some
# setups where the fixture is imported but unused).
_ = SimpleNamespace
