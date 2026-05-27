import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon, { IconName } from '../../components/Icon'
import { track } from '../../lib/analytics'

type ActionId = 'daily' | 'review' | 'writing' | 'reading'

type Action = {
  id: ActionId
  to: string
  icon: IconName
  titleKey: string
  hintKey: string
}

const ACTIONS: Action[] = [
  {
    id: 'daily',
    to: '/learn/daily',
    icon: 'Calendar',
    titleKey: 'quickActions.daily.title',
    hintKey: 'quickActions.daily.description',
  },
  {
    id: 'review',
    to: '/learn/review',
    icon: 'RotateCcw',
    titleKey: 'quickActions.review.title',
    hintKey: 'quickActions.review.description',
  },
  {
    id: 'writing',
    to: '/practice/writing',
    icon: 'PenLine',
    titleKey: 'quickActions.writing.title',
    hintKey: 'quickActions.writing.description',
  },
  {
    id: 'reading',
    to: '/practice/reading',
    icon: 'FileText',
    titleKey: 'quickActions.reading.title',
    hintKey: 'quickActions.reading.description',
  },
]

export default function QuickActions() {
  const { t } = useTranslation('dashboard')
  return (
    <section aria-labelledby="quick-actions-heading">
      <h2 id="quick-actions-heading" className="sr-only">
        {t('quickActions.heading')}
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
        {ACTIONS.map((a) => (
          <Link
            key={a.id}
            to={a.to}
            onClick={() => track('dashboard_quick_action_click', { action: a.id })}
            className="group flex items-start gap-3 rounded-2xl border border-border bg-surface-raised p-4 transition-colors hover:border-primary/40 hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Icon name={a.icon} size="lg" variant="primary" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-fg">{t(a.titleKey)}</p>
              <p className="mt-0.5 text-sm leading-relaxed text-muted-fg">
                {t(a.hintKey)}
              </p>
            </div>
            <Icon
              name="ArrowRight"
              size="md"
              variant="muted"
              className="mt-1 shrink-0 transition-transform duration-base ease-out-soft group-hover:translate-x-0.5 group-hover:text-primary"
            />
          </Link>
        ))}
      </div>
    </section>
  )
}
