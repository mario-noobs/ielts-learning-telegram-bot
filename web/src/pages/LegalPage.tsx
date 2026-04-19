import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Badge } from '../components/ui'

type Props = { kind: 'privacy' | 'terms' }

const CONTENT = {
  privacy: {
    title: 'Chính sách riêng tư',
    intro:
      'IELTS Coach tôn trọng quyền riêng tư của bạn. Tài liệu này mô tả ngắn gọn dữ liệu được thu thập và cách chúng tôi xử lý.',
    sections: [
      {
        h: 'Dữ liệu thu thập',
        p: 'Thông tin tài khoản (email, tên), bài viết Writing, tiến độ học tập. Không thu thập dữ liệu sinh trắc hoặc vị trí chính xác.',
      },
      {
        h: 'Chia sẻ với bên thứ ba',
        p: 'Chúng tôi không bán dữ liệu. Firebase (xác thực) và Google Gemini (chấm AI) xử lý dữ liệu theo thỏa thuận dịch vụ riêng.',
      },
      {
        h: 'Quyền của bạn',
        p: 'Bạn có thể xuất hoặc xóa dữ liệu bất kỳ lúc nào trong Cài đặt → Tài khoản.',
      },
    ],
  },
  terms: {
    title: 'Điều khoản sử dụng',
    intro:
      'Bằng việc sử dụng IELTS Coach, bạn đồng ý các điều khoản dưới đây. Chúng tôi có thể cập nhật; người dùng sẽ được thông báo qua email.',
    sections: [
      {
        h: 'Sử dụng hợp pháp',
        p: 'Không dùng dịch vụ cho mục đích vi phạm pháp luật hoặc quấy rối người khác. Không tự động gửi spam tới hệ thống chấm AI.',
      },
      {
        h: 'Tính chính xác AI',
        p: 'Điểm chấm Writing bởi AI mang tính tham khảo, không thay thế điểm thi IELTS chính thức từ IDP/British Council.',
      },
      {
        h: 'Thanh toán và hủy',
        p: 'Gói Pro tính phí hàng tháng. Bạn có thể hủy bất cứ lúc nào; không hoàn tiền phần kỳ đã sử dụng.',
      },
    ],
  },
} as const

export default function LegalPage({ kind }: Props) {
  const { t } = useTranslation('common')
  const c = CONTENT[kind]

  useEffect(() => {
    const previous = document.title
    document.title = `${c.title} — IELTS Coach`
    return () => {
      document.title = previous
    }
  }, [c.title])

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <nav
        aria-label={t('nav.legalNav')}
        className="mx-auto flex w-full max-w-4xl items-center justify-between px-4 py-4 md:px-6"
      >
        <Link to="/" className="flex items-center gap-2 text-lg font-bold text-fg">
          {t('brand.name')}
          <Badge variant="primary" aria-label={t('auth.brandBetaLabel')}>
            {t('brand.beta')}
          </Badge>
        </Link>
        <Link
          to="/"
          className="rounded-xl px-3 py-2 text-sm font-medium text-muted-fg hover:bg-surface hover:text-fg"
        >
          ← {t('actions.goToDashboard')}
        </Link>
      </nav>
      <main className="mx-auto w-full max-w-3xl px-4 py-10 md:px-6 md:py-16">
        <h1 className="text-3xl font-bold text-fg sm:text-4xl">{c.title}</h1>
        <p className="mt-4 text-base leading-relaxed text-muted-fg">{c.intro}</p>
        <div className="mt-10 flex flex-col gap-8">
          {c.sections.map((s) => (
            <section key={s.h}>
              <h2 className="text-xl font-semibold text-fg">{s.h}</h2>
              <p className="mt-2 leading-relaxed text-muted-fg">{s.p}</p>
            </section>
          ))}
        </div>
        <p className="mt-12 text-sm text-muted-fg">
          Cập nhật lần cuối: {new Date().toISOString().slice(0, 10)}. Có câu hỏi?
          Liên hệ support qua Telegram bot.
        </p>
      </main>
    </div>
  )
}
