import { TrendPoint } from '../lib/progress'

const SERIES: { key: keyof TrendPoint; label: string; color: string }[] = [
  { key: 'overall_band', label: 'Overall', color: '#4f46e5' },
  { key: 'vocabulary_band', label: 'Vocabulary', color: '#f59e0b' },
  { key: 'writing_band', label: 'Writing', color: '#10b981' },
  { key: 'listening_band', label: 'Listening', color: '#ec4899' },
]

function formatDateShort(iso: string): string {
  const [, m, d] = iso.split('-')
  if (!m || !d) return iso
  return `${parseInt(d, 10)}/${parseInt(m, 10)}`
}

export default function BandTrendChart({
  trend,
  target,
}: {
  trend: TrendPoint[]
  target: number
}) {
  const width = 640
  const height = 260
  const padL = 32
  const padR = 12
  const padT = 16
  const padB = 36

  if (trend.length === 0) {
    return (
      <div className="h-52 flex items-center justify-center text-sm text-gray-500 bg-gray-50 rounded-xl border border-gray-200">
        Chưa có dữ liệu — hoàn thành vài bài để xem xu hướng.
      </div>
    )
  }

  if (trend.length === 1) {
    const only = trend[0]
    return (
      <div className="h-52 flex items-center justify-center text-sm text-gray-500 bg-gray-50 rounded-xl border border-gray-200">
        Điểm đầu tiên hôm nay: Overall {only.overall_band.toFixed(1)}. Quay lại
        ngày mai để vẽ xu hướng.
      </div>
    )
  }

  const yMin = 4.0
  const yMax = 9.0
  const n = trend.length
  const xStep = (width - padL - padR) / Math.max(1, n - 1)
  const y = (v: number) =>
    padT + (1 - (v - yMin) / (yMax - yMin)) * (height - padT - padB)

  const targetY = y(target)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-3 space-y-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
        {/* Grid */}
        {[4, 5, 6, 7, 8, 9].map((v) => (
          <g key={v}>
            <line
              x1={padL}
              x2={width - padR}
              y1={y(v)}
              y2={y(v)}
              stroke="#f1f5f9"
              strokeWidth={1}
            />
            <text
              x={padL - 4}
              y={y(v) + 3}
              fontSize="9"
              textAnchor="end"
              fill="#94a3b8"
            >
              {v}
            </text>
          </g>
        ))}

        {/* Target line */}
        <line
          x1={padL}
          x2={width - padR}
          y1={targetY}
          y2={targetY}
          stroke="#10b981"
          strokeWidth={1.5}
          strokeDasharray="4 4"
        />
        <text
          x={width - padR}
          y={targetY - 4}
          fontSize="9"
          textAnchor="end"
          fill="#059669"
        >
          Target {target.toFixed(1)}
        </text>

        {/* X-axis labels (first, middle, last) */}
        {[0, Math.floor(n / 2), n - 1].map((i) => (
          <text
            key={i}
            x={padL + i * xStep}
            y={height - padB + 14}
            fontSize="9"
            textAnchor="middle"
            fill="#475569"
          >
            {formatDateShort(trend[i].date)}
          </text>
        ))}

        {/* Series */}
        {SERIES.map((s) => {
          const path = trend
            .map((p, i) => {
              const vRaw = Number(p[s.key]) || 0
              const v = Math.max(yMin, Math.min(yMax, vRaw))
              return `${i === 0 ? 'M' : 'L'} ${padL + i * xStep} ${y(v)}`
            })
            .join(' ')
          return (
            <path
              key={s.key}
              d={path}
              fill="none"
              stroke={s.color}
              strokeWidth={s.key === 'overall_band' ? 2.5 : 1.5}
              opacity={s.key === 'overall_band' ? 1 : 0.85}
            />
          )
        })}
      </svg>

      <div className="flex flex-wrap gap-3 text-xs">
        {SERIES.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-2 rounded-sm"
              style={{ background: s.color }}
            />
            <span className="text-gray-700">{s.label}</span>
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-[2px] border-t border-dashed border-emerald-500" />
          <span className="text-gray-700">Target</span>
        </span>
      </div>
    </div>
  )
}
