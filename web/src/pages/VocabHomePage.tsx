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
import EmptyState from '../components/EmptyState'
import { useProfile } from '../contexts/AuthContext'

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

export default function VocabHomePage() {
  const { t } = useTranslation('vocab')
  const profile = useProfile()
  const showLinkPrompt = profile != null && profile.id.startsWith('web_')
  const [topics, setTopics] = useState<TopicSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    apiFetch<TopicsResponse>('/api/v1/topics')
      .then((res) => !cancelled && setTopics(res.items))
      .catch((e) => !cancelled && setError(localizeError(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const stats = useMemo(() => {
    const total = topics.reduce((sum, tp) => sum + tp.word_count, 0)
    const mastered = topics.reduce((sum, tp) => sum + tp.mastered_count, 0)
    return { total, mastered }
  }, [topics])

  // Topics with at least one word, sorted "least mastered first" so the
  // gap-closing work surfaces. Empty topics drop to the bottom (we
  // filter them out before render — `/learn/vocab` shows only what
  // the user actually has words in).
  const orderedTopics = useMemo(() => {
    return [...topics]
      .filter((tp) => tp.word_count > 0)
      .sort((a, b) => {
        const aPct = a.mastered_count / a.word_count
        const bPct = b.mastered_count / b.word_count
        if (aPct !== bPct) return aPct - bPct
        return topicLabel(a.id, a.name, t).localeCompare(
          topicLabel(b.id, b.name, t),
        )
      })
  }, [topics, t])

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

      {loading ? (
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
