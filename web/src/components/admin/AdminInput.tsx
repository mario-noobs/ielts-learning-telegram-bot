import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes, type ReactNode } from 'react'

/**
 * Single source of truth for admin-console form fields (US-M11.6).
 *
 * Both `<AdminInput>` and `<AdminSelect>` share the same height + radius
 * + border so rows align with `AdminButton` size="md" (36px) without
 * per-page tweaks. Wrap in `<AdminField label="...">` for shared label
 * layout.
 */

const CONTROL =
  'w-full h-9 px-3 rounded-lg border border-border bg-surface text-sm placeholder:text-muted-fg focus:outline-none focus:ring-2 focus:ring-primary/40'

interface FieldProps {
  label?: string
  hint?: string
  children: ReactNode
}

export function AdminField({ label, hint, children }: FieldProps) {
  return (
    <label className="block">
      {label && <span className="block text-sm font-medium mb-1">{label}</span>}
      {children}
      {hint && <p className="text-xs text-muted-fg mt-1">{hint}</p>}
    </label>
  )
}

const AdminInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function AdminInput({ className = '', ...rest }, ref) {
    return <input ref={ref} {...rest} className={`${CONTROL} ${className}`} />
  },
)

export default AdminInput

export const AdminSelect = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function AdminSelect({ className = '', children, ...rest }, ref) {
  return (
    <select ref={ref} {...rest} className={`${CONTROL} ${className}`}>
      {children}
    </select>
  )
})
