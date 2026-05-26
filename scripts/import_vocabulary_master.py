#!/usr/bin/env python3
"""Import public vocabulary candidates into vocabulary_master.

Default mode is a dry run. Pass ``--apply`` to write to Postgres.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.dialects.postgresql import Insert  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from services.db import get_sync_session  # noqa: E402
from services.db.models import Topic, VocabularyMaster  # noqa: E402

WORDLEVEL_FULL_CSV_URL = (
    "https://raw.githubusercontent.com/gungorkaya-eng/toefl-essential-vocabulary-dataset/"
    "main/toefl_essential_vocabulary.csv"
)
SOURCE = "wordlevel_toefl_ielts_1k"
SOURCE_URL = "https://github.com/gungorkaya-eng/toefl-essential-vocabulary-dataset"
LICENSE = "MIT; README requests attribution/backlink to https://wordlevel.net"
USER_AGENT = "ielts-bot-vocabulary-master-importer/1.0"

_PUNCT_RE = re.compile(r"[^\w\s-]", re.UNICODE)

THEME_TOPIC_SLUGS = {
    "archaeology": "arts",
    "art history": "arts",
    "business": "economy",
    "business administration": "economy",
    "economics": "economy",
    "education": "education",
    "education technology": "education",
    "environmental science": "environment",
    "agricultural science": "food",
    "law": "government",
    "law/political science": "government",
    "political science": "government",
    "biology": "science",
    "chemistry": "science",
    "engineering": "science",
    "geology": "science",
    "materials science": "science",
    "mathematics": "science",
    "oceanography": "science",
    "physics": "science",
    "research methodology": "science",
    "statistics": "science",
    "astronomy": "science",
    "communication studies": "media",
    "linguistics": "media",
    "criminology": "society",
    "general academic": "society",
    "history": "society",
    "literature": "society",
    "philosophy": "society",
    "psychology": "society",
    "sociology": "society",
    "urban planning": "society",
}

DEFAULT_TOPIC_IDS_BY_SLUG = {
    "arts": 1,
    "economy": 2,
    "education": 3,
    "environment": 4,
    "food": 5,
    "government": 6,
    "health": 7,
    "media": 8,
    "science": 9,
    "society": 10,
    "technology": 11,
    "travel": 12,
}


@dataclass(frozen=True)
class MasterWordCandidate:
    id: str
    word: str
    normalized_word: str
    part_of_speech: str
    difficulty: int | None
    topic_id: int | None
    source_theme: str
    definition_en: str
    example_en: str
    synonyms: list[str]
    metadata: dict[str, str]

    def to_insert_values(self) -> dict:
        return {
            "id": self.id,
            "word": self.word,
            "normalized_word": self.normalized_word,
            "part_of_speech": self.part_of_speech,
            "difficulty": self.difficulty,
            "topic_id": self.topic_id,
            "source_theme": self.source_theme,
            "definition_en": self.definition_en,
            "definition_vi": "",
            "ipa": "",
            "example_en": self.example_en,
            "example_vi": "",
            "synonyms": self.synonyms,
            "antonyms": [],
            "collocations": [],
            "word_family": [],
            "source": SOURCE,
            "source_ref": self.normalized_word,
            "source_url": SOURCE_URL,
            "license": LICENSE,
            "status": "candidate",
            "metadata": self.metadata,
        }


def fetch_text(url: str, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        return fetch_text_with_curl(url, timeout)


def fetch_text_with_curl(url: str, timeout: int) -> str:
    result = subprocess.run(
        ["curl", "-fsSL", "--max-time", str(timeout), "-A", USER_AGENT, url],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def normalize_word(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    normalized = normalized.replace("’", "'")
    normalized = _PUNCT_RE.sub("", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def split_csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_difficulty(value: str | None) -> int | None:
    if not value:
        return None
    try:
        difficulty = int(value)
    except ValueError:
        return None
    if 1 <= difficulty <= 5:
        return difficulty
    return None


def candidate_id(normalized_word: str) -> str:
    digest = hashlib.sha1(f"{SOURCE}:{normalized_word}".encode()).hexdigest()[:16]
    return f"vm_{digest}"


def topic_id_for_theme(theme: str, topic_ids_by_slug: dict[str, int]) -> int | None:
    slug = THEME_TOPIC_SLUGS.get(theme.strip().lower())
    if not slug:
        return None
    return topic_ids_by_slug.get(slug)


def parse_wordlevel_rows(
    csv_text: str,
    topic_ids_by_slug: dict[str, int] | None = None,
) -> list[MasterWordCandidate]:
    topic_ids_by_slug = topic_ids_by_slug or {}
    candidates: list[MasterWordCandidate] = []
    seen: set[str] = set()
    for row in csv.DictReader(io.StringIO(csv_text)):
        word = (row.get("word") or "").strip()
        normalized = normalize_word(word)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        theme = (row.get("theme") or "").strip()
        candidates.append(
            MasterWordCandidate(
                id=candidate_id(normalized),
                word=word,
                normalized_word=normalized,
                part_of_speech=(row.get("pos") or "").strip(),
                difficulty=parse_difficulty(row.get("difficulty")),
                topic_id=topic_id_for_theme(theme, topic_ids_by_slug),
                source_theme=theme,
                definition_en=(row.get("definition_en") or "").strip(),
                example_en=(row.get("example_sentence") or "").strip(),
                synonyms=split_csv_list(row.get("synonyms")),
                metadata={"source_dataset": "toefl_essential_vocabulary.csv"},
            )
        )
    return candidates


def load_topic_ids_by_slug() -> dict[str, int]:
    with get_sync_session() as session:
        return dict(session.execute(select(Topic.slug, Topic.id)).all())


def upsert_candidates(candidates: Iterable[MasterWordCandidate]) -> int:
    values = [candidate.to_insert_values() for candidate in candidates]
    if not values:
        return 0

    stmt = build_upsert_statement(values)
    with get_sync_session() as session, session.begin():
        result = session.execute(stmt)
    return result.rowcount or 0


def build_upsert_statement(values: list[dict]) -> Insert:
    table = VocabularyMaster.__table__
    insert_stmt = pg_insert(table).values(values)
    excluded = insert_stmt.excluded
    update_columns = {
        "word": excluded.word,
        "part_of_speech": excluded.part_of_speech,
        "difficulty": excluded.difficulty,
        "topic_id": excluded.topic_id,
        "source_theme": excluded.source_theme,
        "definition_en": excluded.definition_en,
        "example_en": excluded.example_en,
        "synonyms": excluded.synonyms,
        "source": excluded.source,
        "source_ref": excluded.source_ref,
        "source_url": excluded.source_url,
        "license": excluded.license,
        "metadata": excluded["metadata"],
        "updated_at": func.now(),
    }
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["normalized_word"],
        set_=update_columns,
    )
    return stmt


def summarize(candidates: list[MasterWordCandidate]) -> str:
    mapped_topics = sum(1 for candidate in candidates if candidate.topic_id is not None)
    themes = sorted({candidate.source_theme for candidate in candidates if candidate.source_theme})
    samples = ", ".join(candidate.word for candidate in candidates[:5])
    return (
        f"candidates={len(candidates)} mapped_topics={mapped_topics} "
        f"themes={len(themes)} samples=[{samples}]"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write rows to Postgres.")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--source-url", default=WORDLEVEL_FULL_CSV_URL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    topic_ids_by_slug = load_topic_ids_by_slug() if args.apply else DEFAULT_TOPIC_IDS_BY_SLUG
    csv_text = fetch_text(args.source_url, args.timeout)
    candidates = parse_wordlevel_rows(csv_text, topic_ids_by_slug)
    print(summarize(candidates))

    if not args.apply:
        print("dry-run only; pass --apply to write vocabulary_master")
        return 0

    affected = upsert_candidates(candidates)
    print(f"upserted={affected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
