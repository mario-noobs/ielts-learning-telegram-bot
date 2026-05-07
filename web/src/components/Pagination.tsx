import { useTranslation } from 'react-i18next'

interface Props {
  page: number
  totalPages: number
  onPrev: () => void
  onNext: () => void
}

export default function Pagination({ page, totalPages, onPrev, onNext }: Props) {
  const { t } = useTranslation('vocab')
  const canPrev = page > 1
  const canNext = page < totalPages

  return (
    <nav
      aria-label={t('pagination.nav')}
      className="flex items-center justify-between gap-3"
    >
      <button
        type="button"
        onClick={onPrev}
        disabled={!canPrev}
        aria-label={t('pagination.prev')}
        className="px-4 py-2 min-h-[44px] rounded-xl border-2 border-border bg-surface-raised text-fg font-medium hover:border-primary hover:bg-primary/5 disabled:opacity-40 disabled:hover:border-border disabled:hover:bg-surface-raised transition-colors duration-base"
      >
        ◀ {t('pagination.prev')}
      </button>
      <span
        className="text-sm text-muted-fg tabular-nums"
        aria-live="polite"
      >
        {t('pagination.pageOf', { current: page, total: totalPages })}
      </span>
      <button
        type="button"
        onClick={onNext}
        disabled={!canNext}
        aria-label={t('pagination.next')}
        className="px-4 py-2 min-h-[44px] rounded-xl border-2 border-border bg-surface-raised text-fg font-medium hover:border-primary hover:bg-primary/5 disabled:opacity-40 disabled:hover:border-border disabled:hover:bg-surface-raised transition-colors duration-base"
      >
        {t('pagination.next')} ▶
      </button>
    </nav>
  )
}
