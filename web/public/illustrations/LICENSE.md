# Illustrations

All SVG illustrations in this directory are **original work** created for the
IELTS Coach web app as part of US-M6.6 (issue #125). They are released under
the same license as the rest of this repository.

## Design rules (M6.6)

- 128×128 viewBox, single- or two-color flat design
- `fill="currentColor"` / `stroke="currentColor"` so the parent's `text-*`
  utility controls the colour in both light and dark mode
- No gradients, no raster embeds, no external fonts
- Each file optimised with SVGO; target < 8 KB per file and < 50 KB total

## Files

| File | Usage |
|------|-------|
| `empty-vocab.svg` | M1 VocabHomePage — no vocabulary yet |
| `empty-plan.svg` | M4 DashboardPage — daily plan generating or empty |
| `plan-complete.svg` | M4 DashboardPage — all tasks done (celebration) |
| `empty-writing.svg` | M2 WritingHistoryPage — no submissions yet |
| `empty-listening.svg` | M3 ListeningHomePage / History — no sessions today |
| `empty-progress.svg` | M5 ProgressPage — generic empty progress |
| `error-network.svg` | Generic offline / network failure |
| `error-audio.svg` | M3 audio failed to load |
| `rate-limited.svg` | M2 writing score — Gemini 429 |
| `not-enough-data.svg` | M5 band map — < 7 days of data |

These are **placeholder quality** per the ticket. A designer is expected to
polish them in a later milestone (tracked on the UX-1 follow-up list).

## Replacing an illustration

When swapping a file, keep:

1. The same filename (integration call sites reference them by basename)
2. The same 128×128 viewBox
3. The `currentColor` contract — otherwise dark mode will break
