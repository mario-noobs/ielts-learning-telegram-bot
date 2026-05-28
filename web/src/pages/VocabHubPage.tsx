import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import Icon, { type IconName } from '../components/Icon'
import { track } from '../lib/analytics'

function HubAction({
  title,
  description,
  meta,
  to,
  icon,
  primary = false,
  eventName,
}: {
  title: string
  description: string
  meta: string
  to: string
  icon: IconName
  primary?: boolean
  eventName: string
}) {
  return (
    <Link
      to={to}
      onClick={() => track(eventName)}
      className={`flex min-h-36 flex-col justify-between rounded-xl border p-4 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
        primary
          ? 'border-primary/40 bg-primary/10 hover:border-primary/70'
          : 'border-border bg-surface-raised hover:border-primary/40'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className={`rounded-lg p-2 ${primary ? 'bg-primary text-on-primary' : 'bg-surface text-primary'}`}>
          <Icon name={icon} size="md" variant={primary ? 'fg' : 'primary'} />
        </div>
        <Icon name="ArrowRight" size="sm" variant="muted" />
      </div>
      <div className="mt-5">
        <p className="text-sm font-medium text-muted-fg">{meta}</p>
        <h2 className="mt-1 text-lg font-semibold text-fg">{title}</h2>
        <p className="mt-1 text-sm text-muted-fg">{description}</p>
      </div>
    </Link>
  )
}

export default function VocabHubPage() {
  const { t } = useTranslation('vocab')

  return (
    <div className="mx-auto max-w-5xl p-4">
      <header className="mb-6">
        <p className="text-sm font-medium text-primary">{t('hub.eyebrow')}</p>
        <h1 className="mt-1 text-2xl font-bold text-fg md:text-3xl">
          {t('hub.heading')}
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-fg">
          {t('hub.subtitle')}
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <HubAction
          primary
          icon="Calendar"
          to="/learn/daily"
          eventName="vocab_hub_daily_opened"
          meta={t('hub.today.meta')}
          title={t('hub.today.title')}
          description={t('hub.today.description')}
        />
        <HubAction
          icon="BookOpen"
          to="/learn/vocab/my-words"
          eventName="vocab_hub_my_words_opened"
          meta={t('hub.myWords.meta')}
          title={t('hub.myWords.title')}
          description={t('hub.myWords.description')}
        />
        <HubAction
          icon="RotateCcw"
          to="/learn/review"
          eventName="vocab_hub_review_opened"
          meta={t('hub.review.meta')}
          title={t('hub.review.title')}
          description={t('hub.review.description')}
        />
      </div>
    </div>
  )
}
