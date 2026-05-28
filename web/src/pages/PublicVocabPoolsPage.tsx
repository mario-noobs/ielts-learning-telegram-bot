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
  example_en: string
  example_vi: string
  difficulty: number | null
  topic: string
  source_ref: string
  already_saved: boolean
  existing_word_id: string | null
}

interface PublicPoolsResponse {
  enabled: boolean
  items: PublicPool[]
}

interface RecommendationReason {
  code: string
  topic?: string | null
}

interface PublicPoolRecommendation extends PublicPool {
  reasons: RecommendationReason[]
}

interface PublicPoolRecommendationsResponse {
  enabled: boolean
  target_difficulty: number | null
  items: PublicPoolRecommendation[]
}

interface PublicPoolDetailResponse {
  enabled: boolean
  pool: PublicPool
  words: PublicPoolWord[]
}

interface PublicPoolSaveResponse {
  created: boolean
  already_saved: boolean
  word: {
    id: string
    word: string
  }
}

interface VocabConsultDataPoint {
  label: string
  value: string
}

interface VocabConsultMissingRequirement {
  code: string
  current: number
  required: number
  route: string
}

interface VocabConsultItem {
  title: string
  detail: string
  evidence: string
}

interface VocabConsultAction {
  title: string
  detail: string
  route: string | null
  priority: 'high' | 'medium' | 'low'
}

