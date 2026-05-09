/**
 * /learn/vocab — group by topic + sort by mastery (US-#231).
 *
 * Two big shifts vs the previous flat list:
 *
 *   1. **Group by topic.** Each topic is a collapsible section. Topics
 *      with more "Weak" words sort to the top so the user sees the
 *      gap-closing work first.
 *   2. **Sort by mastery within topic.** Inside each section, words
 *      run Weak → Learning → Good → Mastered. Tiebreak: nearest SRS
 *      review date (most due first).
 *
 * Other UX:
 *   - Top-right: progress ring + 4 clickable stat chips that filter
 *     the visible words. Filter persists in localStorage.
 *   - Per-topic pagination disclosure: topics with > 20 words show 20
 *     and a "Hiện thêm" button (not global page navigation).
 *   - Strength chip is clickable → popover with 4 options. Calls
 *     PATCH /api/v1/words/{id}/strength with optimistic UI update.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import EmptyState from '../components/EmptyState'
import Icon from '../components/Icon'

type Strength = 'New' | 'Weak' | 'Learning' | 'Good' | 'Mastered'
type VisualStrength = 'Weak' | 'Learning' | 'Good' | 'Mastered'

interface VocabularyWord {
  id: string
  word: string
  definition: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  topic: string
  strength: Strength
  srs_next_review: string | null
  added_at: string | null
}

interface WordListResponse {
  items: VocabularyWord[]
  next_cursor: string | null
}

interface TopicSummary {
  id: string
  name: string
  word_count: number
  subtopics: string[]
}

interface TopicsResponse {
  items: TopicSummary[]
  total_words: number
}

const FILTER_BUCKETS: VisualStrength[] = ['Weak', 'Learning', 'Good', 'Mastered']
const WORDS_PER_TOPIC_DEFAULT = 20

// Strength order for sorting (lower rank = "more urgent / less mastered").
const STRENGTH_RANK: Record<Strength, number> = {
  New: 0, Weak: 0, Learning: 1, Good: 2, Mastered: 3,
}

// 'New' words live in the Weak bucket visually — the API still returns
// 'New' for words that have never been quizzed, but the UI doesn't
// distinguish that from Weak (both mean "needs work").
function visualStrength(s: Strength): VisualStrength {
  return s === 'New' ? 'Weak' : s
}

const STRENGTH_STYLES: Record<VisualStrength, string> = {
  Weak: 'bg-danger/10 text-danger',
  Learning: 'bg-warning/10 text-warning',
  Good: 'bg-success/10 text-success',
  Mastered: 'bg-primary/10 text-primary',
}

const STRENGTH_BORDER: Record<VisualStrength, string> = {
  Weak: 'border-danger/30',
  Learning: 'border-warning/30',
  Good: 'border-success/30',
  Mastered: 'border-primary/30',
}

function topicLabel(
  slug: string,
  apiName: string,
  t: (k: string, o?: Record<string, unknown>) => string,
): string {
  return t(`topicNames.${slug}`, { defaultValue: apiName })
}

// ── localStorage helpers ─────────────────────────────────────────────

const FILTER_KEY = 'ui.vocab.filter'
const COLLAPSED_KEY = 'ui.vocab.collapsed'
const EXPANDED_KEY = 'ui.vocab.expanded'

function loadFilter(): VisualStrength | null {
  try {
    const v = localStorage.getItem(FILTER_KEY)
    return (FILTER_BUCKETS as readonly string[]).includes(v ?? '')
      ? (v as VisualStrength)
      : null
  } catch {
    return null
  }
}

function loadSet(key: string): Set<string> {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return new Set()
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? new Set(arr) : new Set()
  } catch {
    return new Set()
  }
}

function saveSet(key: string, set: Set<string>): void {
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(set)))
  } catch { /* ignore quota errors */ }
}

// ── Strength chip + popover ──────────────────────────────────────────

interface StrengthChipProps {
  strength: VisualStrength
  onChange: (next: VisualStrength) => Promise<void>
  disabled?: boolean
}

