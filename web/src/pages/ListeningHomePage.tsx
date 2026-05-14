import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import Icon from '../components/Icon'
import ListeningTipsTab from '../components/ListeningTipsTab'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import {
  EXERCISE_ICONS,
  ListeningExerciseView,
  ListeningHistoryItem,
  ListeningType,
} from '../lib/listening'

const TYPES: ListeningType[] = ['dictation', 'gap_fill', 'comprehension']
const TABS = ['practice', 'mock', 'tips'] as const
type Tab = (typeof TABS)[number]

interface UserProfile {
  target_band: number
}

export default function ListeningHomePage() {
  const { t, i18n } = useTranslation('listening')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab: Tab = (TABS.includes(searchParams.get('tab') as Tab)
    ? searchParams.get('tab')!
    : 'practice') as Tab

  const [starting, setStarting] = useState<ListeningType | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [band, setBand] = useState<number>(7.0)
  const [recent, setRecent] = useState<ListeningHistoryItem[]>([])

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => setBand(p.target_band))
      .catch(() => {})
    apiFetch<{ items: ListeningHistoryItem[] }>('/api/v1/listening/history')
      .then((r) => setRecent(r.items.slice(0, 3)))
      .catch(() => {})
  }, [])

  const start = async (exercise_type: ListeningType) => {
    if (starting) return
    setStarting(exercise_type)
    setError(null)
    try {
      const res = await apiFetch<ListeningExerciseView>(
        '/api/v1/listening/generate',
        { method: 'POST', body: JSON.stringify({ exercise_type }) },
      )
      navigate(`/listening/${res.id}`)
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setStarting(null)
    }
  }

  const submittedToday = recent.filter(
    (r) => r.submitted && r.created_at &&
      new Date(r.created_at).toDateString() === new Date().toDateString(),
  ).length

  const setTab = (tab: Tab) => setSearchParams({ tab }, { replace: true })

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-end">
        <Link
          to="/practice/listening/history"
          className="text-sm text-primary hover:text-primary-hover font-medium"
        >
          {t('historyLink')}
        </Link>
      </div>

      <div>
        <h1 className="text-2xl font-bold text-fg">{t('heading')}</h1>
        <p className="text-sm text-muted-fg mt-1">
          {t('subline', { band, done: submittedToday })}
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border" role="tablist">
        {TABS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => setTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-fg hover:text-fg'
            }`}
          >
            {t(`tabs.${tab}`)}
          </button>
        ))}
      </div>

      {/* Practice tab */}
      {activeTab === 'practice' && (
        <div className="space-y-3">
          {error && (
            <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-sm text-danger">
              {error}
            </div>
          )}

          <div className="space-y-3">
            {TYPES.map((type) => (
              <button
                key={type}
                onClick={() => start(type)}
                disabled={!!starting}
                className="w-full text-left bg-surface-raised rounded-xl border border-border hover:border-primary/40 hover:shadow-sm p-4 flex items-center gap-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Icon name={EXERCISE_ICONS[type]} size="xl" variant="primary" />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-fg">{t(`types.${type}.title`)}</p>
                    <span className="text-[10px] font-semibold text-primary bg-primary/10 border border-primary/20 rounded-full px-2 py-0.5">
                      {t('exercise.band', { band })}
                    </span>
                  </div>
                  <p className="text-sm text-muted-fg">{t(`types.${type}.hint`)}</p>
                  <p className="text-xs text-muted-fg mt-0.5 inline-flex items-center gap-1">
                    <Icon name="Clock" size="sm" variant="muted" /> {t(`types.${type}.duration`)}
                  </p>
                </div>
                <span className="text-sm text-primary">
                  {starting === type ? t('generatingBtn') : t('startBtn')}
                </span>
              </button>
            ))}
          </div>

          {recent.length > 0 && (
            <div className="pt-4">
              <h2 className="text-sm font-semibold text-fg mb-2">{t('recentHeading')}</h2>
              <div className="space-y-2">
                {recent.map((it) => (
                  <Link
                    key={it.id}
                    to={`/practice/listening/${it.id}`}
                    className="flex items-center gap-3 bg-surface-raised rounded-lg border border-border hover:border-primary/40 p-2.5 text-sm"
                  >
                    <Icon name={EXERCISE_ICONS[it.exercise_type]} size="md" variant="primary" />
                    <span className="flex-1 text-fg truncate">{it.title}</span>
                    <span
                      className={`text-xs font-semibold ${
                        it.submitted ? 'text-primary' : 'text-muted-fg'
                      }`}
                    >
                      {it.submitted ? `${Math.round((it.score ?? 0) * 100)}%` : '—'}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Mock tab — placeholder for M15.1 */}
      {activeTab === 'mock' && (
        <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
          <Icon name="Hourglass" size="xl" variant="muted" />
          <p className="text-muted-fg text-sm">{t('tabs.mockComingSoon')}</p>
        </div>
      )}

      {/* Tips tab */}
      {activeTab === 'tips' && (
        <ListeningTipsTab locale={i18n.language.startsWith('vi') ? 'vi' : 'en'} />
      )}
    </div>
  )
}
