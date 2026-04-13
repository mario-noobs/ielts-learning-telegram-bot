---
name: Feature Coverage Map
description: What the bot has and what is missing as of April 2026 — ground truth for roadmap planning
type: project
---

**Why:** Roadmap proposals must build on, not duplicate, existing features. This is the baseline.

## Exists today (confirmed by code audit, 2026-04-13)

### Group features
- /daily — scheduled + on-demand vocab post (10 words, AI-generated, group band)
- /newdaily — force-regenerate daily vocab
- /audio <n> — gTTS pronunciation for daily word
- /challenge — daily 5-question MC+fill challenge (AI-generated from group vocab)
- /results — challenge score summary
- /leaderboard — ranked by total_words + accuracy
- /groupsettings — band, topics, daily time config

### DM features
- /start — onboarding (band + topics), ConversationHandler
- /mydaily — personal daily vocab (user's band + topics)
- /quiz — 5-question batch session (MC + fill-blank, AI-generated from user vocab)
- /review — SRS review of due words (SM-2 algorithm, up to 10 words per session)
- /word <word> — AI word explanation
- /write <text> — IELTS writing feedback (band-aware)
- /translate <text> — EN<->VI translation (auto-detect, 2 Gemini calls)
- /mywords — paginated vocab browser with SRS strength indicators
- /progress — stats dashboard (vocab, quiz accuracy, streak, challenge wins)
- /settings — personal band/topics/time config

### Scheduler
- Daily vocab post per group (cron)
- Daily challenge post per group (cron, 30 min after vocab)
- Daily greeting DM to all users at 07:00 VN time

## Product scope (confirmed 2026-04-13)

**In scope:** Vocabulary depth, Pronunciation training
**Out of scope (not roadmap focus):** Writing/essay feedback, Reading comprehension, Speaking cue cards
Note: /write and /translate commands exist in code but are NOT roadmap investment areas going forward.

## Vocabulary gaps (in scope)
- No collocations or word family data (e.g., "economy" -> "economic", "economize")
- No etymology hooks to aid memorability
- No IELTS topic cluster browsing (Environment, Technology, Health, etc.)
- No word-in-context sentences beyond a single AI example
- SRS only tracks recall — does not distinguish recognition vs. production
- No "mastered word" milestone or graduation event
- Leaderboard only sorts by total_words — no accuracy or streak dimension
- Daily greeting is generic — does not personalize by vocab due count or weak topics

## Pronunciation gaps (in scope)
- /audio gives gTTS playback only — no phonemic breakdown, no IPA
- No syllable stress display
- No minimal pairs exercises
- No awareness of Vietnamese-speaker phoneme pitfalls (e.g., final consonants, short/long vowels)
- No shadowing or repeat-after-me flow
- No pronunciation challenge in groups

## Out of scope (do not plan)
- Reading comprehension passages or T/F/NG questions
- Writing Task 1 or Task 2 essay feedback or revision
- Speaking cue card generation
- Any feature requiring speech-to-text input from users
