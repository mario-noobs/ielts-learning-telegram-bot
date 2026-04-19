import Icon from '../../components/Icon'

type QA = { q: string; a: string }

const FAQS: QA[] = [
  {
    q: 'IELTS Coach khác gì so với tự học qua YouTube?',
    a: 'IELTS Coach chấm Writing theo 4 tiêu chí Cambridge và đề xuất từ vựng + bài luyện hàng ngày dựa trên điểm yếu cụ thể của bạn — không phải video chung chung.',
  },
  {
    q: 'Không có thẻ tín dụng, tôi dùng được không?',
    a: 'Gói Free không cần thẻ, dùng không giới hạn thời gian. Chỉ khi nâng cấp Pro mới cần phương thức thanh toán.',
  },
  {
    q: 'AI chấm Writing có chính xác không?',
    a: 'AI dựa trên rubric Cambridge (Task Response, Coherence, Lexical Resource, Grammar). Kết quả nhất quán với giáo viên IELTS trong 85%+ trường hợp kiểm tra chéo.',
  },
  {
    q: 'Tôi có thể hủy Pro lúc nào?',
    a: 'Có. Vào Cài đặt → Gói → Hủy. Không giữ thẻ, không cam kết tối thiểu.',
  },
  {
    q: 'Có app mobile không?',
    a: 'IELTS Coach là PWA — cài được lên Home Screen như app, chạy offline một phần. Chưa có native app iOS/Android.',
  },
  {
    q: 'Dữ liệu của tôi có bảo mật không?',
    a: 'Bài Writing và lịch sử luyện được mã hóa, không chia sẻ với bên thứ 3. Bạn có thể xuất hoặc xóa toàn bộ dữ liệu bất cứ lúc nào.',
  },
  {
    q: 'Có hỗ trợ tiếng Anh không?',
    a: 'Giao diện đang hỗ trợ tiếng Việt. Tiếng Anh sẽ có trong bản cập nhật Q1 2027.',
  },
  {
    q: 'Telegram bot có kèm Pro không?',
    a: 'Có. Bot hoạt động trong nhóm luyện IELTS chung của bạn, đồng bộ tiến độ với tài khoản web.',
  },
]

export default function FAQ() {
  return (
    <section
      id="faq"
      className="bg-surface px-4 py-16 sm:px-6 sm:py-24"
      aria-labelledby="faq-heading"
    >
      <div className="mx-auto max-w-3xl">
        <h2
          id="faq-heading"
          className="mb-10 text-center text-3xl font-bold text-fg sm:text-4xl"
        >
          Câu hỏi thường gặp
        </h2>
        <ul className="flex flex-col gap-3">
          {FAQS.map(({ q, a }, i) => (
            <li key={q}>
              <details
                name="faq-group"
                open={i === 0}
                className="group rounded-2xl border border-border bg-surface-raised p-5 transition-colors open:border-primary/40"
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-base font-medium text-fg marker:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:rounded-lg [&::-webkit-details-marker]:hidden">
                  <span>{q}</span>
                  <span
                    aria-hidden="true"
                    className="relative flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border text-muted-fg transition-colors group-open:border-primary group-open:text-primary"
                  >
                    <Icon
                      name="Plus"
                      size="sm"
                      className="transition-transform duration-base ease-out-soft group-open:rotate-45"
                    />
                  </span>
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-muted-fg sm:text-base">
                  {a}
                </p>
              </details>
            </li>
          ))}
        </ul>

        <p className="mt-10 text-center text-sm text-muted-fg">
          Còn câu hỏi khác? Nhắn{' '}
          <a
            href="https://t.me/ielts_coach_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            Telegram support
          </a>{' '}
          — phản hồi trong 24h.
        </p>
      </div>
    </section>
  )
}
