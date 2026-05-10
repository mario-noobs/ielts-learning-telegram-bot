"""Feature flag service — Firestore-backed flags with a 60s in-memory cache.

Flags live in the `feature_flags/{flag_name}` Firestore collection and are
read via a short-lived process-local cache to avoid round trips on every
evaluation. The cache is a module-level dict keyed by flag name. Cache
hits are fully in-process (dict lookup under a lock) and return in well
under 20ms p95 — effectively memory-access latency. Cache misses do a
single Firestore `document().get()` and then populate the cache for
`FEATURE_FLAG_CACHE_TTL_SECONDS` (default 60s).

Evaluation rules (in order):
    1. Flag missing in Firestore -> False (safe default — unknown flag is OFF)
    2. `enabled = False` -> False (kill-switch wins over everything)
    3. `uid in uid_allowlist` -> True (explicit allowlist beats pct gating)
    4. `uid is None` -> `enabled` (global evaluation, no bucketing)
    5. Otherwise -> `sha256(f"{flag}:{uid}") % 100 < rollout_pct`
       Bucketing uses sha256 for stability across processes and Python
       versions (the built-in `hash()` is per-process randomized and would
       give a user different buckets after a restart).

Admin workflow:
    * `scripts/flags.py` exposes list / get / set / delete — no Firestore
      console access required.
    * Toggling a flag does not require a redeploy; the change propagates to
      every process within `FEATURE_FLAG_CACHE_TTL_SECONDS`.

Planned flags (not created by this module — documented for the next sprint):
    * `design_system_v2`         — M6, route web to the new design system
    * `reading_lab`               — M9, gate the Reading Lab feature

US-M8.6 retired the `postgres_dual_write_users` and `postgres_read_users`
stubs once the cutover landed: Postgres is unconditionally authoritative
for the user core doc, no flag gates the read/write path.

Thread-safety: reads against `_cache` happen under `_cache_lock`, as do
writes (first-fill and refresh after expiry). Locking is cheap compared
to a Firestore RPC and keeps the cache coherent when multiple request
threads race on a cold key.

Latency note for callers on bot hot paths: the first-ever read of a flag
(or the first read after TTL expiry) does a Firestore round trip — the
scheduler code path should treat that miss as non-free. Follow-up reads
return from cache.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ─── DTO ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FeatureFlag:
    """Immutable view of a single feature flag."""

    name: str
    enabled: bool = False
    rollout_pct: int = 0
    uid_allowlist: tuple[str, ...] = ()
    description: str = ""
    # Firestore server timestamp (DatetimeWithNanoseconds) or None before first write.
    updated_at: Optional[object] = None

    def to_dict(self) -> dict:
        """Return a plain dict suitable for JSON/CLI display."""
        d = asdict(self)
        d["uid_allowlist"] = list(self.uid_allowlist)
        return d


# ─── Module-level cache ───────────────────────────────────────────────

# { flag_name: (flag_or_None, expires_at_monotonic) }
# None sentinel is cached too so that a missing flag does not hammer
# Firestore on every evaluation.
_cache: dict[str, tuple[Optional[FeatureFlag], float]] = {}
_cache_lock = threading.Lock()


def _now() -> float:
    """Monotonic clock in seconds. Patched in tests for TTL expiry."""
    return time.monotonic()


def _ttl() -> int:
    # Read lazily so tests that monkeypatch config after import still win.
    import config
    return int(getattr(config, "FEATURE_FLAG_CACHE_TTL_SECONDS", 60))


def clear_cache() -> None:
    """Drop all cached flags. Intended for tests and admin CLI after a write."""
    with _cache_lock:
        _cache.clear()


# ─── Firestore adapters ───────────────────────────────────────────────


def _doc_to_flag(name: str, data: dict) -> FeatureFlag:
    allowlist = data.get("uid_allowlist") or []
    # Coerce to tuple[str, ...] for immutability / hashability.
    return FeatureFlag(
        name=name,
        enabled=bool(data.get("enabled", False)),
        rollout_pct=int(data.get("rollout_pct", 0) or 0),
        uid_allowlist=tuple(str(u) for u in allowlist),
        description=str(data.get("description", "") or ""),
        updated_at=data.get("updated_at"),
    )


def _fetch_flag(name: str) -> Optional[FeatureFlag]:
    """Read a single flag from Postgres. Returns None if the row is missing."""
    from services.repositories import get_feature_flags_repo

    try:
        row = get_feature_flags_repo().get(name)
    except Exception as e:
        # Fail closed — a DB outage must not crash every feature check.
        logger.warning("feature_flag fetch failed for %r: %s", name, e)
        return None

    if row is None:
        return None
    return _doc_to_flag(name, row)


def _get_with_cache(name: str) -> Optional[FeatureFlag]:
    now = _now()
    with _cache_lock:
        cached = _cache.get(name)
        if cached is not None and cached[1] > now:
            return cached[0]

    # Miss / expired — fetch outside the lock so a slow Firestore call
    # does not serialize other cache reads.
    flag = _fetch_flag(name)

    with _cache_lock:
        _cache[name] = (flag, _now() + _ttl())
    return flag


# ─── Public API ───────────────────────────────────────────────────────


def _bucket(flag: str, uid: str) -> int:
    """Stable 0..99 bucket for (flag, uid). Same inputs -> same bucket,
    across processes and Python versions.
    """
    key = f"{flag}:{uid}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    # Take first 8 bytes as an unsigned int, mod 100 -> [0, 99].
    return int.from_bytes(digest[:8], "big") % 100


def is_enabled(flag: str, uid: Optional[str] = None) -> bool:
    """Evaluate whether `flag` is enabled for `uid`.

    Evaluation order:
        1. Missing flag -> False (safe default)
        2. enabled=False -> False
        3. uid in allowlist -> True
        4. uid is None -> enabled (global)
        5. Else -> sha256(flag:uid) % 100 < rollout_pct
    """
    f = _get_with_cache(flag)
    if f is None:
        return False
    if not f.enabled:
        return False
    if uid is not None and uid in f.uid_allowlist:
        return True
    if uid is None:
        # No user context — treat as a global switch.
        return f.enabled
    if f.rollout_pct <= 0:
        return False
    if f.rollout_pct >= 100:
        return True
    return _bucket(flag, uid) < f.rollout_pct


def get_flag(flag: str) -> Optional[FeatureFlag]:
    """Return the full flag DTO, or None if not set. Cached."""
    return _get_with_cache(flag)


def list_flags() -> list[FeatureFlag]:
    """List every flag from Postgres. Bypasses the cache — intended for admin UIs."""
    from services.repositories import get_feature_flags_repo

    try:
        rows = get_feature_flags_repo().list_all()
    except Exception as e:
        logger.warning("feature_flag list failed: %s", e)
        return []

    out = [_doc_to_flag(r["name"], r) for r in rows]
    # Stable ordering for CLI output.
    out.sort(key=lambda f: f.name)
    return out


def set_flag(
    flag: str,
    *,
    enabled: bool = False,
    rollout_pct: int = 0,
    uid_allowlist: Optional[list[str]] = None,
    description: str = "",
) -> FeatureFlag:
    """Upsert a feature flag. Invalidates the in-memory cache for `flag`.

    Rollout percentage is clamped to [0, 100]. Allowlist entries are
    coerced to strings (Firebase Auth UIDs are strings).
    """
    from services.repositories import get_feature_flags_repo

    pct = max(0, min(100, int(rollout_pct)))
    allow = [str(u) for u in (uid_allowlist or [])]

    row = get_feature_flags_repo().upsert(
        flag,
        enabled=bool(enabled),
        rollout_pct=pct,
        uid_allowlist=allow,
        description=description or "",
    )

    # Invalidate the single entry — next read re-populates.
    with _cache_lock:
        _cache.pop(flag, None)

    return FeatureFlag(
        name=flag,
        enabled=bool(enabled),
        rollout_pct=pct,
        uid_allowlist=tuple(allow),
        description=description or "",
        updated_at=row.get("updated_at"),
    )


def delete_flag(flag: str) -> None:
    """Delete a feature flag row and invalidate its cache entry."""
    from services.repositories import get_feature_flags_repo

    get_feature_flags_repo().delete(flag)
    with _cache_lock:
        _cache.pop(flag, None)


# Silence the unused-import warning for `field` so the dataclass import
# stays intentional if we later add default_factory-backed fields.
_ = field
