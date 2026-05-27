import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Icon from '../components/Icon'
import PronunciationButton from '../components/PronunciationButton'
import { apiFetch, apiStream } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'

type Strength = 'New' | 'Weak' | 'Learning' | 'Good' | 'Mastered'
type VisualStrength = 'Weak' | 'Learning' | 'Good' | 'Mastered'

interface DailyWord {
  word: string
  word_id?: string
  daily_source?: string
  reviewed?: boolean
  is_favourite?: boolean
  strength?: Strength
  definition_en: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  example_en: string
  example_vi: string
}

interface DailyStatus {
  reviewed_count: number
  total_count: number
  timezone: string
  next_reset_at: string
  extra_limit?: number
  extra_used?: number
  extra_remaining?: number
}

// Module-level cache: survives tab switches within the same session.
// Keyed by date so it auto-invalidates the next day.
let _cache: { date: string; words: DailyWord[]; topic: string; status: DailyStatus | null } | null = null

export function __resetDailyWordsCacheForTest() {
  _cache = null
}

function todayKey() {
  return new Date().toISOString().slice(0, 10)
}

function topicLabel(
  slug: string,
  t: (k: string, o?: Record<string, unknown>) => string,
): string {
  if (!slug) return ''
  return t(`topicNames.${slug}`, { defaultValue: slug })
}

const STRENGTH_OPTIONS: VisualStrength[] = ['Weak', 'Learning', 'Good', 'Mastered']

function visualStrength(value?: Strength): VisualStrength {
  return value === 'New' || !value ? 'Weak' : value
}

