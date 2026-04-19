import { Link } from 'react-router-dom'
import Icon from '../../components/Icon'

type NavLink = {
  label: string
  href: string
  external?: boolean
  comingSoon?: boolean
}

const PRODUCT_LINKS: NavLink[] = [
  { label: 'Tính năng', href: '#value-props-heading' },
  { label: 'Giá', href: '#pricing' },
  { label: 'Đánh giá', href: '#testimonials' },
  { label: 'Câu hỏi thường gặp', href: '#faq' },
]

const COMPANY_LINKS: NavLink[] = [
  { label: 'Blog', href: '#', comingSoon: true },
]

const LEGAL_LINKS: NavLink[] = [
  { label: 'Điều khoản', href: '/terms' },
  { label: 'Chính sách riêng tư', href: '/privacy' },
]

const SOCIAL_LINKS: NavLink[] = [
  {
    label: 'GitHub',
    href: 'https://github.com/mario-noobs/ielts-bot',
    external: true,
  },
  {
    label: 'Telegram',
    href: 'https://t.me/ielts_coach_bot',
    external: true,
  },
]

const SUPPORT_EMAIL = 'support@ieltscoach.vn'

function ComingSoonPill() {
  return (
    <span className="ml-2 inline-flex items-center rounded-full bg-surface px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-fg">
      Sắp ra mắt
    </span>
  )
}

function FooterNavLink({ link }: { link: NavLink }) {
  const cls =
    'text-sm text-muted-fg transition-colors hover:text-fg focus-visible:outline-none focus-visible:underline focus-visible:text-fg'

  if (link.comingSoon) {
    return (
      <span
        aria-disabled="true"
        className="inline-flex items-center text-sm text-muted-fg/60 cursor-not-allowed"
      >
        {link.label}
        <ComingSoonPill />
      </span>
    )
  }
  if (link.external) {
    return (
      <a href={link.href} target="_blank" rel="noopener noreferrer" className={cls}>
        {link.label}
      </a>
    )
  }
  if (link.href.startsWith('#')) {
    return (
      <a href={link.href} className={cls}>
        {link.label}
      </a>
    )
  }
  return (
    <Link to={link.href} className={cls}>
      {link.label}
    </Link>
  )
}

export default function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer
      className="border-t border-border bg-bg px-4 py-12 sm:px-6"
      aria-labelledby="footer-heading"
    >
      <h2 id="footer-heading" className="sr-only">
        Thông tin chân trang
      </h2>
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-10 md:grid-cols-4">
          <div>
            <Link to="/" className="text-lg font-bold text-fg">
              IELTS Coach
            </Link>
            <p className="mt-3 text-sm leading-relaxed text-muted-fg">
              Luyện IELTS mỗi ngày, 20 phút. AI chấm Writing theo rubric Cambridge.
            </p>
            {/* Language switch placeholder — M7 wires react-i18next */}
            <div className="mt-4">
              <span
                aria-disabled="true"
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs text-muted-fg cursor-not-allowed"
              >
                VN
                <span className="text-muted-fg/50">· EN</span>
                <ComingSoonPill />
              </span>
            </div>
          </div>

          <nav aria-label="Sản phẩm">
            <h3 className="text-sm font-semibold text-fg">Sản phẩm</h3>
            <ul className="mt-3 flex flex-col gap-2">
              {PRODUCT_LINKS.map((l) => (
                <li key={l.label}>
                  <FooterNavLink link={l} />
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Liên hệ và công ty">
            <h3 className="text-sm font-semibold text-fg">Liên hệ</h3>
            <ul className="mt-3 flex flex-col gap-2">
              <li>
                <a
                  href={`mailto:${SUPPORT_EMAIL}`}
                  className="inline-flex items-center gap-1.5 text-sm text-muted-fg transition-colors hover:text-fg focus-visible:text-fg"
                >
                  <Icon name="Mail" size="sm" variant="muted" />
                  {SUPPORT_EMAIL}
                </a>
              </li>
              {COMPANY_LINKS.map((l) => (
                <li key={l.label}>
                  <FooterNavLink link={l} />
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Pháp lý và liên kết">
            <h3 className="text-sm font-semibold text-fg">Pháp lý</h3>
            <ul className="mt-3 flex flex-col gap-2">
              {LEGAL_LINKS.map((l) => (
                <li key={l.label}>
                  <FooterNavLink link={l} />
                </li>
              ))}
            </ul>
            <h3 className="mt-6 text-sm font-semibold text-fg">Kết nối</h3>
            <ul className="mt-3 flex flex-col gap-2">
              {SOCIAL_LINKS.map((l) => (
                <li key={l.label}>
                  <FooterNavLink link={l} />
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <div className="mt-10 border-t border-border pt-6">
          <p className="text-sm text-muted-fg">
            © {year} IELTS Coach. Luyện IELTS thông minh.
          </p>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-fg/70">
            Không liên kết với Cambridge Assessment English, IDP, hoặc British Council.
            Điểm chấm bởi AI mang tính tham khảo, không thay thế điểm thi chính thức.
          </p>
        </div>
      </div>
    </footer>
  )
}
