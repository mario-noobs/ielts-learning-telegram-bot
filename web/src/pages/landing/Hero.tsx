import { Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { Badge, Button } from '../../components/ui'
import LanguageSwitcher from '../../components/LanguageSwitcher'
import { track } from '../../lib/analytics'

const SOCIAL_PROOF_COUNT = 2000

export default function Hero() {
  const { signInWithGoogle } = useAuth()

  const handleSignup = async () => {
    track('landing_cta_clicked', { cta: 'signup' })
    try {
      await signInWithGoogle()
    } catch {
      /* popup closed / network — silent; user retries */
    }
  }

  const handleDemo = () => {
    track('landing_cta_clicked', { cta: 'demo' })
  }

  return (
    <>
      <nav
        aria-label="Landing navigation"
        className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 md:px-6"
      >
        <Link to="/" className="flex items-center gap-2 text-lg font-bold text-fg">
          IELTS Coach
          <Badge variant="primary" aria-label="Phiên bản thử nghiệm">
            Beta
          </Badge>
        </Link>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <Link
            to="/login"
            className="rounded-xl px-3 py-2 text-sm font-medium text-fg hover:bg-surface"
          >
            Đăng nhập
          </Link>
        </div>
      </nav>

      <section
        aria-labelledby="hero-headline"
        className="mx-auto w-full max-w-6xl px-4 py-10 md:px-6 md:py-20"
      >
        <div className="grid items-center gap-10 md:grid-cols-2 md:gap-12">
          <div>
            <h1
              id="hero-headline"
              className="text-4xl font-bold leading-tight text-fg md:text-5xl"
            >
              Từ 6.0 lên 7.5 trong 90 ngày
            </h1>
            <p className="mt-4 text-lg leading-relaxed text-muted-fg md:text-xl">
              Luyện IELTS mỗi ngày, 20 phút.
              <br />
              AI chấm Writing, Speaking theo band mục tiêu.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button
                variant="primary"
                size="lg"
                onClick={handleSignup}
                aria-label="Bắt đầu miễn phí — đăng ký bằng Google"
              >
                Bắt đầu miễn phí
              </Button>
              <Button variant="ghost" size="lg" asChild>
                <a href="#sample-screens" onClick={handleDemo}>
                  Xem demo
                </a>
              </Button>
            </div>

            {SOCIAL_PROOF_COUNT >= 2000 && (
              <p className="mt-6 text-sm text-muted-fg">
                Đã có 2.000+ học viên đang luyện IELTS
              </p>
            )}
          </div>

          <div aria-hidden="true" className="hidden md:block">
            <HeroMockup />
          </div>
        </div>
      </section>
    </>
  )
}

function HeroMockup() {
  return (
    <div className="relative mx-auto aspect-[4/5] w-full max-w-sm rounded-3xl border border-border bg-surface-raised p-6 shadow-lg">
      <div className="flex items-center justify-between">
        <div className="h-3 w-20 rounded-full bg-primary/20" />
        <div className="h-3 w-8 rounded-full bg-accent/30" />
      </div>
      <div className="mt-6 space-y-3">
        <div className="h-24 rounded-2xl bg-primary/10" />
        <div className="h-4 w-3/4 rounded-full bg-muted-fg/20" />
        <div className="h-4 w-1/2 rounded-full bg-muted-fg/20" />
      </div>
      <div className="mt-6 grid grid-cols-3 gap-2">
        <div className="h-16 rounded-xl bg-surface" />
        <div className="h-16 rounded-xl bg-surface" />
        <div className="h-16 rounded-xl bg-surface" />
      </div>
      <div className="mt-6 h-10 rounded-xl bg-primary" />
    </div>
  )
}
