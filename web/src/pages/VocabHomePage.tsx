/**
 * /learn/vocab — topic index (US-#231).
 *
 * After user feedback that the inline expand/collapse layout couldn't
 * surface rare-strength words without paging through every batch of
 * 100, the home page is now a *topic index*. Each card shows the
 * topic's word count + mastered ratio. Click → drill into
 * `/learn/vocab/topic/:slug`, which paginates within that topic.
 *
 * Home no longer fetches the word list — only the lightweight
 * `/api/v1/topics` aggregate (word_count + mastered_count per topic).
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'
import EmptyState from '../components/EmptyState'
import { useProfile } from '../contexts/AuthContext'
import Icon from '../components/Icon'

interface TopicSummary {
  id: string
  name: string
  word_count: number
  mastered_count: number
  subtopics: string[]
}

interface TopicsResponse {
  items: TopicSummary[]
  total_words: number
}

interface VocabularyWord {
  id: string
  word: string
  definition: string
  definition_vi: string
  ipa: string
  part_of_speech: string
}

interface WordListResponse {
  items: VocabularyWord[]
  next_cursor: string | null
}

interface DailyHistoryWord {
  word: string
  word_id: string
  daily_source?: string
  reviewed: boolean
  is_favourite: boolean
  strength: string
  definition_en: string
  definition_vi: string
  ipa: string
  part_of_speech: string
}

interface DailyHistoryEntry {
  date: string
  topic: string
  words: DailyHistoryWord[]
  total_count: number
  reviewed_count: number
  favourite_count: number
  weak_count: number
  mastered_count: number
}

interface DailyHistoryResponse {
  items: DailyHistoryEntry[]
  timezone: string
}

interface DailyWordsResponse {
  date: string
  topic: string
  words: DailyHistoryWord[]
  reviewed_count: number
  total_count: number
}

type VocabTab = 'topics' | 'favourites' | 'history'

const HISTORY_STATS = [
  ['total', 'total_count'],
  ['reviewed', 'reviewed_count'],
  ['favourites', 'favourite_count'],
  ['weak', 'weak_count'],
  ['mastered', 'mastered_count'],
] as const

function topicLabel(
  slug: string,
  apiName: string,
  t: (k: string, o?: Record<string, unknown>) => string,
): string {
  return t(`topicNames.${slug}`, { defaultValue: apiName })
}

function TopicCard({
  topic,
  t,
}: {
  topic: TopicSummary
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  const total = topic.word_count
  const mastered = topic.mastered_count
  const pct = total === 0 ? 0 : (mastered / total) * 100
  return (
    <Link
      to={`/learn/vocab/topic/${encodeURIComponent(topic.id)}`}
      className="block rounded-xl border border-border bg-surface-raised p-4 transition-colors hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold text-fg truncate">
          {topicLabel(topic.id, topic.name, t)}
        </p>
        <span className="shrink-0 text-xs text-muted-fg">
          {t('byTopic.topicSection.count', { count: total })}
        </span>
      </div>
      <div className="mt-3 h-1.5 bg-surface rounded-full overflow-hidden">
        <div
          className="h-full bg-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-muted-fg mt-1.5">
        {t('byTopic.card.masteryLine', {
          mastered, total, pct: Math.round(pct),
        })}
      </p>
    </Link>
  )
}

function FavouriteWordRow({ word }: { word: VocabularyWord }) {
  return (
    <Link
      to={`/learn/vocab/${encodeURIComponent(word.word)}`}
      onClick={() =>
        track('vocab_favourite_detail_opened', {
          word: word.word,
          word_id: word.id,
        })
      }
      className="flex items-center gap-3 rounded-lg border border-transparent bg-surface-raised px-3 py-2.5 hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <Icon name="Heart" size="sm" variant="danger" />
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
        {(word.definition_vi || word.definition) && (
          <p className="text-xs text-muted-fg truncate mt-0.5">
            {word.definition_vi || word.definition}
          </p>
        )}
      </div>
      <Icon name="ArrowRight" size="sm" variant="muted" />
    </Link>
  )
}

function DailyHistoryWordRow({
  date,
  word,
  t,
}: {
  date: string
  word: DailyHistoryWord
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  return (
    <Link
      to={`/learn/vocab/${encodeURIComponent(word.word)}`}
      onClick={() =>
        track('vocab_history_word_detail_opened', {
          date,
          word: word.word,
          word_id: word.word_id,
        })
      }
      className="flex items-center gap-3 py-2.5 hover:text-primary"
    >
      <div className="min-w-0 flex-1">
        <p className="font-medium text-fg truncate">
          {word.word}
          {word.reviewed && (
            <span className="ml-2 text-xs font-normal text-success">
              {t('history.reviewedBadge')}
            </span>
          )}
        </p>
        {(word.definition_vi || word.definition_en) && (
          <p className="mt-0.5 truncate text-xs text-muted-fg">
            {word.definition_vi || word.definition_en}
          </p>
        )}
      </div>
      {word.is_favourite && <Icon name="Heart" size="sm" variant="danger" />}
      <span className="hidden rounded-md bg-surface px-2 py-1 text-xs text-muted-fg sm:inline">
        {t(`strength.${word.strength}`, { defaultValue: word.strength })}
      </span>
      <Icon name="ArrowRight" size="sm" variant="muted" />
    </Link>
  )
}

function DailyHistoryCard({
  entry,
  details,
  loadingDetails,
  isOpen,
  onToggle,
  t,
}: {
  entry: DailyHistoryEntry
  details?: DailyWordsResponse
  loadingDetails: boolean
  isOpen: boolean
  onToggle: () => void
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  const detailWords = details?.words ?? []
  return (
    <article className="rounded-xl border border-border bg-surface-raised p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-fg">{entry.date}</h2>
            {entry.topic && (
              <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {entry.topic}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-fg">
            {t('history.summary', {
              reviewed: entry.reviewed_count,
              total: entry.total_count,
            })}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40"
            aria-expanded={isOpen}
          >
            <Icon name={isOpen ? 'ChevronDown' : 'ChevronRight'} size="sm" variant="muted" />
            {isOpen ? t('history.hideDetails') : t('history.showDetails')}
          </button>
          <Link
            to={`/learn/daily/quiz?date=${encodeURIComponent(entry.date)}`}
            onClick={() =>
              track('vocab_history_review_started', {
                date: entry.date,
                total: entry.total_count,
              })
            }
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40"
          >
            <Icon name="RotateCcw" size="sm" variant="muted" />
            {t('history.reviewCta')}
          </Link>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {HISTORY_STATS.map(([key, field]) => (
          <div key={key} className="rounded-md bg-surface px-3 py-2">
            <p className="text-xs text-muted-fg">{t(`history.stats.${key}`)}</p>
            <p className="text-lg font-semibold text-fg">{entry[field]}</p>
          </div>
        ))}
      </div>

      {isOpen && (
        <div className="mt-4 divide-y divide-border">
          {loadingDetails ? (
            <div className="py-3 text-sm text-muted-fg">{t('history.loadingDetails')}</div>
          ) : detailWords.length === 0 ? (
            <div className="py-3 text-sm text-muted-fg">{t('history.noDetails')}</div>
          ) : (
            detailWords.map((word) => (
              <DailyHistoryWordRow
                key={`${entry.date}-${word.word_id || word.word}`}
                date={entry.date}
                word={word}
                t={t}
              />
            ))
          )}
        </div>
      )}
    </article>
  )
}

export default function VocabHomePage() {
  const { t } = useTranslation('vocab')
  const profile = useProfile()
  const showLinkPrompt = profile != null && profile.id.startsWith('web_')
  const [topics, setTopics] = useState<TopicSummary[]>([])
  const [preferredSlugs, setPreferredSlugs] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<VocabTab>('topics')
  const [favouriteWords, setFavouriteWords] = useState<VocabularyWord[]>([])
  const [dailyHistory, setDailyHistory] = useState<DailyHistoryEntry[] | null>(null)
  const [openHistoryDate, setOpenHistoryDate] = useState<string | null>(null)
  const [historyDetails, setHistoryDetails] = useState<Record<string, DailyWordsResponse>>({})
  const [loadingHistoryDetails, setLoadingHistoryDetails] = useState<string | null>(null)
  const [loadingFavourites, setLoadingFavourites] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      apiFetch<TopicsResponse>('/api/v1/topics'),
      apiFetch<{ topics: string[] }>('/api/v1/me'),
    ])
      .then(([res, me]) => {
        if (cancelled) return
        setTopics(res.items)
        setPreferredSlugs(Array.isArray(me.topics) ? me.topics : [])
      })
      .catch((e) => !cancelled && setError(localizeError(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (activeTab !== 'favourites') return
    let cancelled = false
    setLoadingFavourites(true)
    apiFetch<WordListResponse>('/api/v1/vocabulary?favourite=true&limit=100')
      .then((res) => {
        if (!cancelled) setFavouriteWords(res.items)
      })
      .catch((e) => !cancelled && setError(localizeError(e)))
      .finally(() => !cancelled && setLoadingFavourites(false))
    return () => {
      cancelled = true
    }
  }, [activeTab])

  useEffect(() => {
    if (activeTab !== 'history' || dailyHistory !== null) return
    let cancelled = false
    setLoadingHistory(true)
    async function loadHistory() {
      try {
        const res = await apiFetch<DailyHistoryResponse>('/api/v1/vocabulary/daily/history?limit=30')
        if (!cancelled) setDailyHistory(res.items)
      } catch (e) {
        if (!cancelled) {
          setError(localizeError(e))
          setDailyHistory([])
        }
      } finally {
        if (!cancelled) setLoadingHistory(false)
      }
    }
    void loadHistory()
    return () => {
      cancelled = true
    }
  }, [activeTab, dailyHistory])

  const toggleHistoryDate = async (date: string) => {
    if (openHistoryDate === date) {
      setOpenHistoryDate(null)
      return
    }
    setOpenHistoryDate(date)
    if (historyDetails[date]) return

    setLoadingHistoryDetails(date)
    try {
      const res = await apiFetch<DailyWordsResponse>(
        `/api/v1/vocabulary/daily/${encodeURIComponent(date)}`,
      )
      setHistoryDetails((prev) => ({ ...prev, [date]: res }))
      track('vocab_history_day_expanded', { date, total: res.total_count })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setLoadingHistoryDetails((current) => (current === date ? null : current))
    }
  }

  const stats = useMemo(() => {
    const total = topics.reduce((sum, tp) => sum + tp.word_count, 0)
    const mastered = topics.reduce((sum, tp) => sum + tp.mastered_count, 0)
    return { total, mastered }
  }, [topics])

  // Preferred topics: shown even with 0 words so the user sees their
  // settings reflected immediately. Sorted least-mastered first among
  // those that have words; 0-word ones trail alphabetically.
  const preferredTopics = useMemo(() => {
    if (preferredSlugs.length === 0) return []
    const byId = Object.fromEntries(topics.map((tp) => [tp.id, tp]))
    return preferredSlugs
      .map((slug) => byId[slug] ?? { id: slug, name: slug, word_count: 0, mastered_count: 0, subtopics: [] })
      .sort((a, b) => {
        if (a.word_count === 0 && b.word_count === 0)
          return topicLabel(a.id, a.name, t).localeCompare(topicLabel(b.id, b.name, t))
        if (a.word_count === 0) return 1
        if (b.word_count === 0) return -1
        const aPct = a.mastered_count / a.word_count
        const bPct = b.mastered_count / b.word_count
        return aPct - bPct
      })
  }, [preferredSlugs, topics, t])

  // Non-preferred topics with at least one word, sorted least-mastered first.
  const otherTopics = useMemo(() => {
    return [...topics]
      .filter((tp) => tp.word_count > 0 && !preferredSlugs.includes(tp.id))
      .sort((a, b) => {
        const aPct = a.mastered_count / a.word_count
        const bPct = b.mastered_count / b.word_count
        if (aPct !== bPct) return aPct - bPct
        return topicLabel(a.id, a.name, t).localeCompare(topicLabel(b.id, b.name, t))
      })
  }, [topics, preferredSlugs, t])

  // Legacy: when no preferred topics set, fall back to all topics with words.
  const orderedTopics = useMemo(() => {
    if (preferredSlugs.length > 0) return []
    return [...topics]
      .filter((tp) => tp.word_count > 0)
      .sort((a, b) => {
        const aPct = a.mastered_count / a.word_count
        const bPct = b.mastered_count / b.word_count
        if (aPct !== bPct) return aPct - bPct
        return topicLabel(a.id, a.name, t).localeCompare(topicLabel(b.id, b.name, t))
      })
  }, [topics, preferredSlugs, t])

  const masteryPct = stats.total === 0 ? 0 : (stats.mastered / stats.total) * 100

  return (
    <div className="max-w-5xl mx-auto p-4">
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
        {stats.total > 0 && (
          <div className="flex items-center gap-4">
            <Link
              to="/learn/review"
              className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 transition-colors"
            >
              {t('byTopic.reviewCta')}
            </Link>
            <div className="text-right">
              <p className="text-xs text-muted-fg">
                {t('byTopic.progress.label')}
              </p>
              <p className="text-2xl font-bold text-fg">
                {stats.mastered}<span className="text-base text-muted-fg">/{stats.total}</span>
              </p>
            </div>
            <div
              className="relative h-16 w-16 shrink-0 rounded-full"
              style={{
                background: `conic-gradient(var(--color-primary, #0d9488) ${masteryPct}%, var(--color-surface, #f1f5f9) 0)`,
              }}
              aria-label={t('byTopic.progress.aria', { pct: Math.round(masteryPct) })}
            >
              <div className="absolute inset-1.5 rounded-full bg-bg flex items-center justify-center text-sm font-semibold text-fg">
                {Math.round(masteryPct)}%
              </div>
            </div>
          </div>
        )}
      </header>

      <div className="mb-5 inline-flex rounded-lg border border-border bg-surface-raised p-1">
        <button
          type="button"
          onClick={() => setActiveTab('topics')}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
            activeTab === 'topics'
              ? 'bg-primary text-primary-fg'
              : 'text-muted-fg hover:text-fg'
          }`}
        >
          <Icon name="BookOpen" size="sm" variant={activeTab === 'topics' ? 'fg' : 'muted'} />
          {t('byTopic.tabs.topics', { defaultValue: 'Topics' })}
        </button>
        <button
          type="button"
          onClick={() => {
            if (activeTab !== 'favourites') {
              track('vocab_favourites_tab_viewed')
            }
            setActiveTab('favourites')
          }}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
            activeTab === 'favourites'
              ? 'bg-primary text-primary-fg'
              : 'text-muted-fg hover:text-fg'
          }`}
        >
          <Icon name="Heart" size="sm" variant={activeTab === 'favourites' ? 'fg' : 'muted'} />
          {t('byTopic.tabs.favourites', { defaultValue: 'Favourites' })}
        </button>
        <button
          type="button"
          onClick={() => {
            if (activeTab !== 'history') {
              track('vocab_history_tab_viewed')
            }
            setActiveTab('history')
          }}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
            activeTab === 'history'
              ? 'bg-primary text-primary-fg'
              : 'text-muted-fg hover:text-fg'
          }`}
        >
          <Icon name="Clock" size="sm" variant={activeTab === 'history' ? 'fg' : 'muted'} />
          {t('byTopic.tabs.history', { defaultValue: 'History' })}
        </button>
      </div>

      {showLinkPrompt && (
        <div
          role="region"
          aria-label={t('linkPrompt.title')}
          className="mb-6 flex flex-col gap-3 rounded-xl border border-primary/30 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex-1">
            <p className="font-semibold text-fg">{t('linkPrompt.title')}</p>
            <p className="text-sm text-muted-fg mt-1">
              {t('linkPrompt.description')}
            </p>
          </div>
          <Link
            to="/settings/link-telegram"
            className="shrink-0 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {t('linkPrompt.cta')}
          </Link>
        </div>
      )}

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-4 rounded-lg mb-4">
          <p className="text-danger">{error}</p>
        </div>
      )}

      {activeTab === 'history' ? (
        loadingHistory || dailyHistory === null ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="rounded-xl border border-border bg-surface-raised p-4 animate-pulse"
              >
                <div className="h-4 bg-border rounded w-1/4" />
                <div className="mt-4 h-12 bg-border rounded" />
              </div>
            ))}
          </div>
        ) : dailyHistory.length === 0 ? (
          <EmptyState
            illustration="empty-vocab"
            title={t('empty.history.title', { defaultValue: 'No daily history yet' })}
            description={t('empty.history.description', {
              defaultValue: 'Daily vocab batches you generate will appear here for future review.',
            })}
            primaryAction={{ label: t('empty.history.cta', { defaultValue: 'View daily words' }), to: '/learn/daily' }}
          />
        ) : (
          <div className="space-y-4">
            {dailyHistory.map((entry) => (
              <DailyHistoryCard
                key={entry.date}
                entry={entry}
                details={historyDetails[entry.date]}
                loadingDetails={loadingHistoryDetails === entry.date}
                isOpen={openHistoryDate === entry.date}
                onToggle={() => void toggleHistoryDate(entry.date)}
                t={t}
              />
            ))}
          </div>
        )
      ) : activeTab === 'favourites' ? (
        loadingFavourites ? (
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
        ) : favouriteWords.length === 0 ? (
          <EmptyState
            illustration="empty-vocab"
            title={t('empty.favourites.title', { defaultValue: 'No favourite words yet' })}
            description={t('empty.favourites.description', {
              defaultValue: 'Tap the heart on daily words or vocab rows to collect them here.',
            })}
            primaryAction={{ label: t('empty.favourites.cta', { defaultValue: 'View daily words' }), to: '/learn/daily' }}
          />
        ) : (
          <div className="space-y-1.5">
            {favouriteWords.map((word) => (
              <FavouriteWordRow key={word.id} word={word} />
            ))}
          </div>
        )
      ) : loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-surface-raised p-4 animate-pulse"
            >
              <div className="h-4 bg-border rounded w-1/2" />
              <div className="h-2 bg-border rounded mt-4 w-full" />
            </div>
          ))}
        </div>
      ) : preferredSlugs.length > 0 ? (
        <div className="space-y-8">
          <section>
            <div className="flex items-baseline gap-2 mb-3">
              <h2 className="text-base font-semibold text-fg">{t('byTopic.yourTopics')}</h2>
              <p className="text-xs text-muted-fg">{t('byTopic.yourTopicsSubtitle')}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {preferredTopics.map((tp) =>
                tp.word_count === 0 ? (
                  <Link
                    key={tp.id}
                    to={`/learn/vocab/topic/${encodeURIComponent(tp.id)}`}
                    className="block rounded-xl border border-dashed border-primary/40 bg-primary/5 p-4 transition-colors hover:border-primary/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <p className="font-semibold text-primary truncate">
                      {topicLabel(tp.id, tp.name, t)}
                    </p>
                    <p className="text-xs text-primary/60 mt-2">{t('byTopic.noWordsYet')}</p>
                    <div className="mt-3 h-1.5 bg-primary/10 rounded-full" />
                  </Link>
                ) : (
                  <TopicCard key={tp.id} topic={tp} t={t} />
                )
              )}
            </div>
          </section>

          {otherTopics.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-fg mb-3">{t('byTopic.otherTopics')}</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {otherTopics.map((tp) => (
                  <TopicCard key={tp.id} topic={tp} t={t} />
                ))}
              </div>
            </section>
          )}
        </div>
      ) : orderedTopics.length === 0 ? (
        <EmptyState
          illustration="empty-vocab"
          title={t('empty.noWords.title')}
          description={t('empty.noWords.description')}
          primaryAction={{ label: t('empty.noWords.cta'), to: '/review' }}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {orderedTopics.map((tp) => (
            <TopicCard key={tp.id} topic={tp} t={t} />
          ))}
        </div>
      )}
    </div>
  )
}
