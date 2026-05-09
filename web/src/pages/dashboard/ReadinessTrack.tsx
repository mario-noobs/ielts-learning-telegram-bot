/**
 * Exam readiness track (US-#223).
 *
 * Replaces the old `<ReadinessStrip>` (4 floating skill cards) with a
 * single ordered narrative — what to do next, not just where you stand.
 * Driven by `GET /api/v1/readiness` which returns 4 fixed steps:
 *
 *   goal → daily_plan → skills → mock_test
 *
 * The 4 SkillBandCards still render — but nested inside Step 3 ("Build
 * skills"), where they conceptually belong. Active step auto-expands
 * on mount; clicking a different step closes the previous one.
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon, { IconName } from '../../components/Icon'
import { apiFetch } from '../../lib/api'
import { track } from '../../lib/analytics'
import type { ProgressResponse } from '../../lib/progress'
import { deltaFrom } from '../../lib/progress'
import SkillBandCard from '../../components/SkillBandCard'

type Status = 'done' | 'active' | 'upcoming' | 'locked'
type StepId = 'goal' | 'daily_plan' | 'skills' | 'mock_test'

interface SubTask {
  id: string
  label_key: string
  href: string
  done: boolean
}

interface Step {
  id: StepId
  status: Status
  title_key: string
  rationale_key: string
  rationale_params: Record<string, unknown>
  sub_tasks: SubTask[]
}

interface ReadinessResponse {
  pct_complete: number
  days_until_exam: number | null
  urgent: boolean
  target_band: number
  steps: Step[]
}

interface Props {
  progress: ProgressResponse | null
}

const STATUS_ICON: Record<Status, IconName> = {
  done: 'CheckCircle2',
  active: 'CircleDot',
  upcoming: 'Circle',
  locked: 'Lock',
}

const STATUS_TONE: Record<Status, string> = {
  done: 'text-success',
  active: 'text-primary',
  upcoming: 'text-muted-fg',
  locked: 'text-muted-fg',
}

type SkillKey = 'writing' | 'listening' | 'vocabulary' | 'reading'

const SKILLS: Array<{
  key: SkillKey
  labelKey: string
  iconName: 'PenLine' | 'Headphones' | 'BookOpen' | 'FileText'
  to: string
}> = [
  { key: 'writing', labelKey: 'common:skills.writing', iconName: 'PenLine', to: '/practice/writing' },
  { key: 'listening', labelKey: 'common:skills.listening', iconName: 'Headphones', to: '/practice/listening' },
  { key: 'vocabulary', labelKey: 'common:skills.vocabulary', iconName: 'BookOpen', to: '/learn/vocab' },
  { key: 'reading', labelKey: 'common:skills.reading', iconName: 'FileText', to: '/practice/reading' },
]

function StepRow({
  step,
  index,
  total,
  expanded,
  onToggle,
  progress,
  targetBand,
}: {
  step: Step
  index: number
  total: number
  expanded: boolean
  onToggle: () => void
  progress: ProgressResponse | null
  targetBand: number
}) {
  const { t } = useTranslation(['dashboard', 'common'])
  const isLocked = step.status === 'locked'
  const interactive = !isLocked

  return (
    <li className="border-t border-border first:border-t-0">
      <button
        type="button"
        onClick={interactive ? onToggle : undefined}
        aria-expanded={expanded}
        aria-disabled={isLocked || undefined}
        aria-label={t('readinessTrack.stepAria', {
          n: index + 1,
          total,
          status: t(`readinessTrack.status.${step.status}`),
          title: t(step.title_key),
        })}
        className={`flex w-full items-start gap-3 px-3 py-3 text-left transition-colors ${
          interactive
            ? 'hover:bg-surface focus-visible:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface-raised'
            : 'cursor-default opacity-70'
        }`}
      >
        <span className="mt-0.5 shrink-0">
          <Icon
            name={STATUS_ICON[step.status]}
            size="md"
            className={STATUS_TONE[step.status]}
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-fg">
            {t(step.title_key)}
          </span>
          <span className="mt-0.5 block text-xs text-muted-fg">
            {t(step.rationale_key, step.rationale_params)}
          </span>
        </span>
        {interactive && (
          <span
            aria-hidden="true"
            className={`ml-2 mt-1 shrink-0 transition-transform duration-base ease-out-soft ${
              expanded ? 'rotate-180' : ''
            }`}
          >
            <Icon name="ChevronDown" size="sm" variant="muted" />
          </span>
        )}
      </button>
      {expanded && interactive && (
        <div className="px-3 pb-4 pt-0">
          {step.id === 'skills' ? (
            <SkillsGrid progress={progress} target={targetBand} />
          ) : (
            <SubTaskList tasks={step.sub_tasks} stepId={step.id} />
          )}
        </div>
      )}
    </li>
  )
}

function SubTaskList({
  tasks,
  stepId,
}: {
  tasks: SubTask[]
  stepId: StepId
}) {
  const { t } = useTranslation('dashboard')
  if (tasks.length === 0) return null
  return (
    <ul className="space-y-1.5">
      {tasks.map((task) => (
        <li key={task.id}>
          <Link
            to={task.href}
            onClick={() =>
              track('dashboard_track_subtask_click', {
                step: stepId,
                subtask: task.id,
              })
            }
            className="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm text-fg hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon
              name={task.done ? 'CheckCircle2' : 'Circle'}
              size="sm"
              className={task.done ? 'text-success' : 'text-muted-fg'}
            />
            <span className={task.done ? 'text-muted-fg line-through' : ''}>
              {t(task.label_key)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function SkillsGrid({
  progress,
  target,
}: {
  progress: ProgressResponse | null
  target: number
}) {
  const { t } = useTranslation('common')
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {SKILLS.map((s) => {
        const card = progress
          ? {
              band: progress.snapshot.skills[s.key].band,
              delta: deltaFrom(
                progress.trend,
                `${s.key}_band` as
                  | 'writing_band'
                  | 'listening_band'
                  | 'vocabulary_band'
                  | 'reading_band',
              ),
            }
          : { band: 0, delta: 0 }
        return (
          <Link
            key={s.key}
            to={s.to}
            onClick={() =>
              track('dashboard_track_subtask_click', {
                step: 'skills',
                subtask: s.key,
              })
            }
            className="rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <SkillBandCard
              iconName={s.iconName}
              label={t(s.labelKey.split(':')[1])}
              band={card.band}
              target={target}
              delta={card.delta}
            />
          </Link>
        )
      })}
    </div>
  )
}

export default function ReadinessTrack({ progress }: Props) {
  const { t } = useTranslation('dashboard')
  const [data, setData] = useState<ReadinessResponse | null>(null)
  const [expandedId, setExpandedId] = useState<StepId | null>(null)

  useEffect(() => {
    apiFetch<ReadinessResponse>('/api/v1/readiness')
      .then((d) => {
        setData(d)
        const active = d.steps.find((s) => s.status === 'active')
        // <7 days exam → auto-expand skills (the gap-closing phase),
        // otherwise auto-expand the active step the API picked.
        if (d.urgent) {
          setExpandedId('skills')
        } else if (active) {
          setExpandedId(active.id)
        }
      })
      .catch(() => setData(null))
  }, [])

  const headerCopy = useMemo(() => {
    if (!data) return null
    if (data.urgent && data.days_until_exam !== null) {
      return {
        line: t('readinessTrack.header.urgent', { n: data.days_until_exam }),
        tone: 'text-warning',
      }
    }
    if (data.pct_complete >= 100) {
      return { line: t('readinessTrack.header.ready'), tone: 'text-success' }
    }
    return {
      line: t('readinessTrack.header.pct', { pct: data.pct_complete }),
      tone: 'text-muted-fg',
    }
  }, [data, t])

  if (!data) return null

  // No exam date set → empty-state CTA. Reuses PersonalizationCTA's
  // styling pattern so it visually matches existing onboarding nudges.
  if (data.days_until_exam === null) {
    return (
      <section
        aria-labelledby="readiness-track-heading"
        className="rounded-2xl border border-primary/20 bg-primary/5 p-5"
      >
        <h2
          id="readiness-track-heading"
          className="font-semibold text-fg"
        >
          {t('readinessTrack.empty.heading')}
        </h2>
        <p className="mt-1 text-sm text-muted-fg">
          {t('readinessTrack.empty.description')}
        </p>
        <Link
          to="/settings#exam-date"
          onClick={() =>
            track('dashboard_track_subtask_click', {
              step: 'goal',
              subtask: 'exam_date',
            })
          }
          className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-fg hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <Icon name="Calendar" size="sm" />
          {t('readinessTrack.empty.cta')}
        </Link>
      </section>
    )
  }

  const containerToneCls =
    data.urgent
      ? 'border-warning/30 bg-warning/5'
      : data.pct_complete >= 100
        ? 'border-success/30 bg-success/5'
        : 'border-border bg-surface-raised'

  return (
    <section
      aria-labelledby="readiness-track-heading"
      className={`rounded-2xl border ${containerToneCls}`}
    >
      <header className="flex items-baseline justify-between gap-2 px-4 pb-2 pt-4">
        <h2 id="readiness-track-heading" className="text-base font-semibold text-fg">
          {t('readinessTrack.heading')}
        </h2>
        <span className={`text-sm font-medium ${headerCopy?.tone ?? 'text-muted-fg'}`}>
          {headerCopy?.line}
        </span>
      </header>
      <div className="px-4 pb-3">
        <div
          role="progressbar"
          aria-valuenow={data.pct_complete}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-1.5 w-full overflow-hidden rounded-full bg-surface"
        >
          <div
            className={`h-full transition-all duration-base ease-out-soft ${
              data.pct_complete >= 100
                ? 'bg-success'
                : data.urgent
                  ? 'bg-warning'
                  : 'bg-primary'
            }`}
            style={{ width: `${data.pct_complete}%` }}
          />
        </div>
      </div>
      <ol className="px-1 pb-2">
        {data.steps.map((step, idx) => (
          <StepRow
            key={step.id}
            step={step}
            index={idx}
            total={data.steps.length}
            expanded={expandedId === step.id}
            onToggle={() => {
              const next = expandedId === step.id ? null : step.id
              setExpandedId(next)
              if (next) {
                track('dashboard_track_step_expand', { step: step.id })
              }
            }}
            progress={progress}
            targetBand={data.target_band}
          />
        ))}
      </ol>
    </section>
  )
}
