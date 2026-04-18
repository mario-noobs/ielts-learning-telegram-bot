import { Task1Visualization } from '../lib/writing'

const PALETTE = ['#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

function computeRange(values: number[], viz: Task1Visualization) {
  const min = viz.y_min ?? Math.min(0, ...values)
  const max = viz.y_max ?? Math.max(...values, min + 1)
  return { min, max: max === min ? min + 1 : max }
}

function LineChart({ viz }: { viz: Task1Visualization }) {
  const width = 640
  const height = 280
  const padL = 44
  const padR = 16
  const padT = 20
  const padB = 44
  const allValues = viz.series.flatMap((s) => s.values)
  const { min, max } = computeRange(allValues, viz)
  const n = viz.x_labels.length
  const xStep = n > 1 ? (width - padL - padR) / (n - 1) : 0

  const y = (v: number) =>
    padT + (1 - (v - min) / (max - min)) * (height - padT - padB)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => {
        const val = min + t * (max - min)
        const yy = y(val)
        return (
          <g key={t}>
            <line
              x1={padL}
              x2={width - padR}
              y1={yy}
              y2={yy}
              stroke="#e5e7eb"
              strokeWidth={1}
            />
            <text x={padL - 6} y={yy + 4} fontSize="10" textAnchor="end" fill="#6b7280">
              {val.toFixed(val >= 100 ? 0 : 1)}
            </text>
          </g>
        )
      })}
      {viz.x_labels.map((lbl, i) => (
        <text
          key={i}
          x={padL + i * xStep}
          y={height - padB + 16}
          fontSize="10"
          textAnchor="middle"
          fill="#374151"
        >
          {lbl}
        </text>
      ))}
      {viz.series.map((s, si) => {
        const color = PALETTE[si % PALETTE.length]
        const d = s.values
          .map((v, i) => `${i === 0 ? 'M' : 'L'} ${padL + i * xStep} ${y(v)}`)
          .join(' ')
        return (
          <g key={si}>
            <path d={d} fill="none" stroke={color} strokeWidth={2} />
            {s.values.map((v, i) => (
              <circle
                key={i}
                cx={padL + i * xStep}
                cy={y(v)}
                r={3}
                fill={color}
              />
            ))}
          </g>
        )
      })}
      {viz.y_axis_label && (
        <text
          x={12}
          y={padT - 6}
          fontSize="10"
          fill="#374151"
        >
          {viz.y_axis_label}
        </text>
      )}
      {viz.x_axis_label && (
        <text
          x={width / 2}
          y={height - 6}
          fontSize="10"
          textAnchor="middle"
          fill="#374151"
        >
          {viz.x_axis_label}
        </text>
      )}
    </svg>
  )
}

function BarChart({ viz }: { viz: Task1Visualization }) {
  const width = 640
  const height = 280
  const padL = 44
  const padR = 16
  const padT = 20
  const padB = 44
  const allValues = viz.series.flatMap((s) => s.values)
  const { min, max } = computeRange(allValues, viz)
  const n = viz.x_labels.length
  const groupWidth = (width - padL - padR) / Math.max(1, n)
  const seriesCount = viz.series.length
  const barWidth = Math.max(4, (groupWidth * 0.8) / Math.max(1, seriesCount))

  const y = (v: number) =>
    padT + (1 - (v - min) / (max - min)) * (height - padT - padB)
  const zeroY = y(Math.max(0, min))

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => {
        const val = min + t * (max - min)
        const yy = y(val)
        return (
          <g key={t}>
            <line
              x1={padL}
              x2={width - padR}
              y1={yy}
              y2={yy}
              stroke="#e5e7eb"
              strokeWidth={1}
            />
            <text x={padL - 6} y={yy + 4} fontSize="10" textAnchor="end" fill="#6b7280">
              {val.toFixed(val >= 100 ? 0 : 1)}
            </text>
          </g>
        )
      })}
      {viz.x_labels.map((lbl, i) => (
        <text
          key={i}
          x={padL + groupWidth * (i + 0.5)}
          y={height - padB + 16}
          fontSize="10"
          textAnchor="middle"
          fill="#374151"
        >
          {lbl}
        </text>
      ))}
      {viz.series.map((s, si) =>
        s.values.map((v, i) => {
          const groupLeft = padL + groupWidth * i + (groupWidth * 0.1)
          const x = groupLeft + si * barWidth
          const top = y(v)
          return (
            <rect
              key={`${si}-${i}`}
              x={x}
              y={Math.min(top, zeroY)}
              width={barWidth - 1}
              height={Math.abs(top - zeroY)}
              fill={PALETTE[si % PALETTE.length]}
            />
          )
        })
      )}
    </svg>
  )
}

function PieChart({ viz }: { viz: Task1Visualization }) {
  const size = 260
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 8
  const total = viz.slices.reduce((sum, s) => sum + s.value, 0) || 1
  let angle = -Math.PI / 2
  const arcs = viz.slices.map((s, i) => {
    const slice = (s.value / total) * Math.PI * 2
    const x1 = cx + r * Math.cos(angle)
    const y1 = cy + r * Math.sin(angle)
    const endAngle = angle + slice
    const x2 = cx + r * Math.cos(endAngle)
    const y2 = cy + r * Math.sin(endAngle)
    const large = slice > Math.PI ? 1 : 0
    const path = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`
    angle = endAngle
    return { path, color: PALETTE[i % PALETTE.length], slice: s }
  })
  return (
    <div className="flex flex-col sm:flex-row items-center gap-6">
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        {arcs.map((a, i) => (
          <path key={i} d={a.path} fill={a.color} stroke="white" strokeWidth={1} />
        ))}
      </svg>
      <ul className="text-sm space-y-1">
        {arcs.map((a, i) => (
          <li key={i} className="flex items-center gap-2">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ background: a.color }}
            />
            <span className="text-gray-800">{a.slice.label}</span>
            <span className="text-gray-500 ml-auto">{a.slice.value}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function DataTable({ viz }: { viz: Task1Visualization }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            {viz.table_headers.map((h, i) => (
              <th
                key={i}
                className="text-left border-b-2 border-gray-300 px-3 py-2 font-semibold"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {viz.table_rows.map((row, ri) => (
            <tr key={ri} className="border-b border-gray-100">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Legend({ viz }: { viz: Task1Visualization }) {
  if (viz.series.length === 0) return null
  return (
    <div className="flex flex-wrap gap-3 text-xs mt-2">
      {viz.series.map((s, i) => (
        <span key={i} className="flex items-center gap-1.5">
          <span
            className="inline-block w-3 h-3 rounded-sm"
            style={{ background: PALETTE[i % PALETTE.length] }}
          />
          <span className="text-gray-700">{s.name}</span>
        </span>
      ))}
    </div>
  )
}

export default function TaskVisualization({ viz }: { viz: Task1Visualization }) {
  const renderBody = () => {
    switch (viz.chart_type) {
      case 'line':
        return <LineChart viz={viz} />
      case 'bar':
        return <BarChart viz={viz} />
      case 'pie':
        return <PieChart viz={viz} />
      case 'table':
        return <DataTable viz={viz} />
    }
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-2">
      {viz.title && (
        <h3 className="text-sm font-semibold text-gray-900">{viz.title}</h3>
      )}
      {renderBody()}
      {viz.chart_type !== 'pie' && viz.chart_type !== 'table' && <Legend viz={viz} />}
    </div>
  )
}