interface VocabRoadmapConsultResponse {
  status: 'ready' | 'insufficient_data'
  disclaimer: string
  confidence: 'low' | 'medium' | 'high'
  readiness_range: string
  summary: string
  data_used: VocabConsultDataPoint[]
  missing_requirements: VocabConsultMissingRequirement[]
  strengths: VocabConsultItem[]
  gaps: VocabConsultItem[]
  next_actions: VocabConsultAction[]
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
  const [recommendations, setRecommendations] = useState<PublicPoolRecommendation[]>([])
  const [detail, setDetail] = useState<PublicPoolDetailResponse | null>(null)
  const [savingWordIds, setSavingWordIds] = useState<Set<string>>(() => new Set())
  const [enabled, setEnabled] = useState(true)
  const [error, setError] = useState('')
  const [consult, setConsult] = useState<VocabRoadmapConsultResponse | null>(null)
  const [consultLoading, setConsultLoading] = useState(false)
  const [consultError, setConsultError] = useState('')

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
      const recommendationsRequest = apiFetch<PublicPoolRecommendationsResponse>(
        '/api/v1/vocabulary/public-pools/recommendations',
      ).catch(() => ({ enabled: false, target_difficulty: null, items: [] }))
      Promise.all([
        apiFetch<PublicPoolsResponse>(`/api/v1/vocabulary/public-pools${query}`),
        recommendationsRequest,
      ])
        .then(([res, recs]) => {
          if (cancelled) return
          setEnabled(res.enabled)
          setPools(res.items)
          setRecommendations(recs.enabled ? recs.items : [])
          track('public_vocab_pools_opened')
          if (recs.enabled && recs.items.length > 0) {
            track('public_vocab_roadmap_recommendations_viewed', {
              count: recs.items.length,
              pool_ids: recs.items.map((pool) => pool.id),
            })
          }
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

  const saveWord = async (wordId: string) => {
    if (!poolId) return
    setSavingWordIds((prev) => new Set(prev).add(wordId))
    setError('')
    try {
      const res = await apiFetch<PublicPoolSaveResponse>(
        `/api/v1/vocabulary/public-pools/${encodeURIComponent(poolId)}/words/${encodeURIComponent(wordId)}/save`,
        { method: 'POST' },
      )
      setDetail((current) => {
        if (!current) return current
        return {
          ...current,
          words: current.words.map((word) =>
            word.id === wordId
              ? { ...word, already_saved: true, existing_word_id: res.word.id }
              : word,
          ),
        }
      })
      track('public_vocab_pool_word_saved', {
        pool_id: poolId,
        word_id: wordId,
        created: res.created,
        already_saved: res.already_saved,
      })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setSavingWordIds((prev) => {
        const next = new Set(prev)
        next.delete(wordId)
        return next
      })
    }
  }

  const requestConsult = async () => {
    setConsultLoading(true)
    setConsultError('')
    track('vocab_roadmap_consult_requested')
    try {
      const res = await apiFetch<VocabRoadmapConsultResponse>('/api/v1/vocabulary/roadmap/consult', {
        method: 'POST',
      })
      setConsult(res)
      track('vocab_roadmap_consult_completed', {
        status: res.status,
        confidence: res.confidence,
        action_count: res.next_actions.length,
      })
    } catch (e) {
      const message = localizeError(e)
      setConsultError(message)
      track('vocab_roadmap_consult_failed')
    } finally {
      setConsultLoading(false)
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-4">
        <EmptyState
          illustration="empty-vocab"
          title={t('publicPools.error.title')}
          description={error}
          primaryAction={{ label: t('publicPools.error.cta'), to: '/' }}
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
          primaryAction={{ label: t('publicPools.disabled.cta'), to: '/' }}
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
        {poolId && (
          <Link to="/learn/pools" className="text-sm text-muted-fg hover:text-fg">
            {t('publicPools.backToPools')}
          </Link>
        )}
        <h1 className="mt-2 text-2xl font-bold text-fg">{t('publicPools.heading')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-fg">{t('publicPools.subtitle')}</p>
      </header>

      {!detail && recommendations.length > 0 && (
        <RecommendationStrip recommendations={recommendations} t={t} />
      )}

      {!detail && (
        <RoadmapConsultPanel
          consult={consult}
          error={consultError}
          loading={consultLoading}
          onRequest={requestConsult}
          t={t}
        />
      )}

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
        <PoolDetail
          detail={detail}
          savingWordIds={savingWordIds}
          onSaveWord={saveWord}
          t={t}
        />
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

function reasonLabel(
  reason: RecommendationReason,
  t: (key: string, opts?: Record<string, unknown>) => string,
) {
  const topic = reason.topic
    ? t(`topicNames.${reason.topic}`, { defaultValue: reason.topic })
    : ''
  return t(`publicPools.recommendations.reasons.${reason.code}`, { topic })
}

function RecommendationStrip({
  recommendations,
  t,
}: {
  recommendations: PublicPoolRecommendation[]
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  return (
    <section className="mb-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-fg">
            {t('publicPools.recommendations.heading')}
          </h2>
          <p className="text-sm text-muted-fg">
            {t('publicPools.recommendations.subtitle')}
          </p>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {recommendations.map((pool) => (
          <Link
            key={pool.id}
            to={`/learn/pools/${encodeURIComponent(pool.id)}`}
            onClick={() => track('public_vocab_roadmap_recommendation_clicked', { pool_id: pool.id })}
            className="rounded-xl border border-primary/30 bg-primary/5 p-4 transition-colors hover:border-primary/60"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-primary">
                  {difficultyLabel(pool.difficulty, t)}
                </p>
                <h3 className="mt-1 text-base font-semibold text-fg">{pool.title}</h3>
              </div>
              <Icon name="ArrowRight" size="sm" variant="primary" />
            </div>
            <ul className="mt-3 space-y-1">
              {(pool.reasons || []).slice(0, 2).map((reason, index) => (
                <li key={`${reason.code}-${reason.topic || index}`} className="text-xs text-muted-fg">
                  {reasonLabel(reason, t)}
                </li>
              ))}
            </ul>
          </Link>
        ))}
      </div>
    </section>
  )
}

function RoadmapConsultPanel({
  consult,
  error,
  loading,
  onRequest,
  t,
}: {
  consult: VocabRoadmapConsultResponse | null
  error: string
  loading: boolean
  onRequest: () => void
  t: (key: string, opts?: Record<string, unknown>) => string
}) {
  return (
    <section className="mb-5 rounded-xl border border-border bg-surface-raised p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-fg">
            {t('publicPools.consult.heading')}
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-fg">
            {t('publicPools.consult.subtitle')}
          </p>
        </div>
        <button
          type="button"
          onClick={onRequest}
          disabled={loading}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary transition-colors hover:bg-primary/90 disabled:cursor-wait disabled:opacity-70"
        >
          {loading && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
          {loading ? t('publicPools.consult.loading') : t('publicPools.consult.cta')}
        </button>
      </div>

      {error && (
        <p className="mt-3 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {consult && (
        <div className="mt-4 space-y-4">
          <div className="rounded-lg border border-border bg-bg p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                {t(`publicPools.consult.confidence.${consult.confidence}`)}
              </span>
              {consult.readiness_range && (
                <span className="rounded-md bg-surface px-2 py-1 text-xs text-muted-fg">
                  {t('publicPools.consult.readiness', { range: consult.readiness_range })}
                </span>
              )}
            </div>
            <p className="mt-3 text-sm text-fg">{consult.summary}</p>
            <p className="mt-2 text-xs text-muted-fg">{consult.disclaimer}</p>
          </div>

          {consult.missing_requirements.length > 0 && (
            <div className="grid gap-2 sm:grid-cols-2">
              {consult.missing_requirements.map((item) => (
                <Link
                  key={item.code}
                  to={item.route}
                  className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm transition-colors hover:border-warning/60"
                >
                  <p className="font-medium text-fg">
                    {t(`publicPools.consult.requirements.${item.code}.title`)}
                  </p>
                  <p className="mt-1 text-muted-fg">
                    {t(`publicPools.consult.requirements.${item.code}.detail`, {
                      current: item.current,
                      required: item.required,
                    })}
                  </p>
                </Link>
              ))}
            </div>
          )}

          {(consult.strengths.length > 0 || consult.gaps.length > 0) && (
            <div className="grid gap-3 md:grid-cols-2">
              <ConsultList title={t('publicPools.consult.strengths')} items={consult.strengths} />
              <ConsultList title={t('publicPools.consult.gaps')} items={consult.gaps} />
            </div>
          )}

          {consult.next_actions.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-fg">{t('publicPools.consult.nextActions')}</h3>
              <div className="mt-2 grid gap-2">
                {consult.next_actions.map((action) => {
                  const body = (
                    <>
                      <div className="flex items-start justify-between gap-3">
                        <p className="font-medium text-fg">{action.title}</p>
                        <span className="rounded-md bg-surface px-2 py-1 text-xs text-muted-fg">
                          {t(`publicPools.consult.priority.${action.priority}`)}
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-muted-fg">{action.detail}</p>
                    </>
                  )
                  return action.route ? (
                    <Link
                      key={`${action.title}-${action.route}`}
                      to={action.route}
                      className="rounded-lg border border-border bg-bg p-3 transition-colors hover:border-primary/40"
                    >
                      {body}
                    </Link>
                  ) : (
                    <div key={action.title} className="rounded-lg border border-border bg-bg p-3">
                      {body}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          <div>
            <h3 className="text-sm font-semibold text-fg">{t('publicPools.consult.dataUsed')}</h3>
            <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
              {consult.data_used.map((item) => (
                <div key={item.label} className="rounded-lg bg-bg p-3">
                  <dt className="text-xs text-muted-fg">{item.label}</dt>
                  <dd className="mt-1 font-medium text-fg">{item.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}
    </section>
  )
}

function ConsultList({
  title,
  items,
}: {
  title: string
  items: VocabConsultItem[]
}) {
  return (
    <div className="rounded-lg border border-border bg-bg p-3">
      <h3 className="text-sm font-semibold text-fg">{title}</h3>
      <div className="mt-2 space-y-3">
        {items.map((item) => (
          <div key={item.title}>
            <p className="text-sm font-medium text-fg">{item.title}</p>
            <p className="mt-1 text-sm text-muted-fg">{item.detail}</p>
            {item.evidence && (
              <p className="mt-1 text-xs text-muted-fg">{item.evidence}</p>
            )}
          </div>
        ))}
      </div>
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
      to={`/learn/pools/${encodeURIComponent(pool.id)}`}
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
  savingWordIds,
  onSaveWord,
  t,
}: {
  detail: PublicPoolDetailResponse
  savingWordIds: Set<string>
  onSaveWord: (wordId: string) => void
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
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                disabled={word.already_saved || savingWordIds.has(word.id)}
                onClick={() => onSaveWord(word.id)}
                className={`inline-flex min-h-10 items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  word.already_saved
                    ? 'cursor-default bg-success/10 text-success'
                    : 'bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-60'
                }`}
              >
                {savingWordIds.has(word.id)
                  ? t('publicPools.word.saving')
                  : word.already_saved
                    ? t('publicPools.word.alreadySaved')
                    : t('publicPools.word.save')}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
