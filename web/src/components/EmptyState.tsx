import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import Icon, { type IconName } from './Icon'

/**
 * Empty-state slot. Used to replace the plain "no data" text that shipped in
 * M1-M5 with a consistent illustration + copy + CTA block. Composable (no
 * shadcn primitive dependency): ships before #121 and will auto-adopt the
 * `<Button>` primitive later once it lands.
 *
 * Illustration rules (see US-M6.6 / #125):
 * - `illustration` accepts either the basename of an SVG in
 *   `/public/illustrations/` (e.g. `"empty-vocab"`), or an inline ReactNode.
 * - If omitted, falls back to a Lucide `icon`; if both omitted, no visual is
 *   rendered. Bundle-wise, the SVG path keeps glyphs out of the JS bundle.
 * - Uses `currentColor`, so the parent's `text-*` class drives the stroke/fill.
 */
export interface EmptyStateAction {
  label: string
  onClick?: () => void
  /** React Router path. When present, renders a `<Link>` instead of a `<button>`. */
  to?: string
}

export type EmptyStateVariant = 'default' | 'celebration' | 'error'

export interface EmptyStateProps {
  /** SVG basename in `/illustrations/` (e.g. `"empty-vocab"`) or an inline node. */
  illustration?: string | ReactNode
  /** Lucide icon name, used only when `illustration` is not provided. */
  icon?: IconName
  title: string
  description?: string
  primaryAction?: EmptyStateAction
  secondaryAction?: EmptyStateAction
  variant?: EmptyStateVariant
  className?: string
}

const VARIANT_TINT: Record<EmptyStateVariant, string> = {
  default: 'text-muted-fg',
  celebration: 'text-success',
  error: 'text-danger',
}

function isString(v: unknown): v is string {
  return typeof v === 'string'
}

function renderIllustration(
  illustration: EmptyStateProps['illustration'],
  icon: IconName | undefined,
  tintClass: string,
) {
  if (illustration) {
    if (isString(illustration)) {
      // Static asset served from /public/illustrations/<name>.svg. We use
      // CSS mask-image (not <img>) so the icon colour follows the parent's
      // `text-*` utility — this is what makes dark-mode theming Just Work
      // without bundling the SVG into the JS chunk.
      const url = `/illustrations/${illustration}.svg`
      const style = {
        WebkitMaskImage: `url(${url})`,
        maskImage: `url(${url})`,
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
      } as const
      return (
        <div
          role="img"
          aria-hidden
          className={`w-32 h-32 md:w-40 md:h-40 bg-current ${tintClass}`}
          style={style}
        />
      )
    }
    return <div className={`w-32 h-32 md:w-40 md:h-40 ${tintClass}`}>{illustration}</div>
  }
  if (icon) {
    return <Icon name={icon} size="xl" variant="muted" />
  }
  return null
}

function ActionButton({
  action,
  kind,
}: {
  action: EmptyStateAction
  kind: 'primary' | 'secondary'
}) {
  const baseClass = [
    'inline-flex items-center justify-center rounded-md px-4 py-2 min-h-[44px]',
    'text-sm font-medium',
    'transition-colors duration-base ease-out-soft',
    'disabled:opacity-50 disabled:pointer-events-none',
  ].join(' ')

  const variantClass =
    kind === 'primary'
      ? 'bg-primary text-primary-fg hover:bg-primary-hover'
      : 'bg-transparent text-fg border border-border hover:bg-surface'

  const className = `${baseClass} ${variantClass}`

  if (action.to) {
    return (
      <Link to={action.to} className={className} onClick={action.onClick}>
        {action.label}
      </Link>
    )
  }
  return (
    <button type="button" onClick={action.onClick} className={className}>
      {action.label}
    </button>
  )
}

export default function EmptyState({
  illustration,
  icon,
  title,
  description,
  primaryAction,
  secondaryAction,
  variant = 'default',
  className = '',
}: EmptyStateProps) {
  return (
    <div
      role="region"
      aria-label={title}
      className={[
        'flex flex-col items-center text-center',
        'max-w-sm mx-auto px-4 py-8',
        'gap-6', // 24px vertical rhythm
        className,
      ].join(' ')}
    >
      {renderIllustration(illustration, icon, VARIANT_TINT[variant])}

      <div className="space-y-2">
        <h3 className="text-lg font-semibold text-fg">{title}</h3>
        {description && (
          <p className="text-sm text-muted-fg leading-relaxed">{description}</p>
        )}
      </div>

      {(primaryAction || secondaryAction) && (
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          {primaryAction && <ActionButton action={primaryAction} kind="primary" />}
          {secondaryAction && <ActionButton action={secondaryAction} kind="secondary" />}
        </div>
      )}
    </div>
  )
}
