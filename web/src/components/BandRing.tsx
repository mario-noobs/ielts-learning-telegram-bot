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
          className="stroke-border"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className="stroke-primary transition-[stroke-dasharray] duration-700"
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
          fill="none"
        />
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
            className="stroke-success"
            strokeWidth={3}
          />
        </g>
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-[10px] uppercase tracking-wide text-muted-fg">
          Overall Band
        </span>
        <span className="text-5xl font-bold text-fg">
          {band.toFixed(1)}
        </span>
        <span className="text-xs text-success font-medium mt-1 inline-flex items-center gap-1">
          <Icon name="Target" size="sm" variant="success" label="Band mục tiêu" />
          {target.toFixed(1)}
        </span>
      </div>
    </div>
  )
}
