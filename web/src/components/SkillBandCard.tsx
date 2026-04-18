import Icon, { IconName } from './Icon'

interface Props {
  iconName: IconName
  label: string
  band: number
  target: number
  delta?: number
  subline?: string
  placeholder?: boolean
}

export default function SkillBandCard({
  iconName,
  label,
  band,
  target,
  delta = 0,
  subline,
  placeholder,
}: Props) {
  const pct = Math.max(0, Math.min(1, (band - 4.0) / 5.0))
  const trendIconName: IconName =
    delta > 0 ? 'TrendingUp' : delta < 0 ? 'TrendingDown' : 'Minus'
  const trendVariant: 'success' | 'danger' | 'muted' =
    delta > 0 ? 'success' : delta < 0 ? 'danger' : 'muted'

  return (
    <div
      className={`bg-white rounded-xl border p-4 ${
        placeholder ? 'border-dashed border-gray-300' : 'border-gray-200'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon name={iconName} size="lg" variant="primary" />
          <p className="font-semibold text-gray-900">{label}</p>
        </div>
        {placeholder && (
          <span className="text-[10px] font-medium text-gray-500 bg-gray-100 rounded-full px-2 py-0.5">
            Sắp ra mắt
          </span>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-3xl font-bold text-gray-900">
          {placeholder ? '—' : band.toFixed(1)}
        </span>
        {!placeholder && (
          <span className="text-xs font-medium inline-flex items-center gap-1">
            <Icon name={trendIconName} size="sm" variant={trendVariant} />
            <span className={trendVariant === 'success' ? 'text-success' : trendVariant === 'danger' ? 'text-danger' : 'text-muted-fg'}>
              {Math.abs(delta).toFixed(1)}
            </span>
          </span>
        )}
        <span className="text-xs text-gray-500 ml-auto">
          mục tiêu {target.toFixed(1)}
        </span>
      </div>
      <div className="mt-2 w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 to-pink-500 transition-all duration-500"
          style={{ width: placeholder ? '0%' : `${pct * 100}%` }}
        />
      </div>
      {subline && (
        <p className="text-xs text-gray-500 mt-2">{subline}</p>
      )}
    </div>
  )
}
