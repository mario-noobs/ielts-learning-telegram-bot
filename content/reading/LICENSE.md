# Reading Corpus — Licensing Policy

Every passage in `content/reading/passages/` must declare a `license` field that is one of:

| Value         | Meaning                                                                          |
|---------------|----------------------------------------------------------------------------------|
| `owned`       | Original content authored (or AI-drafted) for IELTS Coach; we hold the copyright |
| `cc-by`       | Creative Commons Attribution; requires `attribution` line surfaced in UI         |
| `public-domain` | No copyright or expired; attribution still recommended for honesty             |

**We do not accept** content that is "fair use", "educational use", scraped from copyrighted exam prep material, or reproduced from Cambridge / IDP / British Council publications. When in doubt, don't merge.

## Attribution requirements

- `cc-by`: `attribution` field must name the original author + a link to the source. The UI surfaces this line below the passage.
- `public-domain`: `attribution` is optional but encouraged (e.g., "Adapted from Project Gutenberg, *Origin of Species* (1859)").
- `owned`: `attribution` should read `"Original content by IELTS Coach"` plus `" (AI-assisted)"` if an LLM was involved. The `ai_assisted: true` flag is independent and must be accurate.

## AI-assisted content

Passages drafted with LLM assistance are permissible as `owned` provided:

1. A human has reviewed factual accuracy, bias, and sensitive-topic handling (tracked in the `review` block).
2. The `ai_assisted: true` flag is set — this drives a disclosure in the UI footer ("some passages were drafted with AI assistance").
3. The review checklist in the PR template is signed off by the PO before merge.

## External sources we trust

| Source                | License type     | Notes                                                  |
|-----------------------|------------------|--------------------------------------------------------|
| Project Gutenberg     | public-domain    | Pre-1928 or explicitly PD works; verify each title     |
| Wikipedia             | cc-by-sa         | **Not accepted** — share-alike conflicts with our ToS  |
| VOA Learning English  | public-domain    | U.S. government work; explicitly free to reuse         |
| NASA, NOAA            | public-domain    | U.S. government work                                   |
| Our World in Data     | cc-by            | Attribution required                                   |

## Removal policy

If a copyright holder contacts us claiming infringement, the passage is pulled from the corpus within 24 hours and the review is logged in `CHANGELOG.md`. PRs that add content we later determine to be non-compliant are reverted.
