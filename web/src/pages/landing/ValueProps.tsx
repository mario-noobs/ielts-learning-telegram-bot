import { BookOpen, PenLine, Target } from 'lucide-react'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from '../../components/ui'

const PROPS = [
  {
    icon: BookOpen,
    title: 'SRS vocab thông minh',
    body: 'Thuật toán SM-2 ghi nhớ 1500+ từ IELTS theo band của bạn.',
  },
  {
    icon: PenLine,
    title: 'AI writing tức thì',
    body: 'Chấm theo 4 tiêu chí Cambridge: Task Response, Coherence, Lexical, Grammar.',
  },
  {
    icon: Target,
    title: 'Adaptive plan',
    body: 'Coach AI đề xuất task hàng ngày dựa trên điểm yếu của bạn.',
  },
] as const

export default function ValueProps() {
  return (
    <section
      aria-labelledby="value-props-heading"
      className="mx-auto w-full max-w-6xl px-4 py-12 md:px-6 md:py-16"
    >
      <h2 id="value-props-heading" className="sr-only">
        Tính năng chính
      </h2>
      <div className="grid gap-4 md:grid-cols-3 md:gap-6">
        {PROPS.map(({ icon: Icon, title, body }) => (
          <Card key={title} className="p-6">
            <CardHeader className="p-0">
              <Icon className="h-8 w-8 text-primary" aria-hidden="true" />
              <CardTitle className="mt-4 text-lg">{title}</CardTitle>
              <CardDescription className="mt-2 leading-relaxed">
                {body}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </section>
  )
}
