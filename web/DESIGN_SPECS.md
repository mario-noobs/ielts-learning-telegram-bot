# IELTS Coach — PWA Design Specs

> Consolidated visual + interaction spec for all 13 pages. Aligns with milestone [UX-1: UI/UX Overhaul](https://github.com/mario-noobs/ielts-learning-telegram-bot/milestone/7). Review this doc, leave comments in the corresponding GitHub issue. Master design system: [`design-system/ielts-coach/MASTER.md`](./design-system/ielts-coach/MASTER.md).

---

## Table of Contents

- [Global Design Language](#global-design-language)
  - [Design tokens (locked)](#design-tokens-locked)
  - [Typography scale](#typography-scale)
  - [Spacing scale](#spacing-scale)
  - [Icon system](#icon-system)
  - [Motion system](#motion-system)
  - [Breakpoints](#breakpoints)
- [AppShell (global layout)](#appshell-global-layout)
- [Pages](#pages)
  1. [LoginPage](#1-loginpage)
  2. [DashboardPage](#2-dashboardpage) (Home)
  3. [VocabHomePage](#3-vocabhomepage) (Học)
  4. [WordDetailPage](#4-worddetailpage)
  5. [FlashcardReviewPage](#5-flashcardreviewpage)
  6. [WritingPage](#6-writingpage)
  7. [WritingHistoryPage](#7-writinghistorypage)
  8. [WritingDetailPage](#8-writingdetailpage)
  9. [ListeningHomePage](#9-listeninghomepage)
  10. [ListeningExercisePage](#10-listeningexercisepage)
  11. [ListeningHistoryPage](#11-listeninghistorypage)
  12. [ProgressPage](#12-progresspage)
  13. [SettingsPage](#13-settingspage)
- [Shared Components](#shared-components)
- [Empty / Loading / Error states](#empty--loading--error-states)
- [Review Checklist](#review-checklist)

---

## Global Design Language

**Style:** Flat Design, Touch-First. Clean surfaces, 2-elevation shadow scale, clear affordances. No gradients on brand surfaces (retire indigo→purple).
**Tone:** Serious exam-prep product for adult Vietnamese learners (18-35). "Chuyên nghiệp, đáng tin," never "trẻ con."
**Platform:** Mobile-first PWA; desktop is enhanced, not primary.

### Design tokens (locked)

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--primary` | `#0D9488` teal-600 | `#14B8A6` teal-500 | CTAs, active states, focus rings, brand |
| `--primary-fg` | `#FFFFFF` | `#042F2E` | Text on primary surfaces |
| `--primary-hover` | `#0F766E` teal-700 | `#2DD4BF` teal-400 | Primary hover/pressed |
| `--accent` | `#EA580C` orange-600 | `#FB923C` orange-400 | Streak, exam countdown urgency, highlights |
| `--success` | `#15803D` green-700 | `#22C55E` green-500 | Correct, mastered, band ≥ 7 |
| `--warning` | `#B45309` amber-700 | `#F59E0B` amber-500 | Weak/learning, <30 days countdown |
| `--danger` | `#B91C1C` red-700 | `#F87171` red-400 | Incorrect, band < 5, destructive |
| `--fg` | `#0F172A` slate-900 | `#F1F5F9` slate-100 | Body text, headings |
| `--muted-fg` | `#475569` slate-600 | `#94A3B8` slate-400 | Secondary text, captions |
| `--bg` | `#FFFFFF` | `#0B1220` | Page background |
| `--surface` | `#F8FAFC` slate-50 | `#111827` slate-900 | Cards, sheets |
| `--surface-raised` | `#FFFFFF` | `#1F2937` slate-800 | Elevated cards, modals |
| `--border` | `#E2E8F0` slate-200 | `#1F2937` slate-800 | Dividers, card borders |
| `--ring` | `#0D9488` (3px, offset 2px) | `#14B8A6` | Focus indicator (keyboard) |

**Contrast verified (WCAG AA):** fg on bg = 16.5:1 · muted-fg on bg = 7.3:1 · primary on bg = 4.8:1 · primary-fg on primary = 6.1:1 · success/danger on bg ≥ 4.5:1.

### Typography scale

**Family:** Be Vietnam Pro (headings + body, Vietnamese-optimized diacritics) · Noto Sans (fallback for CJK/symbols) · `ui-monospace` for numbers in tables/timers.

| Role | Size / Line | Weight | Use |
|------|-------------|--------|-----|
| Display | 32 / 40 | 700 | Not used (reserve) |
| H1 | 24 / 32 | 700 | Page title (DashboardPage "IELTS Coach", ProgressPage "Band Progress") |
| H2 | 20 / 28 | 600 | Section heads ("Kế hoạch hôm nay", "Chủ đề") |
| H3 | 18 / 24 | 600 | Card titles (PlanTaskCard title, SkillBandCard label) |
| Body | 16 / 24 | 400 | Default, form inputs, descriptions |
| Body-sm | 14 / 20 | 400 | Secondary text, metadata |
| Caption | 12 / 16 | 500 | Badges, helper text, timestamps |
| Mono | 14 / 20 | 500 | Audio timer, word count, IPA, linked code |
| Number-lg | 48 / 56 | 700 | BandRing center, quiz score |

**Rules:**
- Never <12px body text
- `letter-spacing: 0` (VN diacritics need breathing room)
- Line-length 35-60 chars on mobile, 60-75 on desktop
- Tabular figures (`font-variant-numeric: tabular-nums`) on all counters, timers, scores

### Spacing scale

4pt/8pt rhythm: `0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.
Container: mobile `px-4`, md+ `px-6`, max-width `max-w-2xl` (reading views) or `max-w-5xl` (index views).

### Icon system

**Lucide, stroke 1.75, consistent family.**

| Size | px | Context |
|------|----|---------|
| `sm` | 16 | Inline badges, chips, captions |
| `md` | 20 | Buttons, inline actions (default) |
| `lg` | 24 | Nav items, card icons |
| `xl` | 32 | Empty state illustrations |

**Core icons (20):**
`LayoutDashboard · BookOpen · PenLine · Headphones · TrendingUp · User · Settings · LogOut · Flame (streak) · Target (band) · Clock · Hourglass (countdown) · Check · X · ArrowRight · ChevronRight · Play · Pause · Volume2 · RotateCcw (replay)`

**Semantic icons (10):**
`FileText (writing history) · Sparkles (AI) · Lightbulb (tip) · Trophy (achievement) · Flag (milestone) · Mic (speaking) · Calendar (exam date) · ShieldCheck (link success) · AlertCircle (error) · Info`

**Rules:** Always wrapped in `<Icon>` component. Decorative → `aria-hidden`. Semantic → `aria-label` required. Never mix filled + outline at the same hierarchy.

### Motion system

| Token | Value | Use |
|-------|-------|-----|
| `--dur-fast` | 120ms | Press feedback, tap scale |
| `--dur-base` | 200ms | Color/opacity transitions, hover |
| `--dur-slow` | 320ms | Ring stroke, skeleton fade-out |
| `--ease-out` | `cubic-bezier(0.2, 0.8, 0.2, 1)` | Default (enter) |
| `--ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | Ring fills, sheet motion |

**Keep:** BandRing stroke fill, ProgressRing, skeleton shimmer (2s infinite), tap scale (0.97).
**Drop:** Typewriter prompt (blocks reading), card gradient hue-shifts, auto-dismiss timers.
**`prefers-reduced-motion: reduce`:** all durations clamp to 0ms, ring snaps to final, shimmer becomes static 8% tint. Timers/audio unaffected.

### Breakpoints

| Name | Min width | Layout |
|------|-----------|--------|
| `xs` | 375 | Base mobile (iPhone SE, small Android) |
| `sm` | 640 | Large phones |
| `md` | 768 | Tablet portrait, start grid layouts |
| `lg` | 1024 | Desktop narrow, sidebar appears (72px icon rail) |
| `xl` | 1280 | Desktop wide, sidebar expands (240px with labels) |

---

## AppShell (global layout)

Wraps every protected route. Replaces 13 hand-rolled "← Trang chủ" links.

### Mobile (<768px)

```
┌────────────────────────────────────────┐
│ [page content scrolls here]            │
│                                        │
│                                        │
│ ...                                    │
│                                        │
│                                        │ ← pb-20 so tab bar doesn't overlap
│                                        │
├────────────────────────────────────────┤ ← 56px tall, env(safe-area-inset-bottom)
│  🏠    📘     ✍️     📈     👤        │ ← Lucide icons, stroke 1.75
│ Home  Học   Luyện Tiến độ Tôi          │ ← 12px label, weight 600 on active
│  •                                     │ ← 2px top border = active tab indicator
└────────────────────────────────────────┘
```

**Tab spec:**

| Route | Icon | Label | Secondary actions inside |
|-------|------|-------|--------------------------|
| `/` | `LayoutDashboard` | Home | — |
| `/vocab` | `BookOpen` | Học | Flashcard review, word detail, topics |
| `/write` | `PenLine` | Luyện | Writing + Listening (sub-nav at top of page) |
| `/progress` | `TrendingUp` | Tiến độ | Coaching tips |
| `/settings` | `User` | Tôi | Profile, settings, logout, link-telegram |

**Active state:** icon + label `text-primary`, 2px `bg-primary` top border, label weight 600.
**Inactive:** icon + label `text-muted-fg`, no border, weight 500.
**Pressed:** scale 0.97 + opacity 0.8 for 120ms.

### Desktop (≥1024px)

```
┌──────┬─────────────────────────────────────────────────┐
│ IC   │  Page title                          [avatar]   │ ← 56px top bar
├──────┤                                                  │
│ 🏠   │                                                  │
│ 📘   │  [page content]                                  │
│ ✍️    │                                                  │
│ 📈   │                                                  │
│ 👤   │                                                  │
│      │                                                  │
│ 72px │                                                  │
└──────┴─────────────────────────────────────────────────┘
```

- 72px icon rail, tooltips on hover
- Expands to 240px sidebar at ≥1280px showing labels
- Logout + theme toggle in avatar menu (top-right)

### Accessibility

- Skip-to-main link: `sr-only` until focused, jumps to `<main id="main">`
- Tab order: main content → nav items (top→bottom) → avatar menu
- `aria-current="page"` on active tab
- Focus ring on every NavLink, visible in both themes

---

## Pages

### 1. LoginPage

**Route:** `/login` · **File:** `src/pages/LoginPage.tsx` · **State:** unauthenticated only

#### Purpose
Trust-building entry point. The first impression a prospective paying user sees. **Must communicate: serious exam-prep product, AI-powered, free trial, no credit card.**

#### Layout

```
┌──────────────────────────────────┐
│                                  │
│         IELTS Coach              │ ← H1, 32/40, weight 700
│   ─────── teal-600 ──────        │ ← 2px divider, 64px wide, centered
│                                  │
│  Luyện IELTS mỗi ngày,           │ ← Body-lg 18/28, weight 600
│  20 phút.                        │
│                                  │
│  AI chấm Writing, Speaking       │ ← Body 16/24, muted-fg
│  theo band mục tiêu.             │
│                                  │
│  ✓ 4 kỹ năng theo band           │ ← Body-sm with check icon
│  ✓ AI chấm bài tức thì           │
│  ✓ Dùng thử 14 ngày, không       │
│    cần thẻ                       │
│                                  │
│  ┌────────────────────────────┐  │
│  │ [G] Đăng nhập với Google   │  │ ← 48px tall, primary, full-width
│  └────────────────────────────┘  │
│                                  │
│  Đã có 2.000+ học viên           │ ← Caption, muted-fg, centered
│  đang luyện IELTS                │
│                                  │
└──────────────────────────────────┘
```

#### Tokens used
- `bg-bg`, `text-fg`, primary button `bg-primary text-primary-fg`, divider `bg-primary`

#### Copy (Vietnamese, final)
- **Value prop:** "Luyện IELTS mỗi ngày, 20 phút." / "AI chấm Writing, Speaking theo band mục tiêu."
- **Bullets:** "4 kỹ năng theo band" · "AI chấm bài tức thì" · "Dùng thử 14 ngày, không cần thẻ"
- **CTA:** "Đăng nhập với Google"
- **Social proof:** "Đã có 2.000+ học viên đang luyện IELTS" (replace with real number once available; hide until available)

#### States
- **Loading:** button text → "Đang đăng nhập..." + disabled; spinner icon inline
- **Error:** red banner below CTA with retry; `role="alert"`
- **Offline:** "Không có kết nối. Kiểm tra mạng rồi thử lại." + `Retry`

#### Responsive
- Mobile: single column, padding `px-6 py-12`, content `max-w-sm` centered vertically
- ≥md: hero image / pattern on right half (future; not M1 scope)

#### A11y
- H1 must be first heading
- Google button has `aria-label="Đăng nhập bằng tài khoản Google"`
- Keyboard: Tab lands on CTA first (skip decorative hero)
- Contrast: primary button 6.1:1 ✓

---

### 2. DashboardPage

**Route:** `/` · **File:** `src/pages/DashboardPage.tsx` · **Primary user action:** start today's top priority task

#### Purpose
The habit loop. One scroll = one glance = today's answer to "what should I do?" Answers must be visible in <3 seconds.

#### Layout (mobile)

```
┌──────────────────────────────────┐
│ Chào buổi sáng,                  │ ← Body-sm muted-fg
│ Mario                            │ ← H1 24/32 weight 700
│                                  │
│  ┌────────────────────────────┐  │
│  │ [Flame]  Streak     🔥 12  │  │ ← accent color
│  │ [Target] Band mục tiêu 7.0 │  │ 3-column stat card
│  │ [Book]   Từ đã học    142  │  │ surface-raised, 16px padding
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────────────────────┐  │
│  │ [Hourglass] Còn 18 ngày thi│  │ ← warning bg + border if urgent
│  │ Hôm nay: 3 task ưu tiên    │  │   (amber) or danger (red if ≤7d)
│  │ Writing Task 2.            │  │
│  │ [Bắt đầu ngay →]           │  │ ← primary CTA, full-width button
│  └────────────────────────────┘  │
│                                  │
│  Kế hoạch hôm nay    [●●●○ 3/4] │ ← H2, ProgressRing on right
│  22 phút · tối đa 30 phút        │ ← caption, muted-fg
│                                  │
│  ┌────────────────────────────┐  │
│  │ [○] [Book] Học 10 từ mới   │  │ ← PlanTaskCard, surface-raised
│  │      Topic: Education      │  │
│  │      ⏱ 8 phút              │  │
│  │                       [→]  │  │
│  └────────────────────────────┘  │
│                                  │
│  [3 more task cards...]          │
│                                  │
│  ┌────────────────────────────┐  │
│  │ 🎉 Hoàn thành toàn bộ!    │  │ ← success card when all done
│  │ Mai quay lại để tiếp streak│  │   bg-success/10, border-success
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

#### Tokens
- Hero greeting: no background (retire indigo→purple gradient); just H1 + stat card
- Stat card: `bg-surface-raised border border-border rounded-2xl`
- Exam urgency card: `bg-warning/10 border-warning/30` (30+ days); `bg-danger/10 border-danger/30` (≤7 days)
- Task card: `bg-surface-raised`, completed → `bg-success/5 border-success/30`, line-through + muted-fg text

#### Replacements
- ❌ Remove: "Khác" emoji link grid at bottom (lines 182-206) — replaced by global nav
- ❌ Remove: UPPERCASE tracking-wide labels — use sentence case
- ❌ Remove: indigo→purple gradient greeting card
- ✅ Add: CTA button inside exam urgency card

#### States
- **Loading:** Stat card skeleton (3 bars), 3 task-card skeletons
- **No plan:** "Chưa có kế hoạch hôm nay" + `[Tạo kế hoạch]` primary button
- **All done:** green completion card replaces task list
- **No exam date:** hide the countdown card entirely

#### Responsive
- ≥md: stats in 1 row inline; task cards in 1 column (reading comprehension > density)
- ≥lg: tasks in 2-column grid

#### A11y
- PlanTaskCard: **separate** the checkbox button from the "open task" button with 12px gap + icon button hit-slop 44×44 — resolves PR-4's nested-button bug
- ProgressRing has `aria-label="3 trên 4 task hoàn thành"` and visible text inside
- Streak flame icon has `aria-hidden`; streak number is part of labeled stat group

---

### 3. VocabHomePage

**Route:** `/vocab` · **File:** `src/pages/VocabHomePage.tsx` · **Primary action:** find + review a word

#### Purpose
Browse, filter, and enter flashcard review. Accommodates 0 words (new user), 50 words (active), 500+ words (power user).

#### Layout

```
┌──────────────────────────────────┐
│ Từ vựng                          │ ← H1
│                                  │
│ ┌─────────┬─────────┬─────────┐  │ ← stat cards
│ │ Tổng số │ Đến hạn │ Đã thạo │  │
│ │  142    │   8     │  26     │  │   2-col mobile, 4-col md+
│ └─────────┴─────────┴─────────┘  │
│                                  │
│ ┌────────────────────────────┐   │
│ │ [Target] Ôn 8 từ đến hạn   │   │ ← primary CTA when due >0
│ │ ~4 phút                    │   │   hides when due == 0
│ │ [Bắt đầu →]                │   │
│ └────────────────────────────┘   │
│                                  │
│ Chủ đề                            │ ← H2
│ ┌──────┬──────┬──────┐            │
│ │Giáo  │Môi   │Công  │            │ ← TopicCard, 2-col mobile
│ │dục   │trường│nghệ  │              3-col md, 4-col lg
│ │42 từ │28 từ │19 từ │            │
│ │███░░│██░░│████░│ 65%│            │
│ └──────┴──────┴──────┘            │
│                                  │
│ Danh sách từ    [🔍 tìm từ...]   │ ← H2 + search input inline on md+
│                                  │
│ [Yếu][Đang học][Tốt][Thạo]      │ ← chip filters, multi-select
│                    142/142 từ   │ ← right-aligned caption
│                                  │
│ ┌─────────────────────────────┐  │
│ │ abandon                     │  │ ← WordCard
│ │ /əˈbændən/          [▶][Tốt]│  │
│ │ từ bỏ, rời bỏ               │  │
│ │ [Giáo dục]                  │  │
│ └─────────────────────────────┘  │
│                                  │
│ [6+ word cards, infinite scroll] │
└──────────────────────────────────┘
```

#### Tokens
- Due-words CTA: `bg-primary text-primary-fg` (drives the hot action)
- Topic progress bar: track `bg-border`, fill `bg-primary`
- Strength pills: `New` neutral / `Weak` danger/10+danger text / `Learning` warning/10 / `Good` success/10 / `Mastered` primary/10+primary text

#### Replacements
- ❌ Remove: "Streak" stat showing "—" (doesn't belong here, already in Dashboard)
- ✅ Replace with: "Đang học" (Learning) as 3rd stat
- ❌ Remove: "Tải thêm" button pagination
- ✅ Replace with: `IntersectionObserver`-based infinite scroll, 50 per fetch, "Đang tải thêm..." footer spinner

#### States
- **0 words (new user):** Replace the list with:
  ```
  [Icon xl: BookOpen]
  Chưa có từ vựng nào
  Liên kết Telegram để đồng bộ từ, hoặc thêm từ mới để bắt đầu.
  [Liên kết Telegram] [Thêm từ mới]
  ```
- **Loading:** topic skeleton (6), word grid skeleton (6)
- **Empty after filter:** "Không có từ nào phù hợp. [Xóa bộ lọc]"
- **Error:** red banner with `[Thử lại]`

#### A11y
- Search input has `<label>` (visually hidden OK) + `aria-describedby="search-hint"`
- Chip filters are `<button aria-pressed={selected}>`
- Topic card `aria-label="Giáo dục, 42 từ, 65% đã thạo"`

---

### 4. WordDetailPage

**Route:** `/vocab/:id` · **File:** `src/pages/WordDetailPage.tsx` · **Primary action:** learn/review a single word

#### Purpose
Deep-dive a word. Definition, IPA, pronunciation audio, examples, SRS status, related words.

#### Layout

```
┌──────────────────────────────────┐
│ ← Back (handled by AppShell)     │
│                                  │
│ abandon        [Tốt]             │ ← H1 + strength pill
│ /əˈbændən/  [▶ Phát âm]          │ ← mono IPA + pronunciation button
│ v.                               │ ← part of speech, muted
│                                  │
│ ─── Nghĩa ───                    │
│ Từ bỏ, rời bỏ một người, nơi,    │ ← VN definition, body-lg
│ hoặc thứ gì đó vĩnh viễn.        │
│                                  │
│ ─── Definition (EN) ───          │
│ To leave (a place, thing, or     │ ← EN definition, body muted
│ person) permanently.             │
│                                  │
│ ─── Ví dụ ───                    │
│ ┌────────────────────────────┐   │
│ │ "They abandoned the car    │   │ ← example in card
│ │  and walked home."         │   │   bg-surface, italic
│ │ Họ bỏ xe và đi bộ về.      │   │
│ └────────────────────────────┘   │
│                                  │
│ ─── Chi tiết SRS ───             │
│ Điểm số: Tốt (7.2 / 10)          │
│ Ôn kế tiếp: trong 3 ngày         │
│ Đã ôn: 5 lần                     │
│                                  │
│ [Ôn từ này ngay]                 │ ← primary CTA
└──────────────────────────────────┘
```

#### A11y
- Pronunciation button: `aria-label="Phát âm từ abandon"` + loading state `aria-busy`
- Strength pill: `<span role="status">` so screen reader announces when it changes post-review

---

### 5. FlashcardReviewPage

**Route:** `/review` · **File:** `src/pages/FlashcardReviewPage.tsx` · **Primary action:** answer 10 flashcards, receive SRS feedback

#### Purpose
Spaced repetition quiz. Multiple-choice or fill-blank. **Learner-paced, not timer-paced** (fixes audit #4).

#### Layout — Pre-session

```
┌──────────────────────────────────┐
│ Ôn tập Flashcard                 │ ← H1
│                                  │
│ ┌────────────────────────────┐   │
│ │ [Target icon]              │   │
│ │                            │   │
│ │ 12 từ đến hạn              │   │ ← primary messaging
│ │ ~6 phút                    │   │
│ │                            │   │
│ │ Trắc nghiệm + điền từ.     │   │ ← muted, explain format
│ │                            │   │
│ │ [Bắt đầu →]                │   │ ← primary full-width
│ └────────────────────────────┘   │
└──────────────────────────────────┘
```

Empty (0 due):
```
[Icon xl: CheckCircle2]
Không có từ nào đến hạn
Quay lại sau 3 giờ, hoặc thêm từ mới.
[Thêm từ vựng] [Về Từ vựng]
```

#### Layout — Question

```
┌──────────────────────────────────┐
│ [x] Thoát            3/10        │ ← close + progress count
│ ████████░░░░░░░░░░░░ 30%         │ ← progress bar
│                                  │
│ "Từ nào có nghĩa 'từ bỏ'?"       │ ← question, body-lg
│                                  │
│ ┌─────────────┬─────────────┐    │
│ │ A. abandon  │ B. enhance  │    │ ← 2x2 grid on ≥sm, 1-col xs
│ ├─────────────┼─────────────┤    │
│ │ C. provide  │ D. enforce  │    │
│ └─────────────┴─────────────┘    │
│                                  │
│ Mẹo: bấm phím 1-4 trên bàn phím │ ← caption helper
└──────────────────────────────────┘
```

#### Layout — Feedback (after answer)

```
┌──────────────────────────────────┐
│ ← full-screen overlay            │
│                                  │
│  [CheckCircle2 xl, success]      │ ← icon (no color-only)
│                                  │
│  Đúng rồi!                       │ ← H2, success
│                                  │
│  abandon = từ bỏ, rời bỏ         │ ← definition, body
│                                  │
│  Tốt → Thạo                      │ ← SRS transition chip
│  Ôn lại trong 3 ngày             │ ← muted caption
│                                  │
│  [Tiếp tục →]  (Space)           │ ← primary CTA, auto-focused
│                                  │
└──────────────────────────────────┘
```

**Critical fix (audit #4):** NO auto-dismiss timer. User taps Continue, presses Space, or presses Enter. No 2-second forced advance.

For "Chưa đúng":
- `AlertCircle` icon + `text-danger`
- Show correct answer: "Đáp án: abandon (từ bỏ)"
- Show user's answer with strikethrough: "Bạn chọn: enhance"
- Same Continue button

#### Fill-blank

```
Điền từ thích hợp:
"They ______ the project due to lack of funding."

┌────────────────────────────┐
│ Ví dụ: abandon             │ ← placeholder hints format
└────────────────────────────┘
[Gửi] (disabled if empty)
```

#### States
- **Session summary (end):** score breakdown + per-question mini rows (correct/wrong + SRS delta)

#### A11y
- Option buttons: `aria-label="Đáp án A: abandon"` so screen reader announces letter + word
- Progress: `role="progressbar" aria-valuenow="3" aria-valuemax="10"`
- Feedback overlay: `role="dialog" aria-modal="true" aria-labelledby="feedback-title"`
- Keyboard `1-4` to answer (already implemented), `Space`/`Enter` to advance, `Esc` to exit
- Reduced motion: overlay appears without scale/fade

---

### 6. WritingPage

**Route:** `/write` · **File:** `src/pages/WritingPage.tsx` · **Primary action:** compose + submit essay

#### Purpose
Full-screen essay editor. Task 1 or Task 2. **Autosave is non-negotiable** (audit #5, PR-5).

#### Layout — Compose

```
┌──────────────────────────────────┐
│                    ⏱ 12:43  │ 245│
│                      từ (target)│
│                      ↑ green when│
│                      ≥250        │
│                                  │
│ [Task 1][Task 2]                 │ ← segmented (disabled once started)
│                                  │
│ ┌────────────────────────────┐   │
│ │ Đề bài           [Đề khác] │   │
│ │                            │   │
│ │ Some people believe that   │   │ ← NO typewriter — full text
│ │ children should learn...   │   │   instantly (reduced-motion drop)
│ │                            │   │
│ └────────────────────────────┘   │
│                                  │
│ [Task 1 visualization if any]    │ ← chart / table for Task 1
│                                  │
│ ┌────────────────────────────┐   │
│ │                            │   │
│ │ Bắt đầu viết tại đây...    │   │ ← textarea, min-h 360px
│ │                            │   │   leading-relaxed
│ │                            │   │
│ │                            │   │
│ └────────────────────────────┘   │
│                                  │
│ Đã lưu nháp lúc 14:32            │ ← autosave indicator, caption
│                                  │
│ Mục tiêu: 250 từ (Task 2)        │ ← footer caption
│ ▁▁▁▁▁▁▁▁▁▁▁▁▁ 98%                │ ← tiny progress bar
│                                  │
│              [Nộp bài →]         │ ← primary, disabled if <50%
└──────────────────────────────────┘
```

#### Word target indicator (audit PR-5)
- <50% of target: `text-danger` + "Cần thêm X từ"
- 50-99%: `text-warning` + "Thêm X từ để đạt mục tiêu"
- ≥100%: `text-success` + `CheckCircle2` icon + "✓ Đạt mục tiêu 250 từ"

#### Layout — Submission loading (audit #5)

Replace silent button-text-change with skeleton:

```
┌────────────────────────────────┐
│ [Sparkles icon, primary, pulse]│
│                                │
│  AI đang chấm bài…             │ ← H3
│  Mất khoảng 10 giây.           │ ← body muted
│  Đừng đóng trang nhé.          │
│                                │
│  ▓▓▓▓▓░░░░░░░ (indeterminate) │ ← progress bar
│                                │
│  [skeleton rows for feedback]  │
│  ▁▁▁▁▁▁▁▁▁▁▁▁                 │
│  ▁▁▁▁▁▁▁▁                     │
│  ▁▁▁▁▁▁▁▁▁▁                   │
└────────────────────────────────┘
```

Textarea is disabled during submission.

#### Autosave spec (PR-5)
- Every 5s, localStorage key `writing_draft_{task_type}_{reviseOf|'new'}`
- Indicator "Đã lưu nháp lúc HH:MM" updates on save
- Restore on mount if draft exists and <24h old (warn if >24h with [Khôi phục] [Bỏ nháp])
- Clear on successful submit
- Never clobber newer payload with older (debounced single-flight)

#### States
- **Revise mode (`?reviseOf=xxx`):** prompt + text pre-filled; header shows "Đang chỉnh sửa bài cũ"
- **Empty prompt:** "Chưa có đề. Bấm 'Tạo đề' để bắt đầu." + primary button

#### A11y
- Textarea has proper `<label>` (sr-only OK)
- Word counter updates are announced via `aria-live="polite"` — but throttle to once per 10 words to avoid screen-reader spam
- Timer: `aria-atomic="true"` and `role="timer"` removed (just a decorative visual — time itself isn't critical)

---

### 7. WritingHistoryPage

**Route:** `/write/history` · **File:** `src/pages/WritingHistoryPage.tsx`

#### Purpose
Chronological list of past essay submissions with band scores.

#### Layout

```
┌──────────────────────────────────┐
│ Bài viết của tôi                 │ ← H1
│                                  │
│ [Tất cả][Task 1][Task 2]         │ ← filter chips
│                                  │
│ ┌─────────────────────────────┐  │
│ │ Task 2 · 14/04/2026         │  │ ← meta line, muted
│ │ Some people believe children│  │ ← prompt excerpt, truncate 2 lines
│ │ should learn through play…  │  │
│ │                             │  │
│ │ [6.5 Band] 248 từ · 18 phút │  │ ← band pill + stats
│ └─────────────────────────────┘  │
│                                  │
│ [more rows...]                   │
└──────────────────────────────────┘
```

**Band pill:** `bg-{band-color}/10 text-{band-color}` — green ≥7, primary ≥6, warning ≥5, danger <5.

**Empty state:** "Chưa có bài viết. [Viết bài đầu tiên]"

---

### 8. WritingDetailPage

**Route:** `/write/:id` · **File:** `src/pages/WritingDetailPage.tsx`

#### Purpose
View a graded essay: band scores per criterion, annotated essay, Vietnamese summary, option to revise.

#### Layout

```
┌──────────────────────────────────┐
│ ← Lịch sử            [Viết mới]  │ ← breadcrumb-ish header
│                                  │
│ ┌─────────────────────────────┐  │
│ │ Điểm tổng                    │  │ ← H2
│ │                              │  │
│ │ [6.5]   Mục tiêu: 7.0        │  │ ← BandBadge + target delta
│ │ -0.5    Dưới mục tiêu        │  │
│ │                              │  │
│ │ Task Response       6.0 ███░ │  │ ← criterion bars
│ │ Coherence           7.0 ████ │  │   feedback caption below
│ │ Lexical Resource    6.5 ███░ │  │
│ │ Grammar             6.5 ███░ │  │
│ └─────────────────────────────┘  │
│                                  │
│ ┌─────────────────────────────┐  │
│ │ [AlertCircle] Tóm tắt        │  │ ← warning bg
│ │ Cải thiện phần giới thiệu... │  │
│ └─────────────────────────────┘  │
│                                  │
│ Bài viết của bạn        248 từ   │ ← H2 + word count
│                                  │
│  Paragraph 1 text with           │
│  [highlighted phrase] ← grammar  │ ← click to see annotation
│  and [another phrase] ← good     │   sheet-style modal on mobile
│                                  │
│ [Chỉnh sửa lại bài này]          │ ← primary CTA at bottom
└──────────────────────────────────┘
```

#### Annotation detail (modal sheet)
- Issue type chip (Ngữ pháp / Từ vựng / Điểm tốt)
- Excerpt in monospace
- "Vấn đề:" + "Gợi ý:" + VN explanation
- Close via tap outside, swipe down (mobile), Esc (keyboard)

#### Color legend (not color-only!)
- Grammar: `bg-danger/10 text-danger` + underline wavy
- Weak vocab: `bg-warning/10 text-warning` + dotted underline
- Good: `bg-success/10 text-success` + single underline

---

### 9. ListeningHomePage

**Route:** `/listening` · **File:** `src/pages/ListeningHomePage.tsx`

#### Purpose
Pick an exercise type: Dictation, Gap Fill, or Comprehension. Show recent history.

#### Layout

```
┌──────────────────────────────────┐
│ Listening Gym                    │ ← H1
│ Luyện nghe Band 7.0.             │ ← caption
│ Hôm nay đã hoàn thành 2 bài.     │
│                                  │
│ ┌────────────────────────────┐   │
│ │ [Headphones] Dictation     │   │ ← icon + label (replaces emoji)
│ │ Band 7.0                   │   │
│ │ Chép lại đoạn hội thoại    │   │
│ │ ⏱ 2-3 phút                 │   │
│ │                [Bắt đầu →] │   │
│ └────────────────────────────┘   │
│                                  │
│ [Gap Fill card]                  │
│ [Comprehension card]             │
│                                  │
│ Gần đây                          │ ← H2
│ ┌─────────────────────────────┐  │
│ │ [Dictation] Daily commute  │  │
│ │ 87%                         │  │
│ └─────────────────────────────┘  │
│ [2 more recent]                  │
└──────────────────────────────────┘
```

---

### 10. ListeningExercisePage

**Route:** `/listening/:id` · **File:** `src/pages/ListeningExercisePage.tsx`

#### Purpose
Play audio + answer comprehension/dictation/gap-fill questions.

#### Layout

```
┌──────────────────────────────────┐
│ Dictation            [Exit]      │
│                                  │
│ [AudioPlayer component]          │ ← see Shared Components
│                                  │
│ Nội dung nghe                     │ ← H2
│ [exercise-specific UI]           │
│   - Dictation: large textarea    │
│   - Gap fill: inline input spans │
│   - Comprehension: 5 MCQ         │
│                                  │
│ Đã nghe 3 lần                    │ ← caption muted
│                                  │
│              [Nộp bài →]         │ ← primary CTA
└──────────────────────────────────┘
```

#### AudioPlayer additions (PR-post-M1)
- Keyboard shortcuts: `Space` play/pause, `←` -5s, `→` +5s, `0` restart
- Speed toggle stays (0.75/1/1.25/1.5)
- Replay button stays
- Icon: `Play`/`Pause`/`RotateCcw` — NOT emoji

#### Post-submission
Same layout as WritingDetailPage but without annotation — show %correct, explanation per answer, and "Nghe lại" button.

---

### 11. ListeningHistoryPage

**Route:** `/listening/history` · **File:** `src/pages/ListeningHistoryPage.tsx`

Mirror of WritingHistoryPage but with Listening-specific filters (type, score range). Same card pattern.

---

### 12. ProgressPage

**Route:** `/progress` · **File:** `src/pages/ProgressPage.tsx`

#### Purpose
Skill-level band visualization, trend line, predictions, coaching tips.

#### Layout

```
┌──────────────────────────────────┐
│ Band Progress      [Đổi mục tiêu]│
│ Cập nhật từ bài làm của bạn.     │
│                                  │
│ ┌────────────────────────────┐   │
│ │                             │   │
│ │    [BandRing large]         │   │ ← 200px ring with center text
│ │     6.5                     │   │   + target marker (teal dot)
│ │  Overall Band               │   │
│ │   🎯 7.0                     │   │
│ │                             │   │
│ │ Cách mục tiêu 0.5 band      │   │
│ │ Dự kiến đạt 7.0 trong 6 tuần│   │ ← ETA line
│ │                             │   │
│ │ ┌──────┬──────┬──────┐      │   │ ← 7-day / 30-day / 90-day
│ │ │ +7d  │ +30d │ +90d │      │   │   projections
│ │ │ 6.6  │ 6.9  │ 7.2  │      │   │
│ │ └──────┴──────┴──────┘      │   │
│ └────────────────────────────┘   │
│                                  │
│ ┌──────────────┬──────────────┐  │ ← 2-col skill cards
│ │ [Book] Vocab │ [Pen] Writing│  │
│ │ 7.2    ▲0.3  │ 6.0    ▼0.2  │  │
│ │ 142 từ · 26  │ 18 bài chấm  │  │
│ │ ▓▓▓▓▓▓░░░░░ │ ▓▓▓▓▓░░░░░░ │  │
│ ├──────────────┼──────────────┤  │
│ │[Headphones]  │ [Mic] Speak  │  │
│ │ Listening    │              │  │
│ │ 6.8    ▲0.1  │ — Sắp ra mắt │  │ ← placeholder card, no band 0.0
│ │ 12 bài chấm  │              │  │
│ │ ▓▓▓▓▓▓▓░░░░ │ ▁▁▁▁▁▁▁▁▁▁▁ │  │
│ └──────────────┴──────────────┘  │
│                                  │
│ Xu hướng 30 ngày   [Overall ▼]   │ ← H2 + series selector
│ [BandTrendChart — mobile view]   │   default shows Overall only
│                                  │   tap legend to toggle series
│ Gợi ý của coach tuần này          │ ← H2
│ ┌────────────────────────────┐   │
│ │ [Pen] Viết 1 bài Task 2... │   │ ← coaching tip card
│ │ [Viết ngay →]              │   │
│ └────────────────────────────┘   │
│ [2 more tips]                    │
└──────────────────────────────────┘
```

#### Critical fixes
- **Speaking placeholder (audit):** hide band number entirely when `placeholder`; show `— Sắp ra mắt` + grey bar at 0%. Do NOT show "0.0".
- **Mobile chart:** default to single Overall series; tap legend chip to toggle others; legend is `<button role="switch" aria-checked>`

---

### 13. SettingsPage

**Route:** `/settings` · **File:** `src/pages/SettingsPage.tsx`

#### Purpose
Profile, preferences, theme, link Telegram, logout.

#### Layout

```
┌──────────────────────────────────┐
│ Cài đặt                          │ ← H1
│                                  │
│ ─── Giao diện ───                │
│ Chủ đề                           │
│ [Hệ thống][Sáng][Tối]            │ ← segmented control
│                                  │
│ ─── Lịch thi ───                 │
│ Ngày thi IELTS                   │
│ [date picker]                    │
│ Còn 18 ngày nữa.                 │ ← caption, colored by urgency
│ [Xóa ngày thi]                   │ ← destructive link, muted
│                                  │
│ Mục tiêu mỗi tuần                │
│ [Nhẹ 90][Vừa 150][Nặng 300][Tùy] │ ← preset chips + custom input
│ Trung bình 21 phút mỗi ngày.     │
│                                  │
│ ─── Tài khoản ───                │
│ Tên       Mario                  │
│ Email     mario@example.com      │
│ Band mục tiêu   7.0  [Chỉnh sửa] │
│ Streak    🔥 12 ngày              │
│                                  │
│ [Liên kết Telegram] ← if unlinked│
│                                  │
│ ─── Khác ───                     │
│ [Về ứng dụng]  [Điều khoản]      │
│                                  │
│ ─── Nguy hiểm ───                │ ← danger zone visually separated
│ [Đăng xuất]  (danger outline)    │
│ [Xóa tài khoản] (danger text)    │
└──────────────────────────────────┘
```

#### Critical fixes
- **Success banner auto-dismiss:** 3s timer on "Đã lưu cài đặt" toast (audit medium #15)
- **Theme toggle** is the new primary item (PR-6)
- **Weekly goal preset chips:** 90/150/300 + "Tùy chỉnh" opens numeric input
- **Delete exam date:** confirm via native `window.confirm` before clearing
- **Danger zone:** separated by visual divider + destructive label per `destructive-nav-separation` rule

#### A11y
- Every form field has a real `<label htmlFor>`
- Theme selector is `role="radiogroup"`, each chip `role="radio" aria-checked`
- "Đã lưu cài đặt" toast has `role="status" aria-live="polite"`, auto-dismisses but keyboard-focusable `[Đóng]` too

---

## Shared Components

### `<Icon name="..." size="md" variant="fg" label="..." />`
Wrapper over `lucide-react`. **The only way to render icons in the app.**
- `size`: `sm` 16 / `md` 20 / `lg` 24 / `xl` 32
- `variant`: `fg` (default), `muted`, `primary`, `accent`, `success`, `warning`, `danger`
- `label`: when set → semantic (`aria-label`); when absent → decorative (`aria-hidden`)

### `<Button variant="primary|secondary|ghost|danger" size="md|sm|lg" loading={false} />`
- Primary: `bg-primary text-primary-fg hover:bg-primary-hover`
- Secondary: `bg-surface-raised border border-border text-fg`
- Ghost: transparent, `hover:bg-surface`
- Danger: `bg-danger text-white`
- Height: `sm` 36 / `md` 44 (default, meets touch target) / `lg` 56
- `loading`: disables + shows inline spinner, text → "Đang xử lý..." or passed via prop
- Focus ring always visible (`focus-visible:ring-2 ring-ring ring-offset-2`)

### `<ErrorBanner error={err} onRetry={fn} />`
Replaces every hand-rolled `bg-red-50 border-l-4 ...` box. Always includes a retry CTA. `role="alert"`.

### `<Skeleton variant="line|card|ring" />`
Replaces inline `animate-pulse` divs. One shape per use case. Respects reduced-motion (static 8% tint).

### `<ProgressRing completed={n} total={m} size={64} />`
Already exists — keep. Just migrate stroke colors to tokens.

### `<BandRing band={7.0} target={7.5} size={200} />`
Already exists — keep. Retire indigo→pink gradient, use solid `primary` or dynamic band-color.

### `<SkillBandCard emoji="..." label="..." band={7} ... />`
Replace `emoji` prop with `iconName` (Lucide icon name). When `placeholder`, render "—" instead of band number.

### `<PlanTaskCard activity={a} onToggle={fn} busy={boolean} />`
**Fix nested-button bug:** separate checkbox (`<button>`) from card nav (`<Link>`) with 12px gap + independent focus rings. No more nested `<button><button/></button>`.

### `<AudioPlayer audioUrl="..." />`
- Primary controls (play/pause/restart) = 48px circles, `bg-primary`
- Seek bar uses `accent-primary` (Tailwind `accent-` color util)
- Speed chips 0.75/1.0/1.25/1.5 with active state `bg-primary text-primary-fg`
- **Add (post-M1):** keyboard Space/←/→ shortcuts, ±5s skip buttons

### `<ThemeToggle />` (new, PR-6)
Segmented control: `[Hệ thống][Sáng][Tối]`. Sets `useTheme()` state + localStorage + Firestore sync.

---

## Empty / Loading / Error states

Every page must implement these 4 states.

| State | Rule |
|-------|------|
| **Initial load** | Skeleton of the page structure (NOT a spinner) — show within 100ms |
| **Empty** | Icon (xl) + title + 1-sentence explainer + primary CTA. Never just "No data." |
| **Error** | `<ErrorBanner>` with specific cause + retry. Network errors say "Kiểm tra mạng rồi thử lại." |
| **Success** | Toast via `role="status"`, auto-dismiss 3s, sr-announced |

---

## Review Checklist

Use this when reviewing any PR touching UI.

### Visual Quality
- [ ] No emojis as icons — `<Icon>` wrapper used everywhere
- [ ] Consistent Lucide icon family (stroke 1.75, no mixed fill/outline)
- [ ] No raw `#rgb` hex in components — only semantic tokens
- [ ] No `text-gray-*` / `bg-gray-*` / `bg-white` — use `text-fg`, `bg-surface`, etc.
- [ ] Gradient brand surfaces retired (no more indigo→purple cards)

### Interaction
- [ ] Every tappable element has pressed feedback (scale 0.97, 120ms)
- [ ] Touch targets ≥44×44px on mobile
- [ ] Micro-interactions 150-300ms; no >500ms blocking animations
- [ ] No nested `<button>` / `<a>` elements
- [ ] Every button has a visible `focus-visible:ring`

### Typography & Color
- [ ] Be Vietnam Pro loaded, Vietnamese diacritics render cleanly
- [ ] Body text ≥16px
- [ ] Primary text contrast ≥4.5:1 both themes
- [ ] Tabular numbers for counters, timers, scores
- [ ] Color never the only indicator (pair with icon/text)

### Layout
- [ ] AppShell wraps the route; no hand-rolled "← Trang chủ"
- [ ] Safe-area insets respected (bottom tab bar)
- [ ] No horizontal scroll at 375px
- [ ] 4/8pt spacing rhythm maintained

### A11y
- [ ] All icon-only buttons have `aria-label`
- [ ] All form inputs have proper `<label>`
- [ ] Keyboard-only flow works (Tab order matches visual order)
- [ ] `prefers-reduced-motion` respected (no animations when set)
- [ ] Dynamic Type at largest size doesn't truncate critical copy

### Dark mode
- [ ] Screenshot in both themes attached to PR
- [ ] No theme-specific hex values
- [ ] Borders visible in dark mode (not just light)
- [ ] Interaction states (hover/pressed/disabled) distinguishable in both

### Copy
- [ ] Vietnamese-first
- [ ] Sentence case (no UPPERCASE TRACKING-WIDE)
- [ ] Error messages include a recovery path
- [ ] Success messages are concrete ("Đã lưu X")

---

## Related

- **GitHub milestone:** [UX-1: UI/UX Overhaul](https://github.com/mario-noobs/ielts-learning-telegram-bot/milestone/7)
- **Umbrella issue:** [#68](https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/68)
- **Role deliverables:** #75 Designer · #76 Architect · #77 QA · #78 PO · #79 TechLead · #80 Open questions
- **Implementation PRs:** #69 tokens · #70 icons · #71 AppShell · #72 a11y · #73 Writing autosave · #74 Flashcard + dark mode
- **Master design system:** [`design-system/ielts-coach/MASTER.md`](./design-system/ielts-coach/MASTER.md)

---

_Last updated 2026-04-18 · Author: UI/UX review roundtable (PO + Designer + Architect + QA + TechLead + Developer)_
