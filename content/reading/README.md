# Reading Corpus

Curated Cambridge-style passages for the Reading Lab (M9).

## Layout

```
content/reading/
├── README.md      (this file — schema + workflow)
├── LICENSE.md     (licensing policy + attribution rules)
└── passages/
    ├── p001.md
    ├── p002.md
    └── ...
```

Each passage is a single markdown file: YAML frontmatter + body text. Filenames use zero-padded sequential ids (`p001.md` … `pNNN.md`).

## Frontmatter schema

```yaml
---
id: p001                      # unique, matches filename
title: "Passage title"
topic: education              # single lowercase slug
band: 7.0                     # one of 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5
word_count: 812               # integer, must be 700..900 inclusive
source: ieltscoach.vn         # short origin identifier
license: owned                # owned | cc-by | public-domain
attribution: "Original content by IELTS Coach, AI-assisted."
ai_assisted: true             # true if LLM was used in drafting
review:
  factual_check: pending      # pending | passed | failed
  bias_check: pending
  sensitive_topics: pending
reviewed_by: null             # GitHub handle once reviewed
reviewed_at: null             # ISO-8601 date
---
```

Body is plain markdown. No HTML. Paragraph breaks are blank lines.

## Band distribution (initial seed)

This first PR ships **10 passages** to exercise the schema, validator, licensing policy, and PR workflow end-to-end. A follow-up issue tracks growing the corpus to the full 30 called for by US-M9.1 AC1 / AC3.

| Band | Count | IDs                 |
|------|-------|---------------------|
| 5.5  | 2     | p001, p002          |
| 6.0  | 1     | p003                |
| 6.5  | 1     | p004                |
| 7.0  | 2     | p005, p006          |
| 7.5  | 2     | p007, p008          |
| 8.0  | 1     | p009                |
| 8.5  | 1     | p010                |
| **Total** | **10** |                 |

Minimum per band in the **final corpus** will be 3 (AC3). The validator currently enforces ≥1 per present band; it will be tightened to ≥3 when the corpus reaches 30.

Band assignments in this seed are provisional and calibrated by reader intuition (topic complexity, vocabulary density, syntactic nesting). Systematic re-calibration against a formal vocabulary profile (e.g. Oxford 5000 / CEFR lists) is a separate follow-up.

## Validation

```
python scripts/validate_reading.py
```

Exits non-zero on any schema violation. CI runs this on every PR that touches `content/reading/**`.

## Adding a passage

1. Copy `passages/_template.md` to the next available id.
2. Fill frontmatter; draft body to 700–900 words.
3. Run the validator.
4. Open a PR using the `reading_passage.md` template — the review checklist is required before merge.

See `LICENSE.md` before adding externally-sourced material.
