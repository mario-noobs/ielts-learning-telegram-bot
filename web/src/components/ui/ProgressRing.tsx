/**
 * ProgressRing — SVG ring showing completed/total.
 *
 * Moved from `components/ProgressRing.tsx` under #121. The default export and
 * props signature are preserved so the existing `components/ProgressRing.tsx`
 * shim can re-export without breaking any import site.
 *
 * Stroke colors migrated from raw hex to design tokens:
 *   - track → --color-border (was #e5e7eb)
 *   - fill  → --color-primary (was #4f46e5, indigo — dropped per DESIGN_SPECS)
 *
 * Motion uses --dur-slow so reduced-motion snaps to the final state.
 */

interface Props {
  completed: number
  total: number
  size?: number
  /** Accessible label override. Defaults to a Vietnamese "X trên Y" phrase. */
  ariaLabel?: string
}

export default function ProgressRing({
  completed,
  total,
  size = 64,
  ariaLabel,
}: Props) {
  const safeTotal = Math.max(1, total)
  const pct = Math.min(1, Math.max(0, completed / safeTotal))
  const stroke = 6
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const dash = c * pct
  const label = ariaLabel ?? `${completed} trên ${total} đã hoàn thành`

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={label}
    >
      <svg
        width={size}
        height={size}
        className="-rotate-90"
        aria-hidden
        focusable={false}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          // stroke="rgb(var(--color-border))" — no raw hex, token-driven
          stroke="rgb(var(--color-border))"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="rgb(var(--color-primary))"
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
          fill="none"
          style={{
            transition:
              'stroke-dasharray var(--dur-slow) var(--ease-in-out)',
          }}
        />
      </svg>
      <span className="absolute text-xs font-semibold text-fg tabular-nums">
        {completed}/{total}
      </span>
    </div>
  )
}
