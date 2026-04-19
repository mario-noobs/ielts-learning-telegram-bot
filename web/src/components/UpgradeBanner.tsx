import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from './Icon'
import { track } from '../lib/analytics'

const DISMISS_KEY = 'upgrade_banner_dismissed_v1'

export default function UpgradeBanner() {
  const [dismissed, setDismissed] = useState<boolean | null>(null)

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(DISMISS_KEY) === '1')
    } catch {
      setDismissed(false)
    }
  }, [])

  const handleDismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, '1')
    } catch {
      /* private mode — dismiss this session only */
    }
    setDismissed(true)
    track('upgrade_banner_dismissed')
  }

  const handleCta = () => {
    track('upgrade_banner_cta')
  }

  if (dismissed !== false) return null

  return (
    <div
      role="region"
      aria-label="Gợi ý nâng cấp Pro"
      className="relative border-b border-primary/20 bg-gradient-to-r from-primary/10 via-primary/5 to-accent/10 px-4 py-2.5 md:px-6"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <Icon name="Sparkles" size="sm" variant="primary" className="hidden sm:block" />
          <p className="min-w-0 truncate text-sm text-fg">
            <span className="font-semibold text-primary">Đang dùng bản Beta</span>
            <span className="mx-1.5 text-muted-fg">·</span>
            <span className="text-muted-fg">
              Mở khoá Writing không giới hạn + Adaptive Plan với Pro
            </span>
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Link
            to="/pricing"
            onClick={handleCta}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-fg transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            Xem gói Pro
          </Link>
          <button
            type="button"
            onClick={handleDismiss}
            aria-label="Đóng thông báo"
            className="rounded-lg p-1.5 text-muted-fg transition-colors hover:bg-surface hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <Icon name="X" size="sm" />
          </button>
        </div>
      </div>
    </div>
  )
}
