import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
import Pagination from '../components/Pagination'
import PronunciationButton from '../components/PronunciationButton'
import { apiStream } from '../lib/api'
import { localizeError } from '../lib/apiError'

interface DailyWord {
  word: string
  word_id?: string
  definition_en: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  example_en: string
  example_vi: string
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

export default function DailyWordsPage() {
  const { t } = useTranslation('vocab')
  const [words, setWords] = useState<DailyWord[]>([])
  const [topic, setTopic] = useState('')
  const [expectedCount, setExpectedCount] = useState(0)
  const [streaming, setStreaming] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  useEffect(() => {
    const controller = new AbortController()

    async function streamWords() {
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
              } else if (event.type === 'word') {
                setWords((prev) => [...prev, event.word])
              } else if (event.type === 'done') {
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
  }, [t])

  const totalSlots = streaming && expectedCount > 0 ? expectedCount : words.length
  const totalPages = useMemo(() => Math.ceil(totalSlots / PAGE_SIZE) || 1, [totalSlots])

  const pageStart = (page - 1) * PAGE_SIZE
  const pageEnd = Math.min(pageStart + PAGE_SIZE, totalSlots)
  const pageWords = words.slice(pageStart, Math.min(pageEnd, words.length))
  const skeletonCount = Math.max(0, pageEnd - Math.max(pageStart, words.length))
  const startNumber = pageStart + 1
  const lastNumber = Math.min(pageStart + pageWords.length, words.length)

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
                defaultValue: 'Generating… {{count}} / {{total}}',
                count: words.length,
                total: expectedCount || '…',
              })
            : `${t('daily.pageOf', { current: page, total: totalPages })} · ${t('daily.wordRange', { first: startNumber, last: lastNumber, total: words.length })}`}
        </p>
      </header>

      <div className="space-y-3">
        {pageWords.map((item, i) => (
          <DailyWordCard key={`${item.word}-${i}`} item={item} index={startNumber + i} />
        ))}
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <WordSkeleton key={`sk-${i}`} />
        ))}
      </div>

      {!streaming && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPrev={() => setPage((p) => Math.max(1, p - 1))}
          onNext={() => setPage((p) => Math.min(totalPages, p + 1))}
        />
      )}

      {!streaming && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <Link
              to="/learn/daily/flip"
              className="p-4 min-h-[56px] rounded-xl border-2 border-border bg-surface-raised text-fg text-center font-medium hover:border-primary hover:bg-primary/5 transition-colors"
            >
              📖 {t('daily.openFlip')}
            </Link>
            <Link
              to="/learn/daily/quiz"
              className="p-4 min-h-[56px] rounded-xl border-2 border-border bg-surface-raised text-fg text-center font-medium hover:border-primary hover:bg-primary/5 transition-colors"
            >
              ✏️ {t('daily.openQuiz')}
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
