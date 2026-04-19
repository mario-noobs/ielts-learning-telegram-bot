import { Link } from 'react-router-dom'
import Icon, { IconName } from '../../components/Icon'
import { track } from '../../lib/analytics'

type ActionId = 'writing' | 'flashcards'

type Action = {
  id: ActionId
  to: string
  icon: IconName
  title: string
  hint: string
}

const ACTIONS: Action[] = [
  {
    id: 'writing',
    to: '/write',
    icon: 'PenLine',
    title: 'Luyện Writing hôm nay',
    hint: 'Nộp bài Task 1 hoặc Task 2, nhận AI feedback theo 4 tiêu chí.',
  },
  {
    id: 'flashcards',
    to: '/review',
    icon: 'RotateCcw',
    title: 'Ôn flashcard',
    hint: 'Review các từ đến hạn theo thuật toán SM-2.',
  },
]

export default function QuickActions() {
  return (
    <section aria-labelledby="quick-actions-heading">
      <h2 id="quick-actions-heading" className="sr-only">
        Hành động nhanh
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4">
        {ACTIONS.map((a) => (
          <Link
            key={a.id}
            to={a.to}
            onClick={() => track('dashboard_quick_action_click', { action: a.id })}
            className="group flex items-start gap-3 rounded-2xl border border-border bg-surface-raised p-4 transition-colors hover:border-primary/40 hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Icon name={a.icon} size="lg" variant="primary" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-fg">{a.title}</p>
              <p className="mt-0.5 text-sm leading-relaxed text-muted-fg">
                {a.hint}
              </p>
            </div>
            <Icon
              name="ArrowRight"
              size="md"
              variant="muted"
              className="mt-1 shrink-0 transition-transform duration-base ease-out-soft group-hover:translate-x-0.5 group-hover:text-primary"
            />
          </Link>
        ))}
      </div>
    </section>
  )
}
