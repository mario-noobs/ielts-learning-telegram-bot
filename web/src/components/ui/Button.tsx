import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

/**
 * Button — core shadcn-style primitive styled exclusively via design tokens.
 *
 * Variants: primary | secondary | ghost | destructive
 * Sizes:    sm (36) | md (44, default, meets 44×44 touch target) | lg (56)
 *
 * Props of note:
 *   - `loading`  shows a spinner and disables the button; children stay visible
 *               so layout doesn't shift (matches shadcn behavior)
 *   - `leftIcon` / `rightIcon`  inline slot for <Icon> or any element
 *   - `asChild`  Radix `Slot` pattern — forwards button styles onto an <a> or
 *               custom child so the DOM stays semantically correct (e.g. router Link)
 */
export const buttonVariants = cva(
  [
    'inline-flex items-center justify-center gap-2 whitespace-nowrap',
    'rounded-xl font-medium select-none',
    'transition-colors duration-base ease-out-soft',
    'disabled:opacity-50 disabled:pointer-events-none',
    'active:scale-[0.98]',
  ].join(' '),
  {
    variants: {
      variant: {
        primary:
          'bg-primary text-primary-fg hover:bg-primary-hover',
        secondary:
          'bg-surface-raised text-fg border border-border hover:bg-surface',
        ghost:
          'bg-transparent text-fg hover:bg-surface',
        destructive:
          'bg-danger text-primary-fg hover:opacity-90',
      },
      size: {
        sm: 'h-9 px-3 text-sm',
        md: 'h-11 px-4 text-base',
        lg: 'h-14 px-6 text-lg',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

type ButtonOwnProps = {
  /** Shows an inline spinner and disables the button. */
  loading?: boolean
  /** Element rendered before children (inside the button). */
  leftIcon?: ReactNode
  /** Element rendered after children. */
  rightIcon?: ReactNode
  /** When true, render children directly with button classes (Radix Slot). */
  asChild?: boolean
}

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants>,
    ButtonOwnProps {}

// Inline spinner that inherits currentColor; no raw hex so it themes cleanly.
function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn('animate-spin', className)}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      focusable={false}
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
        opacity="0.25"
      />
      <path
        d="M22 12a10 10 0 0 1-10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  )
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      loading = false,
      leftIcon,
      rightIcon,
      asChild = false,
      disabled,
      children,
      type,
      ...rest
    },
    ref,
  ) => {
    const Comp = asChild ? Slot : 'button'

    // When asChild, Slot forwards props to a single child — we can't inject
    // spinner/icon siblings without breaking its single-child contract.
    // In that case we rely on the consumer to place icons themselves.
    if (asChild) {
      return (
        <Comp
          ref={ref as never}
          className={cn(buttonVariants({ variant, size }), className)}
          {...rest}
        >
          {children}
        </Comp>
      )
    }

    return (
      <button
        ref={ref}
        type={type ?? 'button'}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading ? <Spinner /> : leftIcon}
        {children}
        {!loading && rightIcon}
      </button>
    )
  },
)
Button.displayName = 'Button'
