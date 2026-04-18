import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
} from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

/**
 * Input — token-styled text input with optional label, leading/trailing
 * addons, and an error variant that flips aria-invalid on.
 *
 * Variants: default | error
 * Sizes:    sm | md (default)
 *
 * The label wiring is automatic: if you pass `label`, the component generates
 * an id (or uses the one you provided), renders a real <label htmlFor>, and
 * associates helper/error text via aria-describedby.
 */

const inputVariants = cva(
  [
    'flex w-full rounded-xl border bg-surface-raised text-fg',
    'placeholder:text-muted-fg',
    'transition-colors duration-base ease-out-soft',
    'disabled:opacity-50 disabled:cursor-not-allowed',
  ].join(' '),
  {
    variants: {
      variant: {
        default: 'border-border focus-visible:border-primary',
        error: 'border-danger focus-visible:border-danger',
      },
      inputSize: {
        sm: 'h-9 text-sm px-3',
        md: 'h-11 text-base px-3.5',
      },
    },
    defaultVariants: {
      variant: 'default',
      inputSize: 'md',
    },
  },
)

export interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'>,
    VariantProps<typeof inputVariants> {
  /** Visible label. Rendered above the input and wired via htmlFor/id. */
  label?: ReactNode
  /** Helper text shown under the input. Read out by screen readers. */
  helperText?: ReactNode
  /** Error message shown under the input; forces variant="error". */
  errorText?: ReactNode
  /** Element rendered inside the input's left slot (e.g. search icon). */
  leadingAddon?: ReactNode
  /** Element rendered inside the input's right slot (e.g. unit label). */
  trailingAddon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      variant,
      inputSize,
      label,
      helperText,
      errorText,
      leadingAddon,
      trailingAddon,
      id,
      ...rest
    },
    ref,
  ) => {
    const generatedId = useId()
    const inputId = id ?? generatedId
    const helperId = `${inputId}-helper`
    const errorId = `${inputId}-error`
    const hasError = Boolean(errorText)
    const resolvedVariant = hasError ? 'error' : variant

    // describedby chains error + helper when both are present; filter avoids
    // producing the dangling whitespace screen readers would read as empty.
    const describedBy = [
      hasError ? errorId : null,
      helperText ? helperId : null,
    ]
      .filter(Boolean)
      .join(' ') || undefined

    const input = (
      <input
        ref={ref}
        id={inputId}
        aria-invalid={hasError || undefined}
        aria-describedby={describedBy}
        className={cn(
          inputVariants({ variant: resolvedVariant, inputSize }),
          (leadingAddon || trailingAddon) && 'px-0',
          className,
        )}
        {...rest}
      />
    )

    const wrapped =
      leadingAddon || trailingAddon ? (
        <div
          className={cn(
            inputVariants({ variant: resolvedVariant, inputSize }),
            'items-center gap-2 px-3',
          )}
        >
          {leadingAddon ? (
            <span className="text-muted-fg flex items-center" aria-hidden>
              {leadingAddon}
            </span>
          ) : null}
          <input
            ref={ref}
            id={inputId}
            aria-invalid={hasError || undefined}
            aria-describedby={describedBy}
            className="flex-1 bg-transparent outline-none placeholder:text-muted-fg text-fg h-full"
            {...rest}
          />
          {trailingAddon ? (
            <span className="text-muted-fg flex items-center" aria-hidden>
              {trailingAddon}
            </span>
          ) : null}
        </div>
      ) : (
        input
      )

    return (
      <div className="flex flex-col gap-1.5 w-full">
        {label ? (
          <label
            htmlFor={inputId}
            className="text-sm font-medium text-fg"
          >
            {label}
          </label>
        ) : null}
        {wrapped}
        {hasError ? (
          <p id={errorId} className="text-sm text-danger" role="alert">
            {errorText}
          </p>
        ) : helperText ? (
          <p id={helperId} className="text-sm text-muted-fg">
            {helperText}
          </p>
        ) : null}
      </div>
    )
  },
)
Input.displayName = 'Input'
