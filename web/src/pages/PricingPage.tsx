import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../components/ui'
import Pricing from './landing/Pricing'
import FAQ from './landing/FAQ'
import Footer from './landing/Footer'

export default function PricingPage() {
  useEffect(() => {
    const previous = document.title
    document.title = 'Gói & giá — IELTS Coach'
    return () => {
      document.title = previous
    }
  }, [])

  return (
    <div className="min-h-dvh overflow-x-hidden bg-bg text-fg">
      <nav
        aria-label="Điều hướng"
        className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 md:px-6"
      >
        <Link to="/" className="flex items-center gap-2 text-lg font-bold text-fg">
          IELTS Coach
          <Badge variant="primary" aria-label="Phiên bản thử nghiệm">
            Beta
          </Badge>
        </Link>
        <Link
          to="/"
          className="rounded-xl px-3 py-2 text-sm font-medium text-muted-fg hover:bg-surface hover:text-fg"
        >
          ← Về trang chủ
        </Link>
      </nav>
      <main>
        <Pricing />
        <FAQ />
      </main>
      <Footer />
    </div>
  )
}
