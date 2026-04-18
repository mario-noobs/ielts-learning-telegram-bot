interface Props {
  completed: number
  total: number
  size?: number
}

export default function ProgressRing({ completed, total, size = 64 }: Props) {
  const safeTotal = Math.max(1, total)
  const pct = Math.min(1, completed / safeTotal)
  const stroke = 6
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const dash = c * pct

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="#e5e7eb"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="#4f46e5"
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
          fill="none"
          className="transition-[stroke-dasharray] duration-500"
        />
      </svg>
      <span className="absolute text-xs font-semibold text-gray-700">
        {completed}/{total}
      </span>
    </div>
  )
}
