import { useCallback, useEffect, useRef, useState } from 'react'
import { Badge, Card, CardContent, CardHeader } from '../../components/ui'
import Icon from '../../components/Icon'

type Testimonial = {
  name: string
  role: string
  band: string
  quote: string
  /** Tailwind bg + fg classes for the initials circle */
  tint: string
}

const testimonials: Testimonial[] = [
  {
    name: 'Minh Anh',
    role: 'Sinh viên, Hà Nội',
    band: '6.5 → 7.5',
    quote:
      'Sau 3 tháng dùng IELTS Coach, tôi tăng 1 band Writing. AI chấm rất cụ thể, mỗi bài đều chỉ ra đâu là lỗi Task Response và Grammar. Trước đây tự học một mình rất mông lung.',
    tint: 'bg-teal-100 text-teal-800',
  },
  {
    name: 'Tuấn Dũng',
    role: 'Kỹ sư, TP.HCM',
    band: '5.5 → 7.0',
    quote:
      'Làm việc 8 tiếng/ngày, chỉ có 30 phút luyện IELTS mỗi tối. Adaptive Plan cho tôi đúng 3 task phù hợp mỗi ngày, không bị quá tải. Đã đạt 7.0 sau 4 tháng.',
    tint: 'bg-orange-100 text-orange-800',
  },
  {
    name: 'Thu Hà',
    role: 'Du học sinh tương lai, Đà Nẵng',
    band: '6.0 → 7.5',
    quote:
      'Vocab SRS là tính năng tôi thích nhất. 1500+ từ IELTS theo topic, học 20 từ/ngày, ôn lại đúng lúc cần. Đến ngày thi, từ nào cũng "nhớ như in".',
    tint: 'bg-sky-100 text-sky-800',
  },
  {
    name: 'Quang Huy',
    role: 'Nhân viên marketing, TP.HCM',
    band: '5.0 → 6.5',
    quote:
      'Tôi mất gốc tiếng Anh 10 năm. Bắt đầu lại từ band 5.0, coach AI kiên nhẫn chỉ lỗi cơ bản mà không phán xét. Sau 6 tháng tôi đã đạt 6.5 để đi du lịch nước ngoài.',
    tint: 'bg-pink-100 text-pink-800',
  },
  {
    name: 'Lan Phương',
    role: 'Giáo viên, Cần Thơ',
    band: '7.0 → 8.0',
    quote:
      'Đã có 7.0 nhưng muốn đạt 8.0 để xin học bổng. Writing feedback ở band cao rất chi tiết: nhấn mạnh cohesion và lexical resource, đúng những gì thi thật đòi hỏi.',
    tint: 'bg-violet-100 text-violet-800',
  },
]

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

const AUTO_MS = 6000

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

export default function Testimonials() {
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const reducedMotion = useRef(prefersReducedMotion())

  const goTo = useCallback((i: number) => {
    setIndex(((i % testimonials.length) + testimonials.length) % testimonials.length)
  }, [])
  const next = useCallback(() => goTo(index + 1), [index, goTo])
  const prev = useCallback(() => goTo(index - 1), [index, goTo])

  useEffect(() => {
    if (paused || reducedMotion.current) return
    const id = window.setInterval(() => {
      setIndex((i) => (i + 1) % testimonials.length)
    }, AUTO_MS)
    return () => window.clearInterval(id)
  }, [paused])

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'ArrowRight') {
      e.preventDefault()
      next()
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      prev()
    }
  }

  return (
    <section
      id="testimonials"
      className="bg-bg px-4 py-16 sm:px-6 sm:py-24"
      aria-labelledby="testimonials-heading"
    >
      <div className="mx-auto max-w-3xl">
        <h2
          id="testimonials-heading"
          className="mb-10 text-center text-3xl font-bold text-fg sm:text-4xl"
        >
          Học viên nói gì
        </h2>

        <div
          role="region"
          aria-roledescription="carousel"
          aria-label="Đánh giá học viên"
          tabIndex={0}
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
          onFocus={() => setPaused(true)}
          onBlur={() => setPaused(false)}
          onKeyDown={onKeyDown}
          className="relative rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <div className="relative min-h-[340px] sm:min-h-[300px]">
            {testimonials.map((t, i) => {
              const active = i === index
              return (
                <div
                  key={t.name}
                  role="group"
                  aria-roledescription="slide"
                  aria-label={`${i + 1} / ${testimonials.length}`}
                  aria-hidden={!active}
                  className={
                    active
                      ? 'relative opacity-100 transition-opacity duration-base ease-out-soft'
                      : 'pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-base ease-out-soft'
                  }
                >
                  <Card>
                    <CardHeader>
                      <div className="flex items-center gap-4">
                        <div
                          aria-hidden="true"
                          className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-border text-lg font-semibold ${t.tint}`}
                        >
                          {initialsOf(t.name)}
                        </div>
                        <div className="flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-fg">
                              {t.name}
                            </span>
                            <Badge variant="success">{t.band}</Badge>
                          </div>
                          <p className="text-sm text-muted-fg">{t.role}</p>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <blockquote className="text-base leading-relaxed text-fg sm:text-lg">
                        “{t.quote}”
                      </blockquote>
                    </CardContent>
                  </Card>
                </div>
              )
            })}
          </div>

          <button
            type="button"
            onClick={prev}
            aria-label="Xem đánh giá trước"
            className="absolute left-0 top-1/2 hidden -translate-x-12 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-surface-raised p-2 text-fg transition-colors hover:bg-surface md:flex"
          >
            <Icon name="ArrowLeft" size="md" />
          </button>
          <button
            type="button"
            onClick={next}
            aria-label="Xem đánh giá kế tiếp"
            className="absolute right-0 top-1/2 hidden -translate-y-1/2 translate-x-12 items-center justify-center rounded-full border border-border bg-surface-raised p-2 text-fg transition-colors hover:bg-surface md:flex"
          >
            <Icon name="ArrowRight" size="md" />
          </button>
        </div>

        <div className="mt-6 flex justify-center gap-2" role="tablist" aria-label="Chọn đánh giá">
          {testimonials.map((t, i) => (
            <button
              key={t.name}
              type="button"
              role="tab"
              aria-selected={i === index}
              aria-label={`Đi tới đánh giá ${i + 1}`}
              onClick={() => goTo(i)}
              className={
                i === index
                  ? 'h-2.5 w-6 rounded-full bg-primary transition-all duration-base'
                  : 'h-2.5 w-2.5 rounded-full bg-border transition-all duration-base hover:bg-muted-fg'
              }
            />
          ))}
        </div>
      </div>
    </section>
  )
}
