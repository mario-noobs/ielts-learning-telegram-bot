#!/usr/bin/env python3
"""Regenerate docs/api/errors.md from api/errors.py's ERR registry.

Run: python scripts/gen_error_docs.py

The output is checked in so reviewers can see the code → HTTP status →
summary table without running anything. CI can also call this with
--check to fail if the committed file is out of date.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.errors import all_codes  # noqa: E402  (after sys.path tweak)
TARGET = ROOT / "docs" / "api" / "errors.md"

HEADER = """# API error codes

> **Generated from `api/errors.py` — do not hand-edit.**
> Regenerate: `python scripts/gen_error_docs.py`.

Every API error follows a single response shape (US-M7.3):

```json
{
  "error": {
    "code": "reading.passage.not_found",
    "params": { "passage_id": "p001" },
    "http_status": 404
  }
}
```

The frontend keeps a per-locale `web/public/locales/{lng}/errors.json`
mapping the dotted code to an ICU-formatted message. Unknown codes fall
back to `common.unknown_error`.

## Codes

| Code | HTTP | Summary |
|------|------|---------|
"""


def render() -> str:
    rows = [
        f"| `{c.code}` | {c.http_status} | {c.summary} |"
        for c in all_codes()
    ]
    return HEADER + "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="fail non-zero if target is out of date")
    args = parser.parse_args()

    new = render()
    if args.check:
        existing = TARGET.read_text() if TARGET.exists() else ""
        if existing.strip() != new.strip():
            print(f"error: {TARGET.relative_to(ROOT)} is out of date. "
                  "Run: python scripts/gen_error_docs.py")
            return 1
        print(f"OK: {TARGET.relative_to(ROOT)} up to date")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(new)
    print(f"wrote {TARGET.relative_to(ROOT)} ({len(new.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
