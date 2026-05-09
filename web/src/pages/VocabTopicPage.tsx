/**
 * /learn/vocab/topic/:slug — words within a single topic (US-#231).
 *
 * Drill-down from the topic index. Paginates within the topic via
 * `?topic={slug}` on `/api/v1/vocabulary`. Filter chips + strength
 * popover live here, scoped to this topic only.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { ApiError } from '../lib/apiError'
import EmptyState from '../components/EmptyState'
import Icon from '../components/Icon'

// Errors thrown by apiFetch carry the server's error code as
// `.message` — `.localize()` turns it into prose via the `errors`
// i18n bundle. Without this the user sees raw codes like
// "common.upstream_error" instead of the translated message.
function describeError(e: unknown): string {
  return e instanceof ApiError ? e.localize() : (e as Error).message
}

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

const FILTER_BUCKETS: VisualStrength[] = ['Weak', 'Learning', 'Good', 'Mastered']
const PAGE_LIMIT = 20

const STRENGTH_RANK: Record<Strength, number> = {
  New: 0, Weak: 0, Learning: 1, Good: 2, Mastered: 3,
}

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

interface StrengthChipProps {
  strength: VisualStrength
  onChange: (next: VisualStrength) => Promise<void>
}

function StrengthChip({ strength, onChange }: StrengthChipProps) {
  const { t } = useTranslation('vocab')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement | null>(null)

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
          if (!busy) setOpen((o) => !o)
        }}
        aria-label={t('byTopic.row.changeMastery', {
          current: t(`strength.${strength}`),
        })}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={busy}
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

function WordRow({
  word,
  onStrengthChange,
}: {
  word: VocabularyWord
  onStrengthChange: (id: string, next: VisualStrength) => Promise<void>
}) {
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
      <span className="shrink-0">
        <StrengthChip
          strength={visual}
          onChange={(next) => onStrengthChange(word.id, next)}
        />
      </span>
    </Link>
  )
}

export default function VocabTopicPage() {
  const { t } = useTranslation('vocab')
  const { slug } = useParams<{ slug: string }>()
  const [words, setWords] = useState<VocabularyWord[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<VisualStrength | null>(null)

  useEffect(() => {
    if (!slug) return
    let cancelled = false
    setLoading(true)
    apiFetch<WordListResponse>(
      `/api/v1/vocabulary?topic=${encodeURIComponent(slug)}&limit=${PAGE_LIMIT}`,
    )
      .then((res) => {
        if (cancelled) return
        setWords(res.items)
        setNextCursor(res.next_cursor)
      })
      .catch((e) => !cancelled && setError(describeError(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [slug])

  const loadMore = async () => {
    if (!nextCursor || loadingMore || !slug) return
    setLoadingMore(true)
    try {
      const res = await apiFetch<WordListResponse>(
        `/api/v1/vocabulary?topic=${encodeURIComponent(slug)}&limit=${PAGE_LIMIT}&cursor=${encodeURIComponent(nextCursor)}`,
      )
      setWords((prev) => [...prev, ...res.items])
      setNextCursor(res.next_cursor)
    } catch (e) {
      setError(describeError(e))
    } finally {
      setLoadingMore(false)
    }
  }

  const counts = useMemo(() => {
    const m: Record<VisualStrength, number> = {
      Weak: 0, Learning: 0, Good: 0, Mastered: 0,
    }
    for (const w of words) m[visualStrength(w.strength)]++
    return m
  }, [words])

  const filteredWords = useMemo(() => {
    const list = filter
      ? words.filter((w) => visualStrength(w.strength) === filter)
      : [...words]
    list.sort((a, b) => {
      const ra = STRENGTH_RANK[a.strength]
      const rb = STRENGTH_RANK[b.strength]
      if (ra !== rb) return ra - rb
      const ta = a.srs_next_review ? new Date(a.srs_next_review).getTime() : Infinity
      const tb = b.srs_next_review ? new Date(b.srs_next_review).getTime() : Infinity
      return ta - tb
    })
    return list
  }, [words, filter])

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
      setError(describeError(e))
    }
  }

  if (!slug) return null

  const titleName = topicLabel(slug, slug, t)
  const total = words.length

  return (
    <div className="max-w-3xl mx-auto p-4">
      <Link
        to="/learn/vocab"
        className="text-sm text-muted-fg hover:text-fg inline-flex items-center gap-1"
      >
        <Icon name="ArrowLeft" size="sm" /> {t('byTopic.topicPage.back')}
      </Link>

      <header className="mt-3 mb-6">
        <h1 className="text-2xl md:text-3xl font-bold text-fg">{titleName}</h1>
        <p className="mt-1 text-sm text-muted-fg">
          {t('byTopic.topicPage.subtitle', { count: total })}
        </p>
      </header>

      {/* Filter chips scoped to this topic. Counts come from loaded
          words only — the API returns paginated results, so chip
          counts are accurate for what's currently visible. Loading
          all pages would defeat the point of pagination. */}
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

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-surface-raised p-3 animate-pulse"
            >
              <div className="h-4 bg-border rounded w-1/3" />
            </div>
          ))}
        </div>
      ) : filteredWords.length === 0 ? (
        words.length === 0 ? (
          <EmptyState
            illustration="empty-vocab"
            title={t('empty.noWords.title')}
            description={t('empty.noWords.description')}
            primaryAction={{ label: t('empty.noWords.cta'), to: '/review' }}
          />
        ) : (
          <div className="rounded-lg border border-dashed border-border p-6 text-center">
            <p className="text-sm text-muted-fg">
              {t('byTopic.empty.filtered.title', {
                strength: filter ? t(`strength.${filter}`) : '',
              })}
            </p>
            <button
              type="button"
              onClick={() => setFilter(null)}
              className="mt-3 text-sm text-primary hover:underline"
            >
              {t('byTopic.empty.filtered.cta')}
            </button>
          </div>
        )
      ) : (
        <div className="space-y-1.5">
          {filteredWords.map((w) => (
            <WordRow
              key={w.id}
              word={w}
              onStrengthChange={onStrengthChange}
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
