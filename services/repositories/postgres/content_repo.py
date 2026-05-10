"""Postgres repos for static content + system tables (M8 Block E+F #234).

Four caller-facing repos in this single file:

- PostgresReadingQuestionsRepo: per-passage AI question cache.
- PostgresEnrichedWordsRepo: shared word metadata cache.
- PostgresFeatureFlagsRepo: admin-config rollouts.
- PostgresAuthLinkCodesRepo: ephemeral DM↔web link codes.

All repos return dicts to match legacy ``firebase_service`` shape.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from services.db import get_sync_session
from services.db.models import AuthLinkCode, EnrichedWord, FeatureFlag, ReadingQuestion


# ─── Reading questions ─────────────────────────────────────────────────


class PostgresReadingQuestionsRepo:
    """Per-passage AI question cache. One write per passage_id, many reads."""

    def get(self, passage_id: str) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.execute(
                select(ReadingQuestion).where(
                    ReadingQuestion.passage_id == passage_id,
                )
            ).scalar_one_or_none()
        if not row:
            return None
        return {
            "questions_client": list(row.questions_client or []),
            "answer_key": list(row.answer_key or []),
            "cached_at": row.cached_at,
        }

    def save(self, passage_id: str, data: dict) -> None:
        """UPSERT — re-saving overwrites."""
        now = datetime.now(timezone.utc)
        stmt = pg_insert(ReadingQuestion).values(
            passage_id=passage_id,
            questions_client=data.get("questions_client") or [],
            answer_key=data.get("answer_key") or [],
            cached_at=now,
        ).on_conflict_do_update(
            index_elements=["passage_id"],
            set_={
                "questions_client": data.get("questions_client") or [],
                "answer_key": data.get("answer_key") or [],
                "cached_at": now,
            },
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)


# ─── Enriched words ────────────────────────────────────────────────────


_ENRICHED_STRUCTURED = {
    "ipa", "part_of_speech", "definition_en", "definition_vi",
    "syllable_stress", "ielts_tip", "examples_by_band",
    "collocations", "word_family",
}


def _enriched_to_dict(e: EnrichedWord) -> dict[str, Any]:
    return {
        "word": e.word,
        "ipa": e.ipa,
        "part_of_speech": e.part_of_speech,
        "definition_en": e.definition_en,
        "definition_vi": e.definition_vi,
        "syllable_stress": e.syllable_stress,
        "ielts_tip": e.ielts_tip,
        "examples_by_band": dict(e.examples_by_band or {}) if e.examples_by_band else None,
        "collocations": list(e.collocations or []) if e.collocations else None,
        "word_family": list(e.word_family or []) if e.word_family else None,
        "cached_at": e.cached_at,
    }


class PostgresEnrichedWordsRepo:
    """Shared word metadata cache."""

    def get(self, word: str) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.execute(
                select(EnrichedWord).where(EnrichedWord.word == word),
            ).scalar_one_or_none()
        return _enriched_to_dict(row) if row else None

    def save(self, word: str, data: dict) -> None:
        """UPSERT — re-saving overwrites all known fields."""
        now = datetime.now(timezone.utc)
        values = {k: v for k, v in data.items() if k in _ENRICHED_STRUCTURED}
        values["cached_at"] = now
        stmt = pg_insert(EnrichedWord).values(
            word=word, **values,
        ).on_conflict_do_update(
            index_elements=["word"],
            set_=values,
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def update_example(self, word: str, band_tier: str, example: dict) -> None:
        """Merge ``examples_by_band[band_tier] = example`` (race-safe)."""
        with get_sync_session() as s, s.begin():
            row = s.execute(
                select(EnrichedWord)
                .where(EnrichedWord.word == word)
                .with_for_update(),
            ).scalar_one_or_none()
            if row is None:
                # The original Firestore call assumed the doc existed
                # — preserve that semantic (no-op on missing).
                return
            merged = dict(row.examples_by_band or {})
            merged[band_tier] = example
            row.examples_by_band = merged


# ─── Feature flags ─────────────────────────────────────────────────────


def _flag_to_dict(f: FeatureFlag) -> dict[str, Any]:
    """Shape matches the dict the legacy ``feature_flag_service`` consumes."""
    return {
        "enabled": f.enabled,
        "kill_switch": f.kill_switch,
        "rollout_pct": f.rollout_pct,
        "uid_allowlist": list(f.uid_allowlist or []),
        "description": f.description or "",
        "updated_at": f.updated_at,
    }


class PostgresFeatureFlagsRepo:
    """Admin-config rollout flag store."""

    def get(self, name: str) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.execute(
                select(FeatureFlag).where(FeatureFlag.name == name),
            ).scalar_one_or_none()
        return _flag_to_dict(row) if row else None

    def list_all(self) -> list[dict]:
        with get_sync_session() as s:
            rows = s.execute(select(FeatureFlag).order_by(FeatureFlag.name)).scalars().all()
        return [{"name": r.name, **_flag_to_dict(r)} for r in rows]

    def upsert(
        self,
        name: str,
        *,
        enabled: bool = False,
        rollout_pct: int = 0,
        uid_allowlist: Optional[list[str]] = None,
        description: str = "",
    ) -> dict:
        pct = max(0, min(100, int(rollout_pct)))
        allow = [str(u) for u in (uid_allowlist or [])]
        now = datetime.now(timezone.utc)
        stmt = pg_insert(FeatureFlag).values(
            name=name,
            enabled=bool(enabled),
            rollout_pct=pct,
            uid_allowlist=allow,
            description=description or "",
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=["name"],
            set_={
                "enabled": bool(enabled),
                "rollout_pct": pct,
                "uid_allowlist": allow,
                "description": description or "",
                "updated_at": now,
            },
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)
        return {
            "name": name,
            "enabled": bool(enabled),
            "kill_switch": False,
            "rollout_pct": pct,
            "uid_allowlist": allow,
            "description": description or "",
            "updated_at": now,
        }

    def delete(self, name: str) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(delete(FeatureFlag).where(FeatureFlag.name == name))


# ─── Auth link codes ───────────────────────────────────────────────────


class PostgresAuthLinkCodesRepo:
    """Ephemeral DM↔web link codes. Cleaned nightly by cleanup_expired."""

    def create(self, code: str, telegram_id: int, expires_at: datetime) -> None:
        now = datetime.now(timezone.utc)
        stmt = pg_insert(AuthLinkCode).values(
            code=code,
            telegram_id=int(telegram_id),
            expires_at=expires_at,
            created_at=now,
        ).on_conflict_do_update(
            index_elements=["code"],
            set_={
                "telegram_id": int(telegram_id),
                "expires_at": expires_at,
                "created_at": now,
            },
        )
        with get_sync_session() as s, s.begin():
            s.execute(stmt)

    def get(self, code: str) -> Optional[dict]:
        with get_sync_session() as s:
            row = s.execute(
                select(AuthLinkCode).where(AuthLinkCode.code == code),
            ).scalar_one_or_none()
        if not row:
            return None
        return {
            "telegram_id": row.telegram_id,
            "created_at": row.created_at,
            "expires_at": row.expires_at,
        }

    def delete(self, code: str) -> None:
        with get_sync_session() as s, s.begin():
            s.execute(delete(AuthLinkCode).where(AuthLinkCode.code == code))


__all__ = [
    "PostgresAuthLinkCodesRepo",
    "PostgresEnrichedWordsRepo",
    "PostgresFeatureFlagsRepo",
    "PostgresReadingQuestionsRepo",
]
