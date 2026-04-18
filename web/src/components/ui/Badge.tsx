import { forwardRef, type HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

/**
 * Badge — small pill for status / category chips.
 *
 * Variants: neutral | primary | success | warning | danger | info
 * Sizes:    caption-sized, single height
 *
 * Uses the *tinted* token pattern from DESIGN_SPECS (`bg-token/10 text-token`)
 * so the pill reads as a status tint rather than a full color block — keeps
 * WCAG AA text contrast while preserving semantic color.
 */
export const badgeVariants = cva(
  [
    'inline-flex items-center gap-1 rounded-full',
    'px-2.5 py-0.5 text-xs font-medium',
    'border border-transparent',
  ].join(' '),
  {
    variants: {
      variant: {
        neutral: 'bg-surface text-fg border-border',
        primary: 'bg-primary/10 text-primary border-primary/20',
        success: 'bg-success/10 text-success border-success/20',
        warning: 'bg-warning/10 text-warning border-warning/20',
        danger: 'bg-danger/10 text-danger border-danger/20',
        // `info` is primary-adjacent but slightly cooler in the design lexicon —
        // we reuse the primary tokens here until an explicit `info` token ships.
        info: 'bg-primary/10 text-primary border-primary/20',
      },
    },
    defaultVariants: {
      variant: 'neutral',
    },
  },
)

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  ),
)
Badge.displayName = 'Badge'
