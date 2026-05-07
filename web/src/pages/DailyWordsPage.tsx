import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Pagination from '../components/Pagination'
import PronunciationButton from '../components/PronunciationButton'
import { apiFetch } from '../lib/api'

interface DailyWord {
  word: string
  definition_en: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  example_en: string
  example_vi: string
}

interface DailyWordsResponse {
  date: string
  topic: string
  words: DailyWord[]
  generated_at: string | null
}

const PAGE_SIZE = 5

function topicLabel(
  slug: string,
  t: (k: string, o?: Record<string, unknown>) => string,
): string {
  if (!slug) return ''
  return t(`topicNames.${slug}`, { defaultValue: slug })
}

function DailyWordCard({ item, index }: { item: DailyWord; index: number }) {
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
          </div>
          {item.ipa && <p className="text-xs text-muted-fg mt-1">/{item.ipa}/</p>}
        </div>
        <PronunciationButton word={item.word} compact />
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
    </article>
  )
}

export default function DailyWordsPage() {
  const { t } = useTranslation('vocab')
  const [data, setData] = useState<DailyWordsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    apiFetch<DailyWordsResponse>('/api/v1/vocabulary/daily', { method: 'POST' })
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e) => !cancelled && setError((e as Error).message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const totalPages = useMemo(() => {
    if (!data || data.words.length === 0) return 0
    return Math.ceil(data.words.length / PAGE_SIZE)
  }, [data])

  const pageItems = useMemo(() => {
    if (!data) return []
    const start = (page - 1) * PAGE_SIZE
    return data.words.slice(start, start + PAGE_SIZE)
  }, [data, page])

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-4 text-center text-muted-fg">
        {t('daily.loading')}
      </div>
    )
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

  if (!data || data.words.length === 0) {
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

  const startNumber = (page - 1) * PAGE_SIZE + 1
  const firstNum = startNumber
  const lastNum = Math.min(startNumber + pageItems.length - 1, data.words.length)

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-fg">{t('daily.heading')}</h1>
        <p className="text-sm text-muted-fg">
          {data.topic && <span>{topicLabel(data.topic, t)} · </span>}
          {t('daily.pageOf', { current: page, total: totalPages })} ·{' '}
          {t('daily.wordRange', {
            first: firstNum,
            last: lastNum,
            total: data.words.length,
          })}
        </p>
      </header>

      <div className="space-y-3">
        {pageItems.map((item, i) => (
          <DailyWordCard key={`${item.word}-${i}`} item={item} index={startNumber + i} />
        ))}
      </div>

      <Pagination
        page={page}
        totalPages={totalPages}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => Math.min(totalPages, p + 1))}
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
        <Link
          to="/daily/flip"
          className="p-4 min-h-[56px] rounded-xl border-2 border-border bg-surface-raised text-fg text-center font-medium hover:border-primary hover:bg-primary/5 transition-colors"
        >
          📖 {t('daily.openFlip')}
        </Link>
        <Link
          to="/daily/quiz"
          className="p-4 min-h-[56px] rounded-xl border-2 border-border bg-surface-raised text-fg text-center font-medium hover:border-primary hover:bg-primary/5 transition-colors"
        >
          ✏️ {t('daily.openQuiz')}
        </Link>
      </div>
    </div>
  )
}
