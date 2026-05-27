import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Icon, { type IconName } from '../components/Icon'
import LoadingScreen from '../components/LoadingScreen'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'

interface TopicSummary {
  id: string
  name: string
  word_count: number
  mastered_count: number
}

interface TopicsResponse {
  items: TopicSummary[]
  total_words: number
}

interface DueResponse {
  items: unknown[]
}

function HubAction({
  title,
  description,
  meta,
  to,
  icon,
  primary = false,
  eventName,
}: {
  title: string
  description: string
  meta: string
  to: string
  icon: IconName
  primary?: boolean
  eventName: string
}) {
  return (
    <Link
      to={to}
      onClick={() => track(eventName)}
      className={`flex min-h-36 flex-col justify-between rounded-xl border p-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
        primary
          ? 'border-primary/40 bg-primary/10 hover:border-primary/70'
          : 'border-border bg-surface-raised hover:border-primary/40'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className={`rounded-lg p-2 ${primary ? 'bg-primary text-on-primary' : 'bg-surface text-primary'}`}>
          <Icon name={icon} size="md" variant={primary ? 'fg' : 'primary'} />
        </div>
        <Icon name="ArrowRight" size="sm" variant="muted" />
      </div>
      <div className="mt-5">
        <p className="text-sm font-medium text-muted-fg">{meta}</p>
        <h2 className="mt-1 text-lg font-semibold text-fg">{title}</h2>
        <p className="mt-1 text-sm text-muted-fg">{description}</p>
      </div>
    </Link>
  )
}

export default function VocabHubPage() {
  const { t } = useTranslation('vocab')
  const [topics, setTopics] = useState<TopicSummary[]>([])
  const [dueCount, setDueCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const [topicRes, dueRes] = await Promise.all([
          apiFetch<TopicsResponse>('/api/v1/topics'),
          apiFetch<DueResponse>('/api/v1/review/due', {
            method: 'POST',
            body: JSON.stringify({ limit: 10 }),
          }),
        ])
        if (cancelled) return
        setTopics(topicRes.items)
        setDueCount(dueRes.items.length)
      } catch (e) {
        if (!cancelled) setError(localizeError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  const stats = useMemo(() => {
    const total = topics.reduce((sum, topic) => sum + topic.word_count, 0)
    const mastered = topics.reduce((sum, topic) => sum + topic.mastered_count, 0)
    const weakTopic = [...topics]
      .filter((topic) => topic.word_count > 0)
      .sort((a, b) => {
        const aPct = a.mastered_count / a.word_count
        const bPct = b.mastered_count / b.word_count
        return aPct - bPct
      })[0]
    return { total, mastered, weakTopic }
  }, [topics])

  if (loading) {
    return <LoadingScreen className="mx-auto max-w-5xl p-4" />
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-4">
        <EmptyState
          illustration="empty-vocab"
          title={t('hub.error.title')}
          description={error}
          primaryAction={{ label: t('hub.error.cta'), onClick: () => window.location.reload() }}
        />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-5xl p-4">
      <header className="mb-6">
        <p className="text-sm font-medium text-primary">{t('hub.eyebrow')}</p>
        <h1 className="mt-1 text-2xl font-bold text-fg md:text-3xl">
          {t('hub.heading')}
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-fg">
          {t('hub.subtitle')}
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <HubAction
          primary
          icon="Calendar"
          to="/learn/daily"
          eventName="vocab_hub_daily_opened"
          meta={t('hub.today.meta')}
          title={t('hub.today.title')}
          description={t('hub.today.description')}
        />
        <HubAction
          icon="RotateCcw"
          to="/learn/review"
          eventName="vocab_hub_review_opened"
          meta={
            dueCount === null
              ? t('hub.review.metaUnknown')
              : t('hub.review.meta', { count: dueCount })
          }
          title={t('hub.review.title')}
          description={t('hub.review.description')}
        />
        <HubAction
          icon="BookOpen"
          to="/learn/vocab/my-words"
          eventName="vocab_hub_my_words_opened"
          meta={t('hub.myWords.meta', {
            total: stats.total,
            mastered: stats.mastered,
          })}
          title={t('hub.myWords.title')}
          description={t('hub.myWords.description')}
        />
        <HubAction
          icon="Target"
          to="/learn/vocab/explore"
          eventName="vocab_hub_explore_opened"
          meta={
            stats.weakTopic
              ? t('hub.explore.metaTopic', {
                  topic: t(`topicNames.${stats.weakTopic.id}`, {
                    defaultValue: stats.weakTopic.name,
                  }),
                })
              : t('hub.explore.meta')
          }
          title={t('hub.explore.title')}
          description={t('hub.explore.description')}
        />
        <HubAction
          icon="Plus"
          to="/learn/vocab/add"
          eventName="vocab_hub_add_opened"
          meta={t('hub.add.meta')}
          title={t('hub.add.title')}
          description={t('hub.add.description')}
        />
      </div>
    </div>
  )
}
