#!/usr/bin/env python3
"""Explore public vocabulary datasets before adding a production word bank.

The script is intentionally read-only. It fetches candidate public sources,
normalizes their headwords, compares them with the local seed vocabulary, and
prints a compact report that can guide a later vocabulary_master import.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SEED_VOCAB_PATH = ROOT / "seeds" / "vocabulary.json"

CEFR_J_URL = (
    "https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/master/"
    "cefrj-vocabulary-profile-1.5.csv"
)
WORDLEVEL_URL = "https://wordlevel.net/en/datasets/"
WORDLEVEL_FULL_CSV_URL = (
    "https://raw.githubusercontent.com/gungorkaya-eng/toefl-essential-vocabulary-dataset/"
    "main/toefl_essential_vocabulary.csv"
)
WORDS_CEFR_BASE = "https://raw.githubusercontent.com/Maximax67/Words-CEFR-Dataset/main/csv"

USER_AGENT = "ielts-bot-vocab-source-explorer/1.0"
FETCH_ERRORS = (OSError, URLError, subprocess.SubprocessError)

POS_TAGS = {
    "JJ": "adjective",
    "JJR": "adjective",
    "JJS": "adjective",
    "NN": "noun",
    "NNS": "noun",
    "RB": "adverb",
    "RBR": "adverb",
    "RBS": "adverb",
    "VB": "verb",
    "VBD": "verb",
    "VBG": "verb",
    "VBN": "verb",
    "VBP": "verb",
    "VBZ": "verb",
}


@dataclass
class DatasetReport:
    name: str
    source_url: str
    license_summary: str
    columns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rows_seen: int = 0
    unique_words: set[str] = field(default_factory=set)
    sample_rows: list[dict[str, str]] = field(default_factory=list)

    def add_row(self, row: dict[str, str], word_value: str, sample_size: int) -> None:
        self.rows_seen += 1
        self.unique_words.update(normalize_word(part) for part in word_variants(word_value))
        self.unique_words.discard("")
        if len(self.sample_rows) < sample_size:
            self.sample_rows.append(row)


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
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"^[^a-z]+|[^a-z]+$", "", normalized)
    return normalized


def word_variants(value: str | None) -> Iterable[str]:
    if not value:
        return []
    if "/" not in value:
        return [value]
    return [part.strip() for part in value.split("/") if part.strip()]


def load_seed_words() -> set[str]:
    with SEED_VOCAB_PATH.open() as f:
        data = json.load(f)

    seed_words: set[str] = set()
    for words in data.values():
        for word_doc in words:
            seed_words.add(normalize_word(word_doc.get("word")))
    seed_words.discard("")
    return seed_words


def parse_csv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def sample_values(values: Iterable[str], limit: int) -> list[str]:
    return sorted(value for value in values if value)[:limit]


def explore_cefr_j(sample_size: int, timeout: int) -> DatasetReport:
    report = DatasetReport(
        name="CEFR-J Vocabulary Profile",
        source_url=CEFR_J_URL,
        license_summary="Free for research/commercial use with citation; copyright Tono Lab/TUFS.",
        notes=[
            "Good CEFR coverage and topic hints, but only up to B2 in this file.",
            "Some rows contain slash-separated spelling variants.",
        ],
    )
    try:
        rows = parse_csv(fetch_text(CEFR_J_URL, timeout))
    except FETCH_ERRORS as exc:
        report.errors.append(f"Could not fetch CEFR-J CSV: {exc}")
        return report

    report.columns = list(rows[0].keys()) if rows else []
    for row in rows:
        report.add_row(
            {
                "word": row.get("headword", ""),
                "pos": row.get("pos", ""),
                "level": row.get("CEFR", ""),
                "topic": first_present(
                    row.get("CoreInventory 1"),
                    row.get("CoreInventory 2"),
                    row.get("Threshold"),
                ),
            },
            row.get("headword", ""),
            sample_size,
        )
    return report


def explore_wordlevel(sample_size: int, timeout: int) -> DatasetReport:
    report = DatasetReport(
        name="WordLevel TOEFL/IELTS Academic Vocabulary",
        source_url=WORDLEVEL_FULL_CSV_URL,
        license_summary="MIT according to the public dataset page metadata.",
        notes=[
            "Best direct IELTS/TOEFL fit found so far.",
            "Full public GitHub CSV has word, POS, difficulty, academic theme, synonyms, definition, and example sentence.",
            "README asks for attribution/backlink even though the LICENSE file is MIT.",
        ],
    )
    rows = fetch_wordlevel_full_csv(report, sample_size, timeout)
    if rows:
        return report

    try:
        page = fetch_text(WORDLEVEL_URL, timeout)
    except FETCH_ERRORS as exc:
        report.errors.append(f"Could not fetch WordLevel page: {exc}")
        return report

    dataset_metadata = extract_json_ld(page)
    if dataset_metadata:
        report.notes.append(f"Dataset name: {dataset_metadata.get('name', 'unknown')}")
        distribution = dataset_metadata.get("distribution") or []
        content_urls = [item.get("contentUrl") for item in distribution if item.get("contentUrl")]
        if content_urls:
            report.notes.append(f"Full dataset link: {', '.join(content_urls)}")

    rows = extract_wordlevel_preview_rows(page)
    report.columns = ["word", "pos", "theme", "definition"]
    for row in rows:
        report.add_row(row, row["word"], sample_size)
    if not rows:
        report.errors.append("Could not parse the public preview table.")
    return report


def fetch_wordlevel_full_csv(
    report: DatasetReport,
    sample_size: int,
    timeout: int,
) -> list[dict[str, str]]:
    try:
        rows = parse_csv(fetch_text(WORDLEVEL_FULL_CSV_URL, timeout))
    except FETCH_ERRORS as exc:
        report.notes.append(f"Full CSV unavailable, falling back to public preview: {exc}")
        return []

    report.columns = list(rows[0].keys()) if rows else []
    for row in rows:
        report.add_row(
            {
                "word": row.get("word", ""),
                "pos": row.get("pos", ""),
                "difficulty": row.get("difficulty", ""),
                "theme": row.get("theme", ""),
                "synonyms": row.get("synonyms", ""),
                "definition_en": row.get("definition_en", ""),
                "example_sentence": row.get("example_sentence", ""),
            },
            row.get("word", ""),
            sample_size,
        )
    return rows


def extract_json_ld(page: str) -> dict[str, object]:
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        page,
        flags=re.DOTALL,
    )
    if not match:
        return {}
    try:
        return json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return {}


def extract_wordlevel_preview_rows(page: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r"<tr[^>]*>\s*"
        r"<td[^>]*>\d+</td>\s*"
        r"<td[^>]*>(?P<word>.*?)</td>\s*"
        r"<td[^>]*>.*?<span[^>]*>(?P<pos>.*?)</span>.*?</td>\s*"
        r"<td[^>]*>.*?</span>(?P<theme>.*?)</span></td>\s*"
        r"<td[^>]*>(?P<definition>.*?)</td>\s*"
        r"</tr>",
        flags=re.DOTALL,
    )
    rows: list[dict[str, str]] = []
    for match in pattern.finditer(page):
        rows.append(
            {
                "word": clean_html_text(match.group("word")),
                "pos": clean_html_text(match.group("pos")),
                "theme": clean_html_text(match.group("theme")),
                "definition": clean_html_text(match.group("definition")),
            }
        )
    return rows


def clean_html_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def explore_words_cefr(sample_size: int, timeout: int) -> DatasetReport:
    report = DatasetReport(
        name="Words-CEFR-Dataset",
        source_url="https://github.com/Maximax67/Words-CEFR-Dataset",
        license_summary="MIT.",
        notes=[
            "Large CEFR/frequency signal, useful for filtering and difficulty calibration.",
            "Not IELTS-specific; proper nouns and noisy long-tail words need filtering.",
        ],
    )
    try:
        words = parse_csv(fetch_text(f"{WORDS_CEFR_BASE}/words.csv", timeout))
        word_pos = parse_csv(fetch_text(f"{WORDS_CEFR_BASE}/word_pos.csv", timeout))
        pos_tags = parse_csv(fetch_text(f"{WORDS_CEFR_BASE}/pos_tags.csv", timeout))
    except FETCH_ERRORS as exc:
        report.errors.append(f"Could not fetch Words-CEFR CSV files: {exc}")
        return report

    word_by_id = {row["word_id"]: row["word"] for row in words}
    tag_by_id = {row["tag_id"]: row["tag"] for row in pos_tags}
    report.columns = ["word", "pos", "cefr", "frequency_count"]

    for row in word_pos:
        word = word_by_id.get(row.get("word_id", ""), "")
        tag = tag_by_id.get(row.get("pos_tag_id", ""), "")
        if not word:
            continue
        mapped_pos = POS_TAGS.get(tag, tag)
        level = cefr_label(row.get("level", ""))
        report.add_row(
            {
                "word": word,
                "pos": mapped_pos,
                "cefr": level,
                "frequency_count": row.get("frequency_count", ""),
            },
            word,
            sample_size,
        )
    return report


def cefr_label(value: str) -> str:
    try:
        numeric = float(value)
    except ValueError:
        return value
    if numeric <= 1:
        return "A1"
    if numeric <= 2:
        return "A2"
    if numeric <= 3:
        return "B1"
    if numeric <= 4:
        return "B2"
    if numeric <= 5:
        return "C1"
    return "C2"


def first_present(*values: str | None) -> str:
    return next((value for value in values if value), "")


def render_report(reports: list[DatasetReport], seed_words: set[str], sample_size: int) -> str:
    lines = [
        "# Vocabulary Source Exploration",
        "",
        f"Local seed unique words: {len(seed_words)}",
        "",
    ]
    for report in reports:
        overlap = report.unique_words & seed_words
        seed_only = seed_words - report.unique_words
        lines.extend(
            [
                f"## {report.name}",
                "",
                f"- Source: {report.source_url}",
                f"- License/terms: {report.license_summary}",
                f"- Rows seen: {report.rows_seen}",
                f"- Unique normalized words: {len(report.unique_words)}",
                f"- Seed overlap: {len(overlap)}",
                f"- Columns: {', '.join(report.columns) if report.columns else 'unknown'}",
            ]
        )
        for note in report.notes:
            lines.append(f"- Note: {note}")
        for error in report.errors:
            lines.append(f"- Error: {error}")

        lines.append(f"- Overlap examples: {', '.join(sample_values(overlap, sample_size)) or 'none'}")
        lines.append(
            f"- Seed-only examples: {', '.join(sample_values(seed_only, sample_size)) or 'none'}"
        )
        lines.append("")
        lines.append("Sample rows:")
        if report.sample_rows:
            for row in report.sample_rows[:sample_size]:
                lines.append(f"- {json.dumps(row, ensure_ascii=False)}")
        else:
            lines.append("- none")
        lines.append("")

    lines.extend(
        [
            "## Import Recommendation",
            "",
            "- Use WordLevel as a small IELTS/TOEFL candidate set if its full downloadable files pass license and quality checks.",
            "- Use CEFR-J as the initial CEFR/difficulty signal because its licensing terms are explicit and its shape is simple.",
            "- Use Words-CEFR as a secondary difficulty/frequency filter, not as direct lesson content.",
            "- Keep AI for missing definitions, examples, Vietnamese translations, collocations, and topic tagging.",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=["all", "cefr-j", "wordlevel", "words-cefr"],
        default="all",
        help="Dataset source to explore.",
    )
    parser.add_argument("--sample-size", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seed_words = load_seed_words()

    explorers = {
        "cefr-j": explore_cefr_j,
        "wordlevel": explore_wordlevel,
        "words-cefr": explore_words_cefr,
    }
    selected = explorers.keys() if args.source == "all" else [args.source]
    reports = [explorers[source](args.sample_size, args.timeout) for source in selected]

    print(render_report(reports, seed_words, args.sample_size))
    return 1 if any(report.errors for report in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
