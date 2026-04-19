import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '../../components/ui'
import Icon from '../../components/Icon'
import { track } from '../../lib/analytics'

type PlanId = 'free' | 'pro' | 'intensive'

type Feature = { text: string; negative?: boolean }

type Tier = {
  name: string
  price: string
  cadence: string
  tagline: string
  features: Feature[]
  cta: string
  planId: PlanId
  highlighted: boolean
}

const tiers: Tier[] = [
  {
    name: 'Free',
    price: '0đ',
    cadence: '/ mãi mãi',
    tagline: 'Thử trước khi cam kết',
    features: [
      { text: 'Vocab SRS · 50 từ/ngày' },
      { text: 'Writing AI chấm 1 bài/tuần' },
      { text: 'Listening · 10 phút/ngày' },
      { text: 'Không có Adaptive Plan', negative: true },
    ],
    cta: 'Bắt đầu miễn phí',
    planId: 'free',
    highlighted: false,
  },
  {
    name: 'Pro',
    price: '99.000đ',
    cadence: '/tháng',
    tagline: 'Phù hợp cho luyện 3–6 tháng',
    features: [
      { text: 'Vocab SRS · không giới hạn' },
      { text: 'Writing AI chấm không giới hạn' },
      { text: 'Listening + Reading đầy đủ' },
      { text: 'Adaptive Plan hàng ngày' },
      { text: 'Xuất báo cáo band progress' },
    ],
    cta: 'Dùng thử Pro 7 ngày',
    planId: 'pro',
    highlighted: true,
  },
  {
    name: 'Intensive',
    price: 'Liên hệ',
    cadence: '',
    tagline: 'Cho mục tiêu 7.5+ trong 90 ngày',
    features: [
      { text: 'Tất cả tính năng Pro' },
      { text: 'Speaking Coach AI (sắp ra mắt)' },
      { text: 'Mock Exam hàng tuần (sắp ra mắt)' },
      { text: 'Coach review cá nhân 2 lần/tháng' },
      { text: 'Ưu tiên hỗ trợ' },
    ],
    cta: 'Chọn Intensive',
    planId: 'intensive',
    highlighted: false,
  },
]

export default function Pricing() {
  const navigate = useNavigate()

  const handleChoose = (planId: PlanId) => {
    track('landing_pricing_cta', { plan: planId })
    try {
      localStorage.setItem('intended_plan', planId)
    } catch {
      /* private mode / quota — query param still carries intent */
    }
    navigate(`/login?plan=${planId}`)
  }

  return (
    <section
      id="pricing"
      className="bg-surface px-4 py-16 sm:px-6 sm:py-24"
      aria-labelledby="pricing-heading"
    >
      <div className="mx-auto max-w-6xl">
        <h2
          id="pricing-heading"
          className="mb-4 text-center text-3xl font-bold text-fg sm:text-4xl"
        >
          Gói học phù hợp với bạn
        </h2>
        <p className="mb-12 text-center text-base text-muted-fg sm:text-lg">
          Không thẻ tín dụng. Hủy bất cứ lúc nào.
        </p>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3 md:items-stretch">
          {tiers.map((tier) => {
            const card = (
              <Card className="flex h-full flex-col" aria-label={`Gói ${tier.name}`}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xl">{tier.name}</CardTitle>
                    {tier.highlighted && (
                      <Badge variant="primary">Phổ biến nhất</Badge>
                    )}
                  </div>
                  <CardDescription>{tier.tagline}</CardDescription>
                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-fg">
                      {tier.price}
                    </span>
                    {tier.cadence && (
                      <span className="text-sm text-muted-fg">
                        {tier.cadence}
                      </span>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="flex-1">
                  <ul className="flex min-h-[200px] flex-col gap-3">
                    {tier.features.map((f) => (
                      <li
                        key={f.text}
                        className="flex items-start gap-2 text-sm"
                      >
                        {f.negative ? (
                          <Icon
                            name="Minus"
                            size="sm"
                            variant="muted"
                            className="mt-0.5"
                          />
                        ) : (
                          <Icon
                            name="Check"
                            size="sm"
                            variant="primary"
                            className="mt-0.5"
                          />
                        )}
                        <span
                          className={
                            f.negative
                              ? 'text-muted-fg line-through decoration-muted-fg/60'
                              : 'text-fg'
                          }
                        >
                          {f.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
                <CardFooter>
                  <Button
                    variant={tier.highlighted ? 'primary' : 'secondary'}
                    size="lg"
                    className="w-full"
                    onClick={() => handleChoose(tier.planId)}
                  >
                    {tier.cta}
                  </Button>
                </CardFooter>
              </Card>
            )

            return tier.highlighted ? (
              <div
                key={tier.name}
                className="rounded-2xl ring-2 ring-primary md:scale-[1.03] md:shadow-lg md:transition-transform"
              >
                {card}
              </div>
            ) : (
              <div key={tier.name}>{card}</div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
