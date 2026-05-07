import { type ReactNode } from 'react'

/**
 * Padded section container for admin pages (US-M11.6).
 *
 * Standardises padding (`p-4`) and stack-spacing (`space-y-4`) so every
 * form / table / chart on an admin page sits in the same shaped box.
 * `title` renders an h2 row with optional right-aligned actions.
 */

interface Props {
  title?: string
  actions?: ReactNode
  className?: string
  children: ReactNode
}

export default function AdminCard({ title, actions, className = '', children }: Props) {
  return (
    <section
      className={`rounded-xl border border-border bg-surface-raised p-4 space-y-4 ${className}`}
    >
      {(title || actions) && (
        <div className="flex items-center justify-between gap-3">
          {title && <h2 className="text-lg font-semibold">{title}</h2>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

/** Standard page-header row used by every admin page. */
export function AdminPageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        {subtitle && <p className="text-muted-fg text-sm">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}
