import { useCallback, useEffect, useState, type ReactElement } from 'react'
import { useTranslation } from 'react-i18next'
import Icon from './Icon'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import type { IconName } from './Icon'
import type { ListeningTip, ListeningTipsResponse, TipCategory } from '../lib/listening'

const CATEGORY_ICONS: Record<TipCategory, IconName> = {
  strategy: 'Lightbulb',
  vocabulary: 'BookOpen',
  pronunciation: 'Mic',
  exam_technique: 'ClipboardCheck',
  mindset: 'Heart',
}

const CATEGORY_COLORS: Record<TipCategory, string> = {
  strategy: 'bg-primary/10 text-primary border-primary/20',
  vocabulary: 'bg-accent/10 text-accent border-accent/20',
  pronunciation: 'bg-warning/10 text-warning border-warning/20',
  exam_technique: 'bg-success/10 text-success border-success/20',
  mindset: 'bg-danger/10 text-danger border-danger/20',
}

/** Renders a subset of markdown: **bold** and "- " bullet lines. */
function MarkdownBody({ text }: { text: string }) {
  const lines = text.split('\n')
  const bulletLines: string[] = []
  const blocks: ReactElement[] = []
  let key = 0

  function flushBullets() {
    if (bulletLines.length === 0) return
    blocks.push(
      <ul key={key++} className="list-disc list-inside space-y-0.5 text-sm text-fg/90">
        {bulletLines.map((b, i) => (
          <li key={i}><InlineText text={b} /></li>
        ))}
      </ul>,
    )
    bulletLines.length = 0
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('- ')) {
      bulletLines.push(trimmed.slice(2))
    } else {
      flushBullets()
      if (trimmed) {
        blocks.push(
          <p key={key++} className="text-sm text-fg/90">
            <InlineText text={trimmed} />
          </p>,
        )
      }
    }
  }
  flushBullets()

  return <div className="space-y-1.5">{blocks}</div>
}

function InlineText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith('**') && part.endsWith('**')
          ? <strong key={i}>{part.slice(2, -2)}</strong>
          : <span key={i}>{part}</span>,
      )}
    </>
  )
}

function SkeletonCard() {
  return (
    <div className="bg-surface-raised rounded-xl border border-border p-4 space-y-2 animate-pulse">
      <div className="flex items-center gap-2">
        <div className="w-5 h-5 rounded-full bg-border" />
        <div className="h-4 w-24 rounded bg-border" />
        <div className="h-5 w-16 rounded-full bg-border ml-auto" />
      </div>
      <div className="space-y-1.5">
        <div className="h-3 w-full rounded bg-border" />
        <div className="h-3 w-4/5 rounded bg-border" />
        <div className="h-3 w-3/5 rounded bg-border" />
      </div>
    </div>
  )
}

interface Props {
  locale: string
}

export default function ListeningTipsTab({ locale }: Props) {
  const { t } = useTranslation('listening')
  const [tips, setTips] = useState<ListeningTip[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTips = useCallback(async (fresh = false) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ locale })
      if (fresh) params.set('fresh', 'true')
      const res = await apiFetch<ListeningTipsResponse>(
        `/api/v1/listening/tips?${params}`,
      )
      setTips(res.tips)
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setLoading(false)
    }
  }, [locale])

  useEffect(() => { fetchTips() }, [fetchTips])

  return (
    <div className="space-y-3" aria-busy={loading}>
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-fg">{t('tips.subtitle')}</p>
        <button
          onClick={() => fetchTips(true)}
          disabled={loading}
          aria-label={t('tips.refreshAriaLabel')}
          className="text-sm text-primary hover:text-primary-hover font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {t('tips.refreshBtn')}
        </button>
      </div>

      {loading && (
        <ul role="list" className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <li key={i}><SkeletonCard /></li>)}
        </ul>
      )}

      {!loading && error && (
        <div className="bg-danger/10 border border-danger/30 rounded-xl p-4 text-center space-y-2">
          <p className="text-sm text-danger">{error}</p>
          <button
            onClick={() => fetchTips()}
            className="text-sm text-primary hover:text-primary-hover font-medium"
          >
            {t('tips.retryBtn')}
          </button>
        </div>
      )}

      {!loading && !error && tips && (
        <ul role="list" className="space-y-3">
          {tips.map((tip) => {
            const cat = (
              ['strategy', 'vocabulary', 'pronunciation', 'exam_technique', 'mindset'].includes(tip.category)
                ? tip.category
                : 'strategy'
            ) as TipCategory
            return (
              <li key={tip.id} className="bg-surface-raised rounded-xl border border-border p-4 space-y-2">
                <div className="flex items-start gap-2">
                  <Icon name={CATEGORY_ICONS[cat]} size="md" variant="primary" />
                  <h3 className="flex-1 font-semibold text-fg text-sm leading-snug">{tip.title}</h3>
                  <span
                    className={`shrink-0 text-[10px] font-semibold border rounded-full px-2 py-0.5 ${CATEGORY_COLORS[cat]}`}
                  >
                    {t(`tips.categories.${cat}`)}
                  </span>
                </div>
                <MarkdownBody text={tip.body} />
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
