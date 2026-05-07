import { type ButtonHTMLAttributes, type ReactNode } from 'react'

/**
 * Single source of truth for admin-console button styling (US-M11.6).
 *
 * Variants:
 *   - primary   → filled, primary CTA (Save, Create, Apply)
 *   - secondary → bordered, low-emphasis (Cancel, Reset)
 *   - danger    → bordered red text, destructive (Delete, Remove)
 *
 * Sizes:
 *   - md (default) → 36px row-height, paired with AdminInput
 *   - sm           → 28px, for inline "remove" affordances inside table rows
 *
 * Don't reach for raw <button className="..."> in admin pages.
 */

export type AdminButtonVariant = 'primary' | 'secondary' | 'danger'
export type AdminButtonSize = 'sm' | 'md'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: AdminButtonVariant
  size?: AdminButtonSize
  children: ReactNode
}

const VARIANT: Record<AdminButtonVariant, string> = {
  primary:
    'bg-primary text-on-primary hover:bg-primary/90 disabled:opacity-50',
  secondary:
    'border border-border bg-surface-raised text-fg hover:bg-surface disabled:opacity-50',
  danger:
    'border border-danger text-danger hover:bg-danger/10 disabled:opacity-50',
}

const SIZE: Record<AdminButtonSize, string> = {
  md: 'h-9 px-3 text-sm',
  sm: 'h-7 px-2 text-xs',
}

export default function AdminButton({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...rest
}: Props) {
  return (
    <button
      {...rest}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors duration-fast ${VARIANT[variant]} ${SIZE[size]} ${className}`}
    >
      {children}
    </button>
  )
}
