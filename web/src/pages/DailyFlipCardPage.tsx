import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import EmptyState from '../components/EmptyState'
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

export default function DailyFlipCardPage() {
  const { t } = useTranslation('vocab')
  const [words, setWords] = useState<DailyWord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)

  useEffect(() => {
    let cancelled = false
    apiFetch<DailyWordsResponse>('/api/v1/vocabulary/daily', { method: 'POST' })
      .then((res) => !cancelled && setWords(res.words))
      .catch((e) => !cancelled && setError((e as Error).message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const reveal = useCallback(() => setRevealed(true), [])
  const prev = useCallback(() => {
    setIndex((i) => Math.max(0, i - 1))
    setRevealed(false)
  }, [])
  const next = useCallback(() => {
    setIndex((i) => Math.min(words.length - 1, i + 1))
    setRevealed(false)
  }, [words.length])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === ' ') {
        e.preventDefault()
        if (!revealed) reveal()
        else next()
      } else if (e.key === 'ArrowRight') {
        next()
      } else if (e.key === 'ArrowLeft') {
        prev()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [revealed, reveal, next, prev])

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

  if (words.length === 0) {
    return (
      <div className="max-w-lg mx-auto p-4">
        <EmptyState
          illustration="empty-vocab"
          title={t('daily.empty.title')}
          description={t('daily.empty.description')}
          primaryAction={{ label: t('daily.empty.cta'), to: '/daily' }}
        />
      </div>
    )
  }

  const total = words.length
  const current = words[index]
  const isLast = index === total - 1

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/daily" className="text-sm text-muted-fg hover:text-fg">
          {t('review.exit')}
        </Link>
        <span className="text-sm text-muted-fg tabular-nums">
          {t('daily.pageOf', { current: index + 1, total })}
        </span>
      </div>

      <div className="bg-surface-raised rounded-xl shadow-sm p-6 text-center space-y-4 min-h-[360px] flex flex-col justify-center">
        <div className="space-y-1">
          <div className="flex items-center justify-center gap-2">
            <h2 className="text-4xl font-bold text-fg">{current.word}</h2>
            <PronunciationButton word={current.word} compact />
          </div>
          {current.ipa && (
            <p className="text-sm text-muted-fg">/{current.ipa}/</p>
          )}
          {current.part_of_speech && (
            <p className="text-xs uppercase tracking-wide text-muted-fg">
              {current.part_of_speech}
            </p>
          )}
        </div>

        {!revealed ? (
          <button
            onClick={reveal}
            className="w-full py-3 min-h-[44px] bg-primary text-primary-fg rounded-xl font-medium hover:bg-primary-hover"
          >
            👁️ {t('review.flip.reveal')}{' '}
            <span className="text-xs opacity-75">(Space)</span>
          </button>
        ) : (
          <div className="text-left space-y-2 border-t border-border pt-4">
            {current.definition_en && (
              <p className="text-fg">{current.definition_en}</p>
            )}
            {current.definition_vi && (
              <p className="text-muted-fg text-sm">{current.definition_vi}</p>
            )}
            {current.example_en && (
              <p className="text-sm text-fg italic pt-2">
                "{current.example_en}"
              </p>
            )}
            {current.example_vi && (
              <p className="text-xs text-muted-fg italic">
                "{current.example_vi}"
              </p>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <button
          onClick={prev}
          disabled={index === 0}
          className="py-3 min-h-[44px] rounded-xl border-2 border-border bg-surface-raised text-fg font-medium hover:border-primary disabled:opacity-40 transition-colors"
        >
          ◀ {t('pagination.prev')}
        </button>
        {isLast ? (
          <Link
            to="/daily"
            className="py-3 min-h-[44px] rounded-xl bg-primary text-primary-fg font-medium hover:bg-primary-hover text-center flex items-center justify-center"
          >
            ✅ {t('daily.flip.done')}
          </Link>
        ) : (
          <button
            onClick={reveal}
            disabled={revealed}
            className="py-3 min-h-[44px] rounded-xl border-2 border-border bg-surface-raised text-fg font-medium hover:border-primary disabled:opacity-40 transition-colors"
          >
            👁️
          </button>
        )}
        <button
          onClick={next}
          disabled={isLast}
          className="py-3 min-h-[44px] rounded-xl border-2 border-border bg-surface-raised text-fg font-medium hover:border-primary disabled:opacity-40 transition-colors"
        >
          {t('pagination.next')} ▶
        </button>
      </div>
    </div>
  )
}