function StrengthChip({ strength, onChange, disabled }: StrengthChipProps) {
  const { t } = useTranslation('vocab')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)

  // Close on outside click. ref scopes the listener to the chip.
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const choose = async (next: VisualStrength) => {
    setOpen(false)
    if (next === strength) return
    setBusy(true)
    try {
      await onChange(next)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          if (!disabled && !busy) setOpen((o) => !o)
        }}
        aria-label={t('byTopic.row.changeMastery', {
          current: t(`strength.${strength}`),
        })}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled || busy}
        className={`text-xs font-medium px-2 py-0.5 rounded-full transition-opacity ${STRENGTH_STYLES[strength]} ${
          busy ? 'opacity-50' : 'hover:opacity-80'
        }`}
      >
        {t(`strength.${strength}`)}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1.5 w-44 rounded-lg border border-border bg-surface-raised shadow-lg z-30 py-1"
        >
          <p className="px-3 py-1.5 text-xs text-muted-fg">
            {t('byTopic.row.changeMasteryConfirm')}
          </p>
          {FILTER_BUCKETS.map((opt) => (
            <button
              key={opt}
              type="button"
              role="menuitem"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                choose(opt)
              }}
              className={`flex w-full items-center justify-between px-3 py-1.5 text-sm hover:bg-surface ${
                opt === strength ? 'font-semibold' : ''
              }`}
            >
              <span>{t(`strength.${opt}`)}</span>
              {opt === strength && <Icon name="Check" size="sm" variant="success" />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Word row ────────────────────────────────────────────────────────

interface WordRowProps {
  word: VocabularyWord
  onStrengthChange: (id: string, next: VisualStrength) => Promise<void>
}

function WordRow({ word, onStrengthChange }: WordRowProps) {
  const visual = visualStrength(word.strength)
  return (
    <Link
      to={`/learn/vocab/${encodeURIComponent(word.word)}`}
      className="flex items-center gap-3 rounded-lg border border-transparent bg-surface-raised px-3 py-2.5 hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-fg truncate">
          {word.word}
          {word.ipa && (
            <span className="ml-1.5 text-xs font-normal text-muted-fg">
              /{word.ipa}/
            </span>
          )}
          {word.part_of_speech && (
            <span className="ml-1.5 text-xs font-normal text-muted-fg">
              {word.part_of_speech}
            </span>
          )}
        </p>
        {word.definition_vi && (
          <p className="text-xs text-muted-fg truncate mt-0.5">
            {word.definition_vi}
          </p>
        )}
      </div>
      {/* Stop-propagation handled inside the chip — click on the chip
          opens the popover, click anywhere else on the row navigates. */}
      <span className="shrink-0">
        <StrengthChip
          strength={visual}
          onChange={(next) => onStrengthChange(word.id, next)}
        />
      </span>
    </Link>
  )
}

// ── Topic section ────────────────────────────────────────────────────

interface TopicSectionProps {
  topic: TopicSummary
  words: VocabularyWord[]
  collapsed: boolean
  expanded: boolean  // "show more" disclosure for topics with >N words
  onToggleCollapse: () => void
  onToggleExpand: () => void
  onStrengthChange: (id: string, next: VisualStrength) => Promise<void>
  t: (k: string, o?: Record<string, unknown>) => string
}

function TopicSection({
  topic, words, collapsed, expanded, onToggleCollapse, onToggleExpand,
  onStrengthChange, t,
}: TopicSectionProps) {
  const masteredCount = words.filter((w) => visualStrength(w.strength) === 'Mastered').length
  const masteredPct = words.length === 0 ? 0 : (masteredCount / words.length) * 100
  const visible = expanded ? words : words.slice(0, WORDS_PER_TOPIC_DEFAULT)
  const overflow = Math.max(0, words.length - WORDS_PER_TOPIC_DEFAULT)

  return (
    <section className="rounded-xl border border-border bg-surface-raised">
      <button
        type="button"
        onClick={onToggleCollapse}
        aria-expanded={!collapsed}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-t-xl"
      >
        <Icon
          name="ChevronDown"
          size="sm"
          variant="muted"
          className={`shrink-0 transition-transform duration-base ease-out-soft ${
            collapsed ? '-rotate-90' : ''
          }`}
        />
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-fg truncate">
            {topicLabel(topic.id, topic.name, t)}
          </p>
        </div>
        <div className="shrink-0 text-xs text-muted-fg">
          {t('byTopic.topicSection.count', { count: words.length })}
        </div>
        <div className="hidden md:block w-24 shrink-0">
          <div className="h-1.5 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-primary"
              style={{ width: `${masteredPct}%` }}
            />
          </div>
        </div>
      </button>

      {!collapsed && (
        <div className="border-t border-border p-2 space-y-1.5">
          {visible.map((w) => (
            <WordRow
              key={w.id}
              word={w}
              onStrengthChange={onStrengthChange}
            />
          ))}
          {overflow > 0 && !expanded && (
            <button
              type="button"
              onClick={onToggleExpand}
              className="block w-full text-center py-2 text-sm text-primary hover:bg-surface rounded-lg"
            >
              {t('byTopic.topicSection.showMore', { count: overflow })}
            </button>
          )}
        </div>
      )}
    </section>
  )
}

// ── Page ────────────────────────────────────────────────────────────

export default function VocabHomePage() {
  const { t } = useTranslation('vocab')
  const [words, setWords] = useState<VocabularyWord[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [topics, setTopics] = useState<TopicSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [filter, setFilter] = useState<VisualStrength | null>(() => loadFilter())
  const [collapsed, setCollapsed] = useState<Set<string>>(() => loadSet(COLLAPSED_KEY))
  const [expanded, setExpanded] = useState<Set<string>>(() => loadSet(EXPANDED_KEY))

  useEffect(() => {
    let cancelled = false
    Promise.all([
      apiFetch<WordListResponse>('/api/v1/vocabulary?limit=100'),
      apiFetch<TopicsResponse>('/api/v1/topics'),
    ])
      .then(([wordsRes, topicsRes]) => {
        if (cancelled) return
        setWords(wordsRes.items)
        setNextCursor(wordsRes.next_cursor)
        setTopics(topicsRes.items)
      })
      .catch((e) => !cancelled && setError((e as Error).message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    try {
      if (filter) localStorage.setItem(FILTER_KEY, filter)
      else localStorage.removeItem(FILTER_KEY)
    } catch { /* ignore */ }
  }, [filter])

  useEffect(() => { saveSet(COLLAPSED_KEY, collapsed) }, [collapsed])
  useEffect(() => { saveSet(EXPANDED_KEY, expanded) }, [expanded])

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return
    setLoadingMore(true)
    try {
      const res = await apiFetch<WordListResponse>(
        `/api/v1/vocabulary?limit=100&cursor=${encodeURIComponent(nextCursor)}`,
      )
      setWords((prev) => [...prev, ...res.items])
      setNextCursor(res.next_cursor)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoadingMore(false)
    }
  }

  // Optimistic update — flip the strength locally first, roll back if
  // the API rejects. Server returns strength_applied=false when the
  // override was a no-op (e.g. user clicked Mastered but they were
  // already past it via quiz progress); we don't notify the user.
  const onStrengthChange = async (
    wordId: string, next: VisualStrength,
  ): Promise<void> => {
    const before = words
    setWords((prev) =>
      prev.map((w) => (w.id === wordId ? { ...w, strength: next } : w)),
    )
    try {
      await apiFetch(`/api/v1/words/${encodeURIComponent(wordId)}/strength`, {
        method: 'PATCH',
        body: JSON.stringify({ strength: next }),
      })
    } catch (e) {
      setWords(before)
      setError((e as Error).message)
    }
  }

  // Stat counts use ALL words (filter doesn't affect denominators).
  const counts = useMemo(() => {
    const m: Record<VisualStrength, number> = {
      Weak: 0, Learning: 0, Good: 0, Mastered: 0,
    }
    for (const w of words) m[visualStrength(w.strength)]++
    return m
  }, [words])

  const total = words.length
  const masteredPct = total === 0 ? 0 : (counts.Mastered / total) * 100

  // Group → sort. Topics ordered by Weak count desc; within topic by
  // strength rank then SRS due date.
  const groupedTopics = useMemo(() => {
    type Entry = { topic: TopicSummary; words: VocabularyWord[]; weakCount: number }
    const byTopic = new Map<string, Entry>()
    for (const tp of topics) {
      byTopic.set(tp.id, { topic: tp, words: [], weakCount: 0 })
    }
    for (const w of words) {
      if (filter && visualStrength(w.strength) !== filter) continue
      const entry = byTopic.get(w.topic)
      if (!entry) {
        // Topic returned by /api/v1/topics may miss; create on the fly
        // so words still surface even if the topics endpoint trails the
        // word list.
        byTopic.set(w.topic, {
          topic: { id: w.topic, name: w.topic, word_count: 0, subtopics: [] },
          words: [w],
          weakCount: visualStrength(w.strength) === 'Weak' ? 1 : 0,
        })
        continue
      }
      entry.words.push(w)
      if (visualStrength(w.strength) === 'Weak') entry.weakCount++
    }
    const out = Array.from(byTopic.values()).filter((e) => e.words.length > 0)
    for (const e of out) {
      e.words.sort((a, b) => {
        const ra = STRENGTH_RANK[a.strength]
        const rb = STRENGTH_RANK[b.strength]
        if (ra !== rb) return ra - rb
        const ta = a.srs_next_review ? new Date(a.srs_next_review).getTime() : Infinity
        const tb = b.srs_next_review ? new Date(b.srs_next_review).getTime() : Infinity
        return ta - tb
      })
    }
    out.sort((a, b) => {
      if (b.weakCount !== a.weakCount) return b.weakCount - a.weakCount
      return topicLabel(a.topic.id, a.topic.name, t).localeCompare(
        topicLabel(b.topic.id, b.topic.name, t),
      )
    })
    return out
  }, [words, topics, filter, t])

  const filteredTotal = useMemo(
    () => groupedTopics.reduce((sum, e) => sum + e.words.length, 0),
    [groupedTopics],
  )

  const toggleCollapsed = (topicId: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(topicId)) next.delete(topicId)
      else next.add(topicId)
      return next
    })
  }

  const toggleExpanded = (topicId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(topicId)) next.delete(topicId)
      else next.add(topicId)
      return next
    })
  }

  return (
    <div className="max-w-5xl mx-auto p-4">
      {/* Header */}
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-fg">
            {t('byTopic.heading')}{' '}
            <span className="inline-block rounded-md bg-primary/10 px-2 py-0.5 text-primary text-xl md:text-2xl">
              {t('byTopic.headingPill')}
            </span>
          </h1>
          <p className="mt-2 text-sm text-muted-fg max-w-xl">
            {t('byTopic.subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-xs text-muted-fg">
              {t('byTopic.progress.label')}
            </p>
            <p className="text-2xl font-bold text-fg">
              {counts.Mastered}<span className="text-base text-muted-fg">/{total}</span>
            </p>
          </div>
          <div
            className="relative h-16 w-16 shrink-0 rounded-full"
            style={{
              background: `conic-gradient(var(--color-primary, #0d9488) ${masteredPct}%, var(--color-surface, #f1f5f9) 0)`,
            }}
            aria-label={t('byTopic.progress.aria', { pct: Math.round(masteredPct) })}
          >
            <div className="absolute inset-1.5 rounded-full bg-bg flex items-center justify-center text-sm font-semibold text-fg">
              {Math.round(masteredPct)}%
            </div>
          </div>
        </div>
      </header>

      {/* Filter chips */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {FILTER_BUCKETS.map((bucket) => {
          const active = filter === bucket
          return (
            <button
              key={bucket}
              type="button"
              onClick={() => setFilter((cur) => (cur === bucket ? null : bucket))}
              aria-pressed={active}
              className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                active
                  ? `${STRENGTH_STYLES[bucket]} ${STRENGTH_BORDER[bucket]}`
                  : 'border-border text-muted-fg hover:text-fg hover:border-primary/40'
              }`}
            >
              {t(`strength.${bucket}`)}
              <span className="ml-1.5 opacity-70">{counts[bucket]}</span>
            </button>
          )
        })}
        {filter && (
          <button
            type="button"
            onClick={() => setFilter(null)}
            className="text-xs text-muted-fg hover:text-fg ml-auto"
          >
            {t('byTopic.clearFilter')}
          </button>
        )}
      </div>

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-4 rounded-lg mb-4">
          <p className="text-danger">{error}</p>
        </div>
      )}

      {/* List body */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-surface-raised p-4 animate-pulse">
              <div className="h-4 bg-border rounded w-1/3 mb-2" />
              <div className="h-3 bg-border rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : filteredTotal === 0 ? (
        words.length === 0 ? (
          <EmptyState
            illustration="empty-vocab"
            title={t('empty.noWords.title')}
            description={t('empty.noWords.description')}
            primaryAction={{ label: t('empty.noWords.cta'), to: '/review' }}
          />
        ) : (
          <EmptyState
            illustration="empty-vocab"
            title={t('byTopic.empty.filtered.title', {
              strength: filter ? t(`strength.${filter}`) : '',
            })}
            description={t('byTopic.empty.filtered.description')}
            primaryAction={{
              label: t('byTopic.empty.filtered.cta'),
              onClick: () => setFilter(null),
            }}
          />
        )
      ) : (
        <div className="space-y-3">
          {groupedTopics.map((entry) => (
            <TopicSection
              key={entry.topic.id}
              topic={entry.topic}
              words={entry.words}
              collapsed={collapsed.has(entry.topic.id)}
              expanded={expanded.has(entry.topic.id)}
              onToggleCollapse={() => toggleCollapsed(entry.topic.id)}
              onToggleExpand={() => toggleExpanded(entry.topic.id)}
              onStrengthChange={onStrengthChange}
              t={t}
            />
          ))}
        </div>
      )}

      {nextCursor && (
        <div className="flex justify-center mt-6">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="px-4 py-2 bg-primary text-primary-fg rounded-lg hover:bg-primary-hover disabled:opacity-50"
          >
            {loadingMore ? t('loadingMore') : t('loadMore')}
          </button>
        </div>
      )}
    </div>
  )
}
