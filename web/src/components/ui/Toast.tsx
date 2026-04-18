import {
  createContext,
  forwardRef,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ComponentPropsWithoutRef,
  type ElementRef,
  type ReactNode,
} from 'react'
import * as ToastPrimitive from '@radix-ui/react-toast'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

/**
 * Toast — Radix Toast wrapped with tokens + a tiny `useToast()` hook.
 *
 *  <ToastProvider>          wraps the app (once, near the root).
 *  const { toast } = useToast()
 *  toast({ title, description, variant, duration })
 *
 * Variants: default | success | warning | danger
 * Auto-dismiss: 3s by default, overrideable per call.
 * role="status" with polite live region (Radix handles foreground/foregroundable).
 * Reduced-motion snaps in/out via --dur-base = 0ms.
 */

const toastVariants = cva(
  [
    'pointer-events-auto relative flex w-full items-start gap-3',
    'rounded-xl border p-4 shadow-md',
    'data-[state=open]:animate-in data-[state=closed]:animate-out',
    'data-[state=closed]:fade-out-80 data-[state=open]:slide-in-from-bottom-2',
    'data-[swipe=move]:transition-none',
  ].join(' '),
  {
    variants: {
      variant: {
        default: 'bg-surface-raised border-border text-fg',
        success: 'bg-success/10 border-success/30 text-fg',
        warning: 'bg-warning/10 border-warning/30 text-fg',
        danger: 'bg-danger/10 border-danger/30 text-fg',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export type ToastVariant = NonNullable<
  VariantProps<typeof toastVariants>['variant']
>

export interface ToastPayload {
  id?: string
  title?: ReactNode
  description?: ReactNode
  variant?: ToastVariant
  /** ms; defaults to 3000. Set Infinity to require manual dismiss. */
  duration?: number
}

interface ToastItem extends Required<Pick<ToastPayload, 'id'>> {
  title?: ReactNode
  description?: ReactNode
  variant: ToastVariant
  duration: number
  open: boolean
}

interface ToastContextValue {
  toast: (payload: ToastPayload) => string
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast() must be called inside <ToastProvider>.')
  }
  return ctx
}

interface ProviderProps {
  children: ReactNode
  /** Optional default duration override (ms). */
  defaultDuration?: number
}

export function ToastProvider({
  children,
  defaultDuration = 3000,
}: ProviderProps) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, open: false } : t)),
    )
  }, [])

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(
    (payload: ToastPayload): string => {
      const id =
        payload.id ??
        `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      setToasts((prev) => [
        ...prev,
        {
          id,
          title: payload.title,
          description: payload.description,
          variant: payload.variant ?? 'default',
          duration: payload.duration ?? defaultDuration,
          open: true,
        },
      ])
      return id
    },
    [defaultDuration],
  )

  const value = useMemo<ToastContextValue>(
    () => ({ toast, dismiss }),
    [toast, dismiss],
  )

  return (
    <ToastContext.Provider value={value}>
      <ToastPrimitive.Provider swipeDirection="right" duration={defaultDuration}>
        {children}
        {toasts.map((t) => (
          <ToastPrimitive.Root
            key={t.id}
            open={t.open}
            duration={t.duration}
            onOpenChange={(open) => {
              if (!open) {
                // Defer remove so the close animation can run; --dur-base
                // clamps to 0ms under reduced-motion so this is still fast.
                dismiss(t.id)
                window.setTimeout(() => remove(t.id), 220)
              }
            }}
            className={cn(toastVariants({ variant: t.variant }))}
            style={{ transitionDuration: 'var(--dur-base)' }}
          >
            <div className="flex-1 flex flex-col gap-0.5">
              {t.title ? (
                <ToastPrimitive.Title className="text-sm font-semibold text-fg">
                  {t.title}
                </ToastPrimitive.Title>
              ) : null}
              {t.description ? (
                <ToastPrimitive.Description className="text-sm text-muted-fg">
                  {t.description}
                </ToastPrimitive.Description>
              ) : null}
            </div>
            <ToastPrimitive.Close
              aria-label="Đóng"
              className="text-muted-fg hover:text-fg transition-colors duration-base ease-out-soft"
            >
              <span aria-hidden>×</span>
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport
          className={cn(
            'fixed bottom-0 right-0 z-[100] flex max-h-screen w-full flex-col-reverse gap-2 p-4 sm:max-w-sm',
            'outline-none',
          )}
        />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  )
}

/** Raw Radix primitive re-exports for advanced composition scenarios. */
export const RadixToast = ToastPrimitive
export const Toast = forwardRef<
  ElementRef<typeof ToastPrimitive.Root>,
  ComponentPropsWithoutRef<typeof ToastPrimitive.Root> &
    VariantProps<typeof toastVariants>
>(({ className, variant, ...props }, ref) => (
  <ToastPrimitive.Root
    ref={ref}
    className={cn(toastVariants({ variant }), className)}
    {...props}
  />
))
Toast.displayName = 'Toast'
