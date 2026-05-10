import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import Icon from '../../components/Icon'

type Strength = 'New' | 'Weak' | 'Learning' | 'Good' | 'Mastered'

type WordItem = {
  id: string
  word: string
  added_at: string | null
  // The /api/v1/vocabulary endpoint returns the full VocabularyWord
  // shape (api/models/vocabulary.py). Round 1 of this widget read a
  // non-existent ``meaning_vi`` field and never rendered any meaning;
  // the correct field is ``definition_vi``.
  definition_vi: string
  topic: string
  strength: Strength
}

type WordListResponse = {
  items: WordItem[]
  next_cursor: string | null
}

const STRENGTH_TONE: Record<Strength, string> = {
  New: 'bg-muted-fg/10 text-muted-fg',
  Weak: 'bg-danger/10 text-danger',
  Learning: 'bg-warning/10 text-warning',
  Good: 'bg-primary/10 text-primary',
  Mastered: 'bg-success/10 text-success',
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('vi-VN', { day: 'numeric', month: 'short' })
}

export default function RecentContent() {
  const { t } = useTranslation(['dashboard', 'vocab'])
  const [items, setItems] = useState<WordItem[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch<WordListResponse>('/api/v1/vocabulary?limit=3')
      .then((r) => setItems(r.items))
      .catch(() => {
        setError(true)
        setItems([])
      })
  }, [])

  if (items === null) return null

  return (
    <section aria-labelledby="recent-content-heading">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 id="recent-content-heading" className="font-semibold text-fg">
          {t('dashboard:recentContent.heading')}
        </h2>
        <Link
          to="/learn/vocab"
          className="text-sm text-primary hover:text-primary-hover focus-visible:outline-none focus-visible:underline"
        >
          {t('dashboard:recentContent.viewAll')} →
        </Link>
      </div>

      {items.length === 0 ? (
        <div className="rounded-2xl border border-border bg-surface-raised p-6 text-center">
          <p className="text-sm text-fg font-medium">
            {error
              ? t('dashboard:recentContent.errorTitle')
              : t('dashboard:recentContent.emptyTitle')}
          </p>
          <p className="mt-1 text-xs text-muted-fg">
            {error
              ? t('dashboard:recentContent.errorBody')
              : t('dashboard:recentContent.emptyBody')}
          </p>
          <Link
            to="/learn/daily"
            className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-fg hover:bg-primary-hover"
          >
            {t('dashboard:recentContent.emptyCta')}
          </Link>
        </div>
      ) : (
        <ul className="rounded-2xl border border-border bg-surface-raised divide-y divide-border overflow-hidden">
          {items.map((w) => (
            <li key={w.id}>
              <Link
                // /learn/vocab/:id is keyed on the word string (matches
                // VocabTopicPage), not the per-user vocab UUID. Passing a
                // UUID here used to make WordDetailPage feed the UUID
                // straight into AI enrichment as if it were a word —
                // the AI then returned cached gibberish so every recent
                // word rendered as the same arbitrary entry.
                to={`/learn/vocab/${encodeURIComponent(w.word)}`}
                className="flex items-center gap-3 p-4 transition-colors hover:bg-surface focus-visible:bg-surface focus-visible:outline-none"
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon name="BookOpen" size="md" variant="primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate font-medium text-fg">{w.word}</p>
                    <span
                      className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STRENGTH_TONE[w.strength] ?? STRENGTH_TONE.New}`}
                    >
                      {t(`vocab:strength.${w.strength}`, {
                        defaultValue: w.strength,
                      })}
                    </span>
                  </div>
                  {w.definition_vi ? (
                    <p className="truncate text-sm text-muted-fg">
                      {w.definition_vi}
                    </p>
                  ) : null}
                  {w.topic ? (
                    <p className="mt-0.5 truncate text-xs text-muted-fg">
                      {t(`vocab:topicNames.${w.topic}`, { defaultValue: w.topic })}
                    </p>
                  ) : null}
                </div>
                <div className="shrink-0 text-xs text-muted-fg">
                  {formatDate(w.added_at)}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