function formatResetCountdown(nextResetAt: string, now: Date): string {
  const resetAt = new Date(nextResetAt)
  const ms = Math.max(0, resetAt.getTime() - now.getTime())
  const totalMinutes = Math.ceil(ms / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${minutes}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

function DailyWordCard({
  item,
  index,
  isFavourite,
  onFavouriteToggle,
  onStrengthChange,
  extraLabel,
}: {
  item: DailyWord
  index: number
  isFavourite: boolean
  onFavouriteToggle: () => void
  onStrengthChange: (next: VisualStrength) => void
  extraLabel: string
}) {
  const strength = visualStrength(item.strength)
  return (
    <article className="bg-surface-raised rounded-xl shadow-sm p-5 border border-transparent">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-xs text-muted-fg tabular-nums">#{index}</span>
            <h3 className="text-xl font-semibold text-fg">{item.word}</h3>
            {item.part_of_speech && (
              <span className="text-xs uppercase tracking-wide text-muted-fg">
                {item.part_of_speech}
              </span>
            )}
            {item.daily_source === 'extra' && (
              <span className="rounded-md bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
                {extraLabel}
              </span>
            )}
          </div>
          {item.ipa && <p className="text-xs text-muted-fg mt-1">/{item.ipa}/</p>}
        </div>
        <div className="shrink-0 flex items-center gap-1.5">
          <Link
            to={`/learn/vocab/${encodeURIComponent(item.word)}`}
            onClick={() => track('daily_word_detail_opened', { word: item.word })}
            aria-label={`Xem chi tiết ${item.word}`}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-fg hover:bg-surface hover:text-primary"
          >
            <Icon name="Eye" size="sm" />
          </Link>
          <button
            type="button"
            onClick={onFavouriteToggle}
            disabled={!item.word_id}
            aria-label={isFavourite ? 'Bỏ yêu thích' : 'Yêu thích'}
            className={`inline-flex h-8 w-8 items-center justify-center rounded-lg transition-colors disabled:opacity-40 ${
              isFavourite ? 'text-danger' : 'text-muted-fg hover:bg-surface hover:text-danger'
            }`}
          >
            <Icon name="Heart" size="sm" variant={isFavourite ? 'danger' : 'muted'} />
          </button>
          <PronunciationButton word={item.word} compact />
        </div>
      </header>
      <div className="mt-3 space-y-1">
        {item.definition_en && <p className="text-fg">{item.definition_en}</p>}
        {item.definition_vi && (
          <p className="text-sm text-muted-fg">{item.definition_vi}</p>
        )}
      </div>
      {(item.example_en || item.example_vi) && (
        <div className="mt-3 border-l-2 border-border pl-3 space-y-0.5">
          {item.example_en && (
            <p className="text-sm text-fg italic">"{item.example_en}"</p>
          )}
          {item.example_vi && (
            <p className="text-xs text-muted-fg italic">"{item.example_vi}"</p>
          )}
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-1.5">
        {STRENGTH_OPTIONS.map((option) => {
          const active = option === strength
          return (
            <button
              key={option}
              type="button"
              disabled={!item.word_id}
              onClick={() => onStrengthChange(option)}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-40 ${
                active
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border text-muted-fg hover:border-primary/30 hover:text-fg'
              }`}
            >
              {option}
            </button>
          )
        })}
      </div>
    </article>
  )
}

function WordSkeleton() {
  return (
    <article className="bg-surface-raised rounded-xl shadow-sm p-5 border border-transparent animate-pulse">
      <div className="flex items-baseline gap-2 mb-3">
        <div className="h-3 bg-border rounded w-6" />
        <div className="h-5 bg-border rounded w-32" />
        <div className="h-3 bg-border rounded w-10" />
      </div>
      <div className="space-y-2">
        <div className="h-4 bg-border rounded w-3/4" />
        <div className="h-3 bg-border rounded w-1/2" />
      </div>
      <div className="mt-3 border-l-2 border-border pl-3 space-y-1.5">
        <div className="h-3 bg-border rounded w-4/5" />
        <div className="h-3 bg-border rounded w-2/3" />
      </div>
    </article>
  )
}

function GenerationProgress({
  current,
  total,
  t,
}: {
  current: number
  total: number
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  const hasTotal = total > 0
  const pct = hasTotal ? Math.min(96, Math.round((current / total) * 100)) : 12
  const stage = !hasTotal
    ? 'waiting'
    : current === 0
      ? 'preparing'
      : current >= total
        ? 'finalizing'
        : current / total >= 0.75
          ? 'almost'
          : 'generating'

  return (
    <section
      aria-live="polite"
      aria-label={t('daily.generation.title')}
      className="rounded-xl border border-primary/30 bg-primary/5 p-4"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon name="Sparkles" size="md" variant="primary" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-fg">
              {t(`daily.generation.stages.${stage}`)}
            </p>
            <p className="text-xs font-medium tabular-nums text-muted-fg">
              {hasTotal
                ? t('daily.generation.percent', { pct })
                : t('daily.generation.starting')}
            </p>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-bg">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-muted-fg">
            {hasTotal
              ? t('daily.generation.count', { current, total })
              : t('daily.generation.waitingDetail')}
          </p>
        </div>
      </div>
    </section>
  )
}

export default function DailyWordsPage() {
  const { t, i18n } = useTranslation('vocab')
  const cached = _cache?.date === todayKey() ? _cache : null
  const [words, setWords] = useState<DailyWord[]>(cached?.words ?? [])
  const [favouriteIds, setFavouriteIds] = useState<Set<string>>(
    () => new Set((cached?.words ?? []).filter((w) => w.is_favourite && w.word_id).map((w) => w.word_id as string)),
  )
  const [topic, setTopic] = useState(cached?.topic ?? '')
  const [status, setStatus] = useState<DailyStatus | null>(cached?.status ?? null)
  const [now, setNow] = useState(() => new Date())
  const [expectedCount, setExpectedCount] = useState(cached?.words.length ?? 0)
  const [streaming, setStreaming] = useState(!cached)
  const [loadingExtra, setLoadingExtra] = useState(false)
  const [extraNotice, setExtraNotice] = useState<string | null>(null)
  const [extraError, setExtraError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const statusTrackedRef = useRef(false)

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60000)
    return () => window.clearInterval(id)
  }, [])

  useEffect(() => {
    if (!status || statusTrackedRef.current) return
    statusTrackedRef.current = true
    track('daily_vocab_status_viewed', {
      reviewed_count: status.reviewed_count,
      total_count: status.total_count,
      timezone: status.timezone,
    })
  }, [status])

  useEffect(() => {
    if (!streaming) return
    const controller = new AbortController()

    async function streamWords() {
      const collected: DailyWord[] = []
      let streamedTopic = ''
      let streamedDate = todayKey()
      let streamedStatus: DailyStatus | null = null
      try {
        const res = await apiStream('/api/v1/vocabulary/daily/stream', {
          method: 'POST',
          signal: controller.signal,
        })
        if (!res.body) return

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const event = JSON.parse(line.slice(6))
              if (event.type === 'start') {
                setExpectedCount(event.count)
                setTopic(event.topic)
                streamedDate = event.date || streamedDate
                if (event.status) {
                  streamedStatus = event.status
                  setStatus(event.status)
                }
                streamedTopic = event.topic
              } else if (event.type === 'word') {
                collected.push(event.word)
                setWords((prev) => [...prev, event.word])
                if (event.word.is_favourite && event.word.word_id) {
                  setFavouriteIds((prev) => new Set(prev).add(event.word.word_id))
                }
              } else if (event.type === 'done') {
                _cache = {
                  date: streamedDate,
                  words: collected,
                  topic: streamedTopic,
                  status: streamedStatus,
                }
                setStreaming(false)
              } else if (event.type === 'error') {
                setError(t('daily.loadError', { defaultValue: 'Failed to generate words.' }))
                setStreaming(false)
              }
            } catch {
              // ignore malformed SSE line
            }
          }
        }
      } catch (e) {
        if (controller.signal.aborted) return
        setError(localizeError(e))
        setStreaming(false)
      } finally {
        if (!controller.signal.aborted) setStreaming(false)
      }
    }

    streamWords()
    return () => controller.abort()
  }, [streaming, t])

  const skeletonCount = streaming && expectedCount > words.length ? expectedCount - words.length : 0
  const reviewableCount = words.filter((word) => Boolean(word.word_id)).length
  const reviewedCount = status?.reviewed_count ?? words.filter((word) => word.reviewed).length
  const totalCount = status?.total_count ?? words.length
  const extraUsed = status?.extra_used ?? words.filter((word) => word.daily_source === 'extra').length
  const extraLimit = status?.extra_limit ?? 5
  const extraRemaining = status?.extra_remaining ?? Math.max(0, extraLimit - extraUsed)
  const extraRequestCount = Math.min(5, extraRemaining)
  const nearComplete = totalCount > 0 && reviewedCount >= Math.max(1, totalCount - 1)
  const showLearnMore = !streaming && nearComplete && extraRemaining > 0
  const showExtraLimit = !streaming && totalCount > 0 && status != null && extraRemaining <= 0
  const exactReset = status?.next_reset_at
    ? new Intl.DateTimeFormat(i18n.language, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        timeZone: status.timezone,
        timeZoneName: 'short',
      }).format(new Date(status.next_reset_at))
    : ''
  const resetCountdown = status?.next_reset_at
    ? formatResetCountdown(status.next_reset_at, now)
    : ''
  const generationTotal = expectedCount || status?.total_count || 0

  const applyDailyResponse = (res: {
    date: string
    words: DailyWord[]
    topic: string
    reviewed_count: number
    total_count: number
    timezone: string
    next_reset_at: string
    extra_limit?: number
    extra_used?: number
    extra_remaining?: number
  }) => {
    const nextStatus = {
      reviewed_count: res.reviewed_count,
      total_count: res.total_count,
      timezone: res.timezone,
      next_reset_at: res.next_reset_at,
      extra_limit: res.extra_limit,
      extra_used: res.extra_used,
      extra_remaining: res.extra_remaining,
    }
    setWords(res.words)
    setFavouriteIds(new Set(res.words.filter((w) => w.is_favourite && w.word_id).map((w) => w.word_id as string)))
    setTopic(res.topic)
    setStatus(nextStatus)
    setExpectedCount(res.words.length)
    _cache = {
      date: res.date,
      words: res.words,
      topic: res.topic,
      status: nextStatus,
    }
  }

  const toggleFavourite = async (word: DailyWord) => {
    if (!word.word_id) return
    const next = !favouriteIds.has(word.word_id)
    const apply = (isFavourite: boolean) => {
      setFavouriteIds((prev) => {
        const updated = new Set(prev)
        if (isFavourite) updated.add(word.word_id as string)
        else updated.delete(word.word_id as string)
        return updated
      })
      setWords((prev) =>
        prev.map((w) =>
          w.word_id === word.word_id ? { ...w, is_favourite: isFavourite } : w,
        ),
      )
      if (_cache?.date === todayKey()) {
        _cache = {
          ..._cache,
          words: _cache.words.map((w) =>
            w.word_id === word.word_id ? { ...w, is_favourite: isFavourite } : w,
          ),
        }
      }
    }
    apply(next)
    try {
      await apiFetch(`/api/v1/vocabulary/${word.word_id}/favourite`, {
        method: 'POST',
        body: JSON.stringify({ favourite: next }),
      })
      track('daily_word_favourited', { word: word.word, favourite: next })
    } catch (e) {
      apply(!next)
      setError(localizeError(e))
    }
  }

  const updateStrength = async (word: DailyWord, next: VisualStrength) => {
    if (!word.word_id) return
    const before = words
    const apply = (items: DailyWord[]) => {
      setWords(items)
      if (_cache?.date === todayKey()) {
        _cache = { ..._cache, words: items }
      }
    }
    const reviewed = Boolean(word.reviewed || next !== 'Weak')
    apply(words.map((w) => (
      w.word_id === word.word_id ? { ...w, strength: next, reviewed } : w
    )))
    try {
      await apiFetch(`/api/v1/words/${encodeURIComponent(word.word_id)}/strength`, {
        method: 'PATCH',
        body: JSON.stringify({ strength: next }),
      })
      if (!word.reviewed && reviewed && status) {
        const nextStatus = {
          ...status,
          reviewed_count: Math.min(status.total_count, status.reviewed_count + 1),
        }
        setStatus(nextStatus)
        if (_cache?.date === todayKey()) {
          _cache = { ..._cache, status: nextStatus }
        }
      }
      track('daily_word_strength_changed', { word: word.word, strength: next })
    } catch (e) {
      apply(before)
      setError(localizeError(e))
    }
  }

  const learnMore = async () => {
    if (extraRequestCount <= 0) return
    const previousExtraCount = words.filter((word) => word.daily_source === 'extra').length
    setLoadingExtra(true)
    setExtraNotice(null)
    setExtraError(null)
    track('daily_vocab_learn_more_clicked', {
      count: extraRequestCount,
      remaining: extraRemaining,
    })
    try {
      const res = await apiFetch<{
        date: string
        words: DailyWord[]
        topic: string
        reviewed_count: number
        total_count: number
        timezone: string
        next_reset_at: string
        extra_limit: number
        extra_used: number
        extra_remaining: number
      }>('/api/v1/vocabulary/daily/extra', {
        method: 'POST',
        body: JSON.stringify({ count: extraRequestCount }),
      })
      applyDailyResponse(res)
      const added = Math.max(
        0,
        res.words.filter((word) => word.daily_source === 'extra').length - previousExtraCount,
      )
      setExtraNotice(t('daily.learnMore.added', { count: added }))
      track('daily_vocab_extra_words_added', {
        count: added,
        remaining: res.extra_remaining,
      })
    } catch (e) {
      setExtraError(localizeError(e))
    } finally {
      setLoadingExtra(false)
    }
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-4">
        <div className="bg-danger/10 border-l-4 border-danger p-4 rounded-lg text-danger text-sm">
          {error}
        </div>
      </div>
    )
  }

  if (!streaming && words.length === 0) {
    return (
      <div className="max-w-lg mx-auto p-4">
        <EmptyState
          illustration="empty-vocab"
          title={t('daily.empty.title')}
          description={t('daily.empty.description')}
          primaryAction={{ label: t('daily.empty.cta'), to: '/vocab' }}
        />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-fg">{t('daily.heading')}</h1>
        <p className="text-sm text-muted-fg">
          {topic && <span>{topicLabel(topic, t)} · </span>}
          {streaming
            ? t('daily.generating', {
                defaultValue: 'Generating… {count} / {total}',
                count: words.length,
                total: expectedCount || '…',
              })
            : t('daily.wordCount', { defaultValue: '{count} words', count: words.length })}
        </p>
      </header>

      {streaming && (
        <GenerationProgress
          current={words.length}
          total={generationTotal}
          t={t}
        />
      )}

      {totalCount > 0 && (
        <section
          aria-label={t('daily.status.title')}
          className="rounded-xl border border-border bg-surface-raised p-4"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-fg">
                {reviewedCount >= totalCount
                  ? t('daily.status.complete')
                  : t('daily.status.progress', {
                      reviewed: reviewedCount,
                      total: totalCount,
                    })}
              </p>
              {status?.next_reset_at && (
                <p className="mt-1 text-xs text-muted-fg">
                  {t('daily.status.reset', {
                    countdown: resetCountdown,
                    time: exactReset,
                  })}
                </p>
              )}
            </div>
            <div className="h-2 rounded-full bg-surface sm:w-40 overflow-hidden">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${totalCount === 0 ? 0 : (reviewedCount / totalCount) * 100}%` }}
              />
            </div>
          </div>
        </section>
      )}

      {(showLearnMore || showExtraLimit) && (
        <section className="rounded-xl border border-border bg-surface-raised p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-fg">
                {t('daily.learnMore.title')}
              </p>
              <p className="mt-1 text-xs text-muted-fg">
                {showLearnMore
                  ? t('daily.learnMore.description', {
                      remaining: extraRemaining,
                      limit: extraLimit,
                    })
                  : t('daily.learnMore.limit', {
                      countdown: resetCountdown,
                      time: exactReset,
                    })}
              </p>
            </div>
            {showLearnMore && (
              <button
                type="button"
                onClick={learnMore}
                disabled={loadingExtra}
                className="inline-flex shrink-0 items-center justify-center rounded-lg border border-primary/40 px-4 py-2 text-sm font-semibold text-primary hover:bg-primary/5 disabled:opacity-50"
              >
                {loadingExtra
                  ? t('daily.learnMore.loading')
                  : t('daily.learnMore.cta', { count: extraRequestCount })}
              </button>
            )}
          </div>
          {extraNotice && (
            <p className="mt-3 text-xs font-medium text-success">{extraNotice}</p>
          )}
          {extraError && (
            <p className="mt-3 text-xs font-medium text-danger">{extraError}</p>
          )}
          {loadingExtra && (
            <div className="mt-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
              <p className="text-xs font-medium text-primary">
                {t('daily.learnMore.progress')}
              </p>
            </div>
          )}
        </section>
      )}

      <div className="space-y-3">
        {words.map((item, i) => (
          <DailyWordCard
            key={`${item.word}-${i}`}
            item={item}
            index={i + 1}
            isFavourite={Boolean(item.word_id && favouriteIds.has(item.word_id))}
            onFavouriteToggle={() => toggleFavourite(item)}
            onStrengthChange={(next) => updateStrength(item, next)}
            extraLabel={t('daily.learnMore.badge')}
          />
        ))}
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <WordSkeleton key={`sk-${i}`} />
        ))}
      </div>

      {!streaming && (
        <>
          {reviewableCount > 0 && (
            <Link
              to="/learn/daily/quiz"
              onClick={() => track('vocab_review_started_from_daily', { count: reviewableCount })}
              className="block rounded-xl bg-primary px-4 py-3 text-center text-sm font-semibold text-primary-fg hover:bg-primary-hover transition-colors"
            >
              {t('daily.reviewToday', {
                defaultValue: "Review today's words",
                count: reviewableCount,
              })}
            </Link>
          )}

          <div className="grid grid-cols-1 gap-3 pt-2">
            <Link
              to="/learn/daily/flip"
              className="p-4 min-h-[56px] rounded-xl border-2 border-border bg-surface-raised text-fg text-center font-medium hover:border-primary hover:bg-primary/5 transition-colors"
            >
              📖 {t('daily.openFlip')}
            </Link>
          </div>

          <div className="flex items-center justify-between rounded-xl border border-border bg-surface-raised px-4 py-3">
            <p className="text-sm text-muted-fg">{t('daily.allWordsLabel')}</p>
            <Link
              to="/learn/vocab"
              className="text-sm font-medium text-primary hover:underline"
            >
              {t('daily.allWordsCta')} →
            </Link>
          </div>
        </>
      )}
    </div>
  )
}
