import Icon from './Icon'

interface Props {
  band: number
  target: number
  size?: number
}

export default function BandRing({ band, target, size = 200 }: Props) {
  const stroke = 14
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(1, (band - 4.0) / 5.0))
  const dash = c * pct
  const targetPct = Math.max(0, Math.min(1, (target - 4.0) / 5.0))
  const targetAngle = -90 + targetPct * 360

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
          stroke="url(#bandGradient)"
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
          fill="none"
          className="transition-[stroke-dasharray] duration-700"
        />
        <defs>
          <linearGradient id="bandGradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#ec4899" />
          </linearGradient>
        </defs>
        {/* Target marker */}
        <g
          style={{
            transformOrigin: `${size / 2}px ${size / 2}px`,
            transform: `rotate(${targetAngle}deg)`,
          }}
        >
          <line
            x1={size / 2}
            y1={stroke / 2 - 2}
            x2={size / 2}
            y2={stroke + 4}
            stroke="#10b981"
            strokeWidth={3}
          />
        </g>
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-[10px] uppercase tracking-wide text-gray-500">
          Overall Band
        </span>
        <span className="text-5xl font-bold text-gray-900">
          {band.toFixed(1)}
        </span>
        <span className="text-xs text-emerald-600 font-medium mt-1 inline-flex items-center gap-1">
          <Icon name="Target" size="sm" variant="success" label="Band mục tiêu" />
          {target.toFixed(1)}
        </span>
      </div>
    </div>
  )
}
