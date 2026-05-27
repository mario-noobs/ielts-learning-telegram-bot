import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Icon from '../components/Icon'
import LoadingScreen from '../components/LoadingScreen'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'

interface PublicPool {
  id: string
  title: string
  source: string
  source_theme: string
  word_count: number
  difficulty: number | null
  difficulty_min: number | null
  difficulty_max: number | null
  topics: string[]
  source_url: string
  license: string
  provenance: string
}

interface PublicPoolWord {
  id: string
  word: string
  definition_en: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  difficulty: number | null
  topic: string
  source_ref: string
}

interface PublicPoolsResponse {
  enabled: boolean
  items: PublicPool[]
}

interface PublicPoolDetailResponse {
  enabled: boolean
  pool: PublicPool
  words: PublicPoolWord[]
}

const DIFFICULTIES = [1, 2, 3, 4, 5]

function difficultyLabel(value: number | null, t: (key: string, opts?: Record<string, unknown>) => string) {
  return value ? t('publicPools.difficultyValue', { value }) : t('publicPools.difficultyUnknown')
}

export default function PublicVocabPoolsPage() {
  const { t } = useTranslation('vocab')
  const { poolId } = useParams<{ poolId?: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const difficulty = searchParams.get('difficulty') || ''
  const topic = searchParams.get('topic') || ''
  const [pools, setPools] = useState<PublicPool[] | null>(null)
  const [detail, setDetail] = useState<PublicPoolDetailResponse | null>(null)
  const [enabled, setEnabled] = useState(true)
  const [error, setError] = useState('')

  const query = useMemo(() => {
    const params = new URLSearchParams()
    if (difficulty) params.set('difficulty', difficulty)
    if (topic) params.set('topic', topic)
    const raw = params.toString()
    return raw ? `?${raw}` : ''
  }, [difficulty, topic])

  useEffect(() => {
    let cancelled = false
    setError('')
    if (poolId) {
      setDetail(null)
      apiFetch<PublicPoolDetailResponse>(`/api/v1/vocabulary/public-pools/${encodeURIComponent(poolId)}${query}`)
        .then((res) => {
          if (cancelled) return
          setEnabled(res.enabled)
          setDetail(res)
          track('public_vocab_pool_detail_opened', { pool_id: poolId })
        })
        .catch((e) => !cancelled && setError(localizeError(e)))
    } else {
      setPools(null)
      apiFetch<PublicPoolsResponse>(`/api/v1/vocabulary/public-pools${query}`)
        .then((res) => {
          if (cancelled) return
          setEnabled(res.enabled)
          setPools(res.items)
          track('public_vocab_pools_opened')
        })
        .catch((e) => !cancelled && setError(localizeError(e)))
    }
    return () => {
      cancelled = true
    }
  }, [poolId, query])

  const topicOptions = useMemo(() => {
    const source = detail ? [detail.pool] : pools ?? []
    return Array.from(new Set(source.flatMap((pool) => pool.topics))).sort()
  }, [detail, pools])

  const setFilter = (key: 'difficulty' | 'topic', value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next)
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-4">
        <EmptyState
          illustration="empty-vocab"
          title={t('publicPools.error.title')}
          description={error}
          primaryAction={{ label: t('publicPools.error.cta'), to: '/learn/vocab' }}
        />
      </div>
    )
  }

  if (!enabled) {
    return (
      <div className="mx-auto max-w-3xl p-4">
        <EmptyState
          illustration="empty-vocab"
          title={t('publicPools.disabled.title')}
          description={t('publicPools.disabled.description')}
          primaryAction={{ label: t('publicPools.disabled.cta'), to: '/learn/vocab' }}
        />
      </div>
    )
  }

  if ((!poolId && pools === null) || (poolId && detail === null)) {
    return <LoadingScreen className="mx-auto max-w-5xl p-4" />
  }

  return (
    <div className="mx-auto max-w-5xl p-4">
      <header className="mb-5">
        <Link to="/learn/vocab" className="text-sm text-muted-fg hover:text-fg">
          {t('publicPools.back')}
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-fg">{t('publicPools.heading')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-fg">{t('publicPools.subtitle')}</p>
      </header>

      <div className="mb-5 flex flex-col gap-3 rounded-xl border border-border bg-surface-raised p-4 sm:flex-row sm:items-end">
        <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-muted-fg">
          {t('publicPools.filters.difficulty')}
          <select
            value={difficulty}
            onChange={(e) => setFilter('difficulty', e.target.value)}
            className="rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg"
          >
            <option value="">{t('publicPools.filters.allDifficulties')}</option>
            {DIFFICULTIES.map((value) => (
              <option key={value} value={value}>
                {difficultyLabel(value, t)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-muted-fg">
          {t('publicPools.filters.topic')}
          <select
            value={topic}
            onChange={(e) => setFilter('topic', e.target.value)}
            className="rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg"
          >
            <option value="">{t('publicPools.filters.allTopics')}</option>
            {topicOptions.map((slug) => (
              <option key={slug} value={slug}>
                {t(`topicNames.${slug}`, { defaultValue: slug })}
              </option>
            ))}
          </select>
        </label>
      </div>

      {detail ? (
        <PoolDetail detail={detail} t={t} />
      ) : pools && pools.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {pools.map((pool) => (
            <PoolCard key={pool.id} pool={pool} t={t} />
          ))}
        </div>
      ) : (
        <EmptyState
          illustration="empty-vocab"
          title={t('publicPools.empty.title')}
          description={t('publicPools.empty.description')}
        />
      )}
    </div>
  )
}

function PoolCard({
  pool,
  t,
}: {
  pool: PublicPool
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  return (
    <Link
      to={`/learn/vocab/pools/${encodeURIComponent(pool.id)}`}
      className="flex min-h-52 flex-col justify-between rounded-xl border border-border bg-surface-raised p-4 transition-colors hover:border-primary/40"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="rounded-lg bg-primary/10 p-2">
          <Icon name="BookOpen" size="md" variant="primary" />
        </div>
        <span className="rounded-md bg-surface px-2 py-1 text-xs text-muted-fg">
          {difficultyLabel(pool.difficulty, t)}
        </span>
      </div>
      <div className="mt-5">
        <h2 className="text-base font-semibold text-fg">{pool.title}</h2>
        <p className="mt-1 text-sm text-muted-fg">
          {t('publicPools.card.wordCount', { count: pool.word_count })}
        </p>
        <p className="mt-3 text-xs text-muted-fg">
          {t('publicPools.card.source', { source: pool.source })}
        </p>
        <p className="mt-1 truncate text-xs text-muted-fg">
          {pool.license || t('publicPools.card.noLicense')}
        </p>
      </div>
    </Link>
  )
}

function PoolDetail({
  detail,
  t,
}: {
  detail: PublicPoolDetailResponse
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border bg-surface-raised p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-fg">{detail.pool.title}</h2>
            <p className="mt-1 text-sm text-muted-fg">
              {t('publicPools.card.wordCount', { count: detail.pool.word_count })} ·{' '}
              {difficultyLabel(detail.pool.difficulty, t)}
            </p>
          </div>
          {detail.pool.source_url && (
            <a
              href={detail.pool.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-medium text-primary hover:text-primary-hover"
            >
              {t('publicPools.detail.sourceLink')}
            </a>
          )}
        </div>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-muted-fg">{t('publicPools.detail.source')}</dt>
            <dd className="font-medium text-fg">{detail.pool.source}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-fg">{t('publicPools.detail.license')}</dt>
            <dd className="font-medium text-fg">{detail.pool.license || t('publicPools.card.noLicense')}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-fg">{t('publicPools.detail.provenance')}</dt>
            <dd className="font-medium text-fg">{detail.pool.provenance}</dd>
          </div>
        </dl>
      </section>

      <div className="divide-y divide-border rounded-xl border border-border bg-surface-raised">
        {detail.words.map((word) => (
          <div key={word.id} className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="font-semibold text-fg">{word.word}</h3>
                <p className="text-xs text-muted-fg">
                  {word.part_of_speech}
                  {word.ipa ? ` · /${word.ipa}/` : ''}
                </p>
              </div>
              <span className="rounded-md bg-surface px-2 py-1 text-xs text-muted-fg">
                {difficultyLabel(word.difficulty, t)}
              </span>
            </div>
            <p className="mt-2 text-sm text-fg">{word.definition_en}</p>
            {word.definition_vi && <p className="mt-1 text-sm text-muted-fg">{word.definition_vi}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
