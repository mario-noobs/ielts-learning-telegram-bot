import { useTranslation } from 'react-i18next'
import { timeOfDay } from '../../lib/plan'

interface Props {
  name: string
}

const MOTIVATION_COUNT = 5

function dayOfYear(date: Date): number {
  const start = new Date(date.getFullYear(), 0, 0)
  const diff = date.getTime() - start.getTime()
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

export default function DashboardGreeting({ name }: Props) {
  const { t } = useTranslation('dashboard')
  const now = new Date()
  const firstName = name.split(/\s+/).slice(-1)[0] || name
  const motivationIdx = dayOfYear(now) % MOTIVATION_COUNT
  const greeting = t(`greeting.${timeOfDay(now)}`, { name: firstName })

  return (
    <section
      aria-labelledby="dashboard-greeting-heading"
      className="bg-gradient-to-br from-primary to-primary-hover rounded-2xl px-5 py-4 text-primary-fg shadow-md md:px-6 md:py-5"
    >
      <h1
        id="dashboard-greeting-heading"
        className="text-xl font-bold md:text-2xl"
      >
        {greeting} <span aria-hidden="true">👋</span>
      </h1>
      <p className="mt-1.5 text-sm leading-relaxed text-primary-fg/90">
        {t(`greeting.motivation.${motivationIdx}`)}
      </p>
    </section>
  )
}
