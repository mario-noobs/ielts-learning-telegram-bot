import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useProfile } from '../contexts/AuthContext'
import { track } from '../lib/analytics'
import {
  Modal,
  ModalContent,
  ModalDescription,
  ModalFooter,
  ModalHeader,
  ModalTitle,
} from './ui'
import { Button } from './ui/Button'

const PAID_PLANS = new Set(['personal_pro', 'team_member', 'org_member'])

const SHOWN_KEY_PREFIX = 'quota.modal.shown.'
const SUPPORT_MAILTO = 'mailto:support@example.com'

interface QuotaExceededDetail {
  plan_quota?: number
  used?: number
  feature?: string
  plan?: string
  [key: string]: unknown
}

function todayKey(): string {
  // UTC date — matches backend reset boundary (`docs/quota.md`).
  const d = new Date()
  return `${SHOWN_KEY_PREFIX}${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
}

/**
 * Global modal that opens when any AI route returns 429 with
 * `error.code === "quota.daily_exceeded"` (US-M13.3).
 *
 * Shows once per saturation event (per UTC day), tracked via sessionStorage
 * so a hard reload won't re-trigger if the user has already acknowledged it.
 *
 * Free users see "Upgrade to Pro" → /pricing. Paid users see "Contact admin"
 * → mailto support (placeholder until the in-app support inbox lands).
 *
 * Mounted once globally in `<AppShell>`. Focus-trap, escape-to-close, and
 * focus restore are inherited from the underlying Radix dialog primitive.
 */
export default function QuotaExceededModal() {
  const { t } = useTranslation('dashboard')
  const navigate = useNavigate()
  const profile = useProfile()
  const [open, setOpen] = useState(false)
  const [detail, setDetail] = useState<QuotaExceededDetail>({})

  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<QuotaExceededDetail>
      const key = todayKey()
      try {
        if (sessionStorage.getItem(key) === '1') return
        sessionStorage.setItem(key, '1')
      } catch {
        /* private mode — show modal in-memory once via the open state */
      }
      setDetail(customEvent.detail ?? {})
      setOpen(true)
      track('quota.modal.shown', customEvent.detail ?? {})
    }
    window.addEventListener('quota:exceeded', handler)
    return () => window.removeEventListener('quota:exceeded', handler)
  }, [])

  const isFree = !profile || !PAID_PLANS.has(profile.plan)
  const planLabel = (detail.plan as string | undefined) ?? profile?.plan ?? 'free'
  const quota = detail.plan_quota ?? 0

  const handlePrimary = useCallback(() => {
    track('quota.modal.cta_clicked', { paid: !isFree })
    setOpen(false)
    if (isFree) {
      navigate('/pricing')
    } else {
      window.location.href = SUPPORT_MAILTO
    }
  }, [isFree, navigate])

  const handleSecondary = useCallback(() => {
    setOpen(false)
  }, [])

  return (
    <Modal open={open} onOpenChange={setOpen}>
      <ModalContent>
        <ModalHeader>
          <ModalTitle>{t('aiUsage.modal.title')}</ModalTitle>
          <ModalDescription>
            {t('aiUsage.modal.body', { plan_quota: quota, plan: planLabel })}
          </ModalDescription>
        </ModalHeader>
        <ModalFooter>
          <Button variant="ghost" onClick={handleSecondary}>
            {t('aiUsage.modal.secondary')}
          </Button>
          <Button variant="primary" onClick={handlePrimary}>
            {isFree
              ? t('aiUsage.modal.primary')
              : t('aiUsage.modal.primaryPaid')}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}
