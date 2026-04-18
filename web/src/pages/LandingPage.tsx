import { useEffect } from 'react'
import Hero from './landing/Hero'
import ValueProps from './landing/ValueProps'

export default function LandingPage() {
  useEffect(() => {
    const previous = document.title
    document.title = 'IELTS Coach — Luyện IELTS mỗi ngày'
    return () => {
      document.title = previous
    }
  }, [])

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-xl focus:bg-surface-raised focus:px-4 focus:py-2 focus:text-fg"
      >
        Bỏ qua tới nội dung chính
      </a>
      <main id="main">
        <Hero />
        <ValueProps />
        <section id="sample-screens" aria-hidden="true" />
        <section id="pricing" aria-hidden="true" />
        <section id="faq" aria-hidden="true" />
      </main>
    </div>
  )
}
