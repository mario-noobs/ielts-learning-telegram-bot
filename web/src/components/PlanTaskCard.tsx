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
      className={`bg-surface-raised rounded-xl border p-3 flex items-center gap-3 transition-colors duration-base ${
        completed
          ? 'border-success/40 bg-success/5'
          : 'border-border hover:border-primary/40'
      }`}
    >
      {/* Checkbox — 44×44 touch target, visual circle 32×32 centered */}
      <button
        type="button"
        onClick={() => !busy && !completed && onToggle(activity.id)}
        disabled={busy || completed}
        aria-label={completed ? `${activity.title} — đã hoàn thành` : `Đánh dấu hoàn thành: ${activity.title}`}
        aria-pressed={completed}
        className="min-w-[44px] min-h-[44px] shrink-0 grid place-items-center rounded-lg disabled:cursor-default"
      >
        <span
          className={`w-8 h-8 rounded-full border-2 flex items-center justify-center transition-colors duration-base ${
            completed
              ? 'bg-success border-success text-white'
              : 'border-border bg-surface-raised group-hover:border-primary'
          }`}
          aria-hidden
        >
          {completed && (
            <svg viewBox="0 0 20 20" className="w-4 h-4 fill-current">
              <path d="M7.3 13.3l-3.6-3.6 1.4-1.4 2.2 2.2 5.6-5.6 1.4 1.4z" />
            </svg>
          )}
        </span>
      </button>

      <button
        type="button"
        onClick={() => navigate(activity.route)}
        aria-label={`Mở ${activity.title}`}
        className="flex-1 text-left min-w-0 min-h-[44px] rounded-lg py-1"
      >
        <div className="flex items-center gap-2">
          <Icon name={meta.icon} size="md" variant={completed ? 'muted' : 'primary'} />
          <p
            className={`font-semibold truncate ${
              completed ? 'text-muted-fg line-through' : 'text-fg'
            }`}
          >
            {activity.title}
          </p>
        </div>
        <p className="text-xs text-muted-fg mt-0.5 truncate">
          {activity.description}
        </p>
        <p className="text-[11px] text-muted-fg mt-0.5 inline-flex items-center gap-1">
          <Icon name="Clock" size="sm" variant="muted" /> {activity.estimated_minutes} phút
        </p>
      </button>

      <Icon name="ChevronRight" size="md" variant="primary" className="shrink-0" />
    </div>
  )
}
