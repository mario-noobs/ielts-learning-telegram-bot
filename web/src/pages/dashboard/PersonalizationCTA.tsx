import { useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'
import { track } from '../../lib/analytics'

interface Props {
  /** Field the settings page should scroll / focus on open */
  focusField: 'target-band' | 'exam-date'
}

export default function PersonalizationCTA({ focusField }: Props) {
  const [dismissed, setDismissed] = useState(false)
  if (dismissed) return null

  const isBand = focusField === 'target-band'
  const title = isBand
    ? 'Đặt mục tiêu band IELTS của bạn'
    : 'Cho chúng tôi biết ngày thi của bạn'
  const hint = isBand
    ? 'Cá nhân hoá kế hoạch luyện hàng ngày theo band mục tiêu.'
    : 'Chúng tôi sẽ tăng cường luyện tập khi ngày thi đến gần.'

  return (
    <section
      aria-labelledby="personalization-cta-heading"
      className="rounded-2xl border border-primary/20 bg-primary/5 p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h2
            id="personalization-cta-heading"
            className="font-semibold text-fg"
          >
            {title}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-fg">{hint}</p>
          <Link
            to={`/settings#${focusField}`}
            onClick={() => track('dashboard_personalization_cta_click', { field: focusField })}
            className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-fg transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <Icon name="Plus" size="sm" />
            {isBand ? 'Thêm mục tiêu' : 'Thêm ngày thi'}
          </Link>
        </div>
        <button
          type="button"
          onClick={() => setDismissed(true)}
          aria-label="Ẩn gợi ý"
          className="rounded-lg p-1.5 text-muted-fg transition-colors hover:bg-surface hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon name="X" size="sm" />
        </button>
      </div>
    </section>
  )
}
