import { greetingFor } from '../../lib/plan'

interface Props {
  name: string
}

const MOTIVATIONAL_LINES = [
  'Mỗi ngày luyện tập đưa bạn gần hơn một chút đến mục tiêu.',
  '20 phút hôm nay hơn 2 giờ cuối tuần.',
  'Tiến bộ không phải là điều kì diệu — nó là thói quen.',
  'Viết một câu tốt hơn còn giá trị hơn chục câu vội.',
  'Bài luyện nhỏ hôm nay là band cao trong ngày thi.',
]

function dayOfYear(date: Date): number {
  const start = new Date(date.getFullYear(), 0, 0)
  const diff = date.getTime() - start.getTime()
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

export default function DashboardGreeting({ name }: Props) {
  const now = new Date()
  const greeting = greetingFor(now)
  const line = MOTIVATIONAL_LINES[dayOfYear(now) % MOTIVATIONAL_LINES.length]
  const firstName = name.split(/\s+/).slice(-1)[0] || name

  return (
    <section
      aria-labelledby="dashboard-greeting-heading"
      className="bg-gradient-to-br from-primary to-primary-hover rounded-2xl p-6 text-primary-fg shadow-md"
    >
      <p className="text-sm opacity-90">{greeting},</p>
      <h1
        id="dashboard-greeting-heading"
        className="mt-1 text-2xl font-bold md:text-3xl"
      >
        {firstName}! <span aria-hidden="true">👋</span>
      </h1>
      <p className="mt-3 text-sm leading-relaxed text-primary-fg/90 md:text-base">
        {line}
      </p>
    </section>
  )
}
