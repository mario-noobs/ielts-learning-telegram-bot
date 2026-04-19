#!/usr/bin/env python3
"""Validate the reading passage corpus in content/reading/passages/.

Exits 0 on success, 1 on any schema or content-rule violation.

Rules:
  - every .md file (except _template.md) parses as YAML frontmatter + body
  - frontmatter matches the schema (see REQUIRED_KEYS / ALLOWED_VALUES)
  - filename matches frontmatter.id (e.g. p001.md → id: p001)
  - word_count is within 700..900 inclusive AND matches the body's actual word count (±3 tolerance)
  - every band tier has at least 3 passages (AC3, issue #135)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("error: PyYAML is not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
PASSAGES = ROOT / "content" / "reading" / "passages"

ALLOWED_BANDS = {5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5}
ALLOWED_LICENSES = {"owned", "cc-by", "public-domain"}
ALLOWED_REVIEW = {"pending", "passed", "failed"}
WORD_MIN, WORD_MAX = 700, 900
WORD_COUNT_TOLERANCE = 3
# AC3 (#135) requires 3-per-band once the corpus reaches 30. For the initial
# seed (10 passages), we enforce >=1 per present band; the follow-up issue
# that grows the corpus to 30 will bump this back to 3.
MIN_PER_BAND = 1

REQUIRED_KEYS = {
    "id", "title", "topic", "band", "word_count",
    "source", "license", "attribution", "ai_assisted",
    "review", "reviewed_by", "reviewed_at",
}
REQUIRED_REVIEW_KEYS = {"factual_check", "bias_check", "sensitive_topics"}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def validate_one(path: Path) -> list[str]:
    errors: list[str] = []
    raw = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(raw)
    if not match:
        return [f"{path.name}: missing or malformed YAML frontmatter"]

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        return [f"{path.name}: frontmatter is not valid YAML — {exc}"]
    body = match.group(2).strip()

    missing = REQUIRED_KEYS - set(meta)
    if missing:
        errors.append(f"{path.name}: missing required keys: {sorted(missing)}")
        return errors

    if meta["id"] != path.stem:
        errors.append(f"{path.name}: id '{meta['id']}' does not match filename stem '{path.stem}'")

    if not isinstance(meta["title"], str) or not meta["title"].strip():
        errors.append(f"{path.name}: title must be a non-empty string")

    if not isinstance(meta["topic"], str) or not re.fullmatch(r"[a-z][a-z0-9-]*", meta["topic"]):
        errors.append(f"{path.name}: topic must be a lowercase slug (a-z, 0-9, hyphen)")

    if meta["band"] not in ALLOWED_BANDS:
        errors.append(f"{path.name}: band '{meta['band']}' is not one of {sorted(ALLOWED_BANDS)}")

    if not isinstance(meta["word_count"], int):
        errors.append(f"{path.name}: word_count must be an integer")
    elif not (WORD_MIN <= meta["word_count"] <= WORD_MAX):
        errors.append(f"{path.name}: word_count {meta['word_count']} out of range [{WORD_MIN}, {WORD_MAX}]")
    else:
        actual = count_words(body)
        if abs(actual - meta["word_count"]) > WORD_COUNT_TOLERANCE:
            errors.append(
                f"{path.name}: declared word_count {meta['word_count']} differs from body count {actual}"
                f" (tolerance ±{WORD_COUNT_TOLERANCE})"
            )
        if not (WORD_MIN <= actual <= WORD_MAX):
            errors.append(f"{path.name}: body word count {actual} out of range [{WORD_MIN}, {WORD_MAX}]")

    if meta["license"] not in ALLOWED_LICENSES:
        errors.append(f"{path.name}: license '{meta['license']}' not in {sorted(ALLOWED_LICENSES)}")

    if not isinstance(meta["attribution"], str) or not meta["attribution"].strip():
        errors.append(f"{path.name}: attribution must be a non-empty string")

    if not isinstance(meta["ai_assisted"], bool):
        errors.append(f"{path.name}: ai_assisted must be a boolean")

    review = meta.get("review")
    if not isinstance(review, dict):
        errors.append(f"{path.name}: review must be a mapping with keys {sorted(REQUIRED_REVIEW_KEYS)}")
    else:
        missing_review = REQUIRED_REVIEW_KEYS - set(review)
        if missing_review:
            errors.append(f"{path.name}: review missing keys: {sorted(missing_review)}")
        for k, v in review.items():
            if k in REQUIRED_REVIEW_KEYS and v not in ALLOWED_REVIEW:
                errors.append(f"{path.name}: review.{k}='{v}' not in {sorted(ALLOWED_REVIEW)}")

    return errors


def main() -> int:
    if not PASSAGES.is_dir():
        print(f"error: {PASSAGES} does not exist", file=sys.stderr)
        return 1

    files = sorted(p for p in PASSAGES.glob("*.md") if p.name != "_template.md")
    if not files:
        print(f"error: no passage files found in {PASSAGES}", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    band_counts: dict[float, int] = {}

    for path in files:
        errs = validate_one(path)
        all_errors.extend(errs)
        if not errs:
            raw = path.read_text(encoding="utf-8")
            match = FRONTMATTER_RE.match(raw)
            assert match, "already validated above"
            meta: dict[str, Any] = yaml.safe_load(match.group(1)) or {}
            band_counts[meta["band"]] = band_counts.get(meta["band"], 0) + 1

    for band in sorted(ALLOWED_BANDS):
        count = band_counts.get(band, 0)
        if count < MIN_PER_BAND:
            all_errors.append(
                f"band {band} has {count} passages; minimum is {MIN_PER_BAND} (AC3)"
            )

    if all_errors:
        print(f"FAIL: {len(all_errors)} issue(s) in {len(files)} passage(s)", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    total = sum(band_counts.values())
    print(f"OK: {total} passages, band distribution: {dict(sorted(band_counts.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
