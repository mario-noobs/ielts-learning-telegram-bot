import { useNavigate } from 'react-router-dom'
import Icon from './Icon'
import { PlanActivity, TYPE_META } from '../lib/plan'

interface Props {
  activity: PlanActivity
  onToggle: (id: string) => void
  busy?: boolean
}

export default function PlanTaskCard({ activity, onToggle, busy }: Props) {
  const navigate = useNavigate()
  const meta = TYPE_META[activity.type]

  const completed = activity.completed

  return (
    <div
      className={`bg-white rounded-xl border p-3 flex items-center gap-3 transition-all ${
        completed
          ? 'border-green-400 bg-green-50/40'
          : 'border-gray-200 hover:border-indigo-300 hover:shadow-sm'
      }`}
    >
      <button
        type="button"
        onClick={() => !busy && !completed && onToggle(activity.id)}
        disabled={busy || completed}
        aria-label={completed ? 'Đã hoàn thành' : 'Đánh dấu hoàn thành'}
        className={`w-8 h-8 shrink-0 rounded-full border-2 flex items-center justify-center transition-all ${
          completed
            ? 'bg-green-500 border-green-500 text-white scale-100'
            : 'border-gray-300 hover:border-indigo-400 bg-white'
        }`}
      >
        {completed && (
          <svg viewBox="0 0 20 20" className="w-4 h-4 fill-current">
            <path d="M7.3 13.3l-3.6-3.6 1.4-1.4 2.2 2.2 5.6-5.6 1.4 1.4z" />
          </svg>
        )}
      </button>

      <button
        type="button"
        onClick={() => navigate(activity.route)}
        className="flex-1 text-left min-w-0"
      >
        <div className="flex items-center gap-2">
          <Icon name={meta.icon} size="md" variant={completed ? 'muted' : 'primary'} />
          <p
            className={`font-semibold truncate ${
              completed ? 'text-gray-500 line-through' : 'text-gray-900'
            }`}
          >
            {activity.title}
          </p>
        </div>
        <p className="text-xs text-gray-500 mt-0.5 truncate">
          {activity.description}
        </p>
        <p className="text-[11px] text-gray-400 mt-0.5 inline-flex items-center gap-1">
          <Icon name="Clock" size="sm" variant="muted" /> {activity.estimated_minutes} phút
        </p>
      </button>

      <Icon name="ChevronRight" size="md" variant="primary" className="shrink-0" />
    </div>
  )
}
