import { useTranslation } from 'react-i18next'

interface LoadingScreenProps {
  title?: string
  subtitle?: string
  fullScreen?: boolean
  className?: string
}

export default function LoadingScreen({
  title,
  subtitle,
  fullScreen = false,
  className = '',
}: LoadingScreenProps) {
  const { t } = useTranslation('common')
  const heading = title ?? t('loadingScreen.title')
  const description = subtitle ?? t('loadingScreen.subtitle')

  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={[
        'flex items-center justify-center px-4 text-center',
        fullScreen ? 'min-h-dvh' : 'min-h-[320px]',
        className,
      ].join(' ')}
    >
      <div className="w-full max-w-sm">
        <div className="relative mx-auto h-28 w-28" aria-hidden="true">
          <div className="study-loader-ring absolute inset-0 rounded-full border border-primary/20" />
          <div className="study-loader-ring study-loader-ring-delay absolute inset-3 rounded-full border border-accent/25" />
          <div className="absolute left-1/2 top-1/2 grid h-14 w-14 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-2xl border border-border bg-surface-raised shadow-sm">
            <span className="text-lg font-semibold text-primary">A</span>
          </div>
          <span className="study-loader-token study-loader-token-one">B2</span>
          <span className="study-loader-token study-loader-token-two">7.0</span>
          <span className="study-loader-token study-loader-token-three">SRS</span>
        </div>

        <div className="mt-5 space-y-2">
          <h2 className="text-base font-semibold text-fg">{heading}</h2>
          <p className="text-sm leading-6 text-muted-fg">{description}</p>
        </div>

        <div className="mx-auto mt-5 h-1.5 w-44 overflow-hidden rounded-full bg-border/70">
          <div className="study-loader-meter h-full w-1/2 rounded-full bg-primary" />
        </div>
      </div>
      <span className="sr-only">{t('status.loading')}</span>
    </div>
  )
}
