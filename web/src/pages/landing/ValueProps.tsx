import { BookOpen, FileText, Headphones, PenLine } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from '../../components/ui'

interface PropDef {
  icon: typeof BookOpen
  illustration: string // path under web/public/landing/
  i18nKey: 'vocab' | 'writing' | 'listening' | 'reading'
  iconColor: string
  iconBg: string
}

const PROPS: PropDef[] = [
  {
    icon: BookOpen,
    illustration: '/landing/vocab.svg',
    i18nKey: 'vocab',
    iconColor: 'text-primary',
    iconBg: 'bg-primary/10',
  },
  {
    icon: PenLine,
    illustration: '/landing/writing.svg',
    i18nKey: 'writing',
    iconColor: 'text-accent',
    iconBg: 'bg-accent/10',
  },
  {
    icon: Headphones,
    illustration: '/landing/howitworks-2-feedback.svg',
    i18nKey: 'listening',
    iconColor: 'text-warning',
    iconBg: 'bg-warning/10',
  },
  {
    icon: FileText,
    illustration: '/landing/howitworks-3-readiness.svg',
    i18nKey: 'reading',
    iconColor: 'text-success',
    iconBg: 'bg-success/10',
  },
]

export default function ValueProps() {
  const { t } = useTranslation('landing')
  return (
    <section
      aria-labelledby="value-props-heading"
      className="mx-auto w-full max-w-6xl px-4 py-12 md:px-6 md:py-20"
    >
      <div className="mb-10 max-w-2xl md:mb-14">
        <h2
          id="value-props-heading"
          className="text-3xl font-bold text-fg md:text-4xl"
        >
          {t('valueProps.heading')}
        </h2>
        <p className="mt-3 text-lg text-muted-fg">
          {t('valueProps.subheading')}
        </p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4 md:gap-8">
        {PROPS.map(({ icon: Icon, illustration, i18nKey, iconColor, iconBg }) => (
          <Card
            key={i18nKey}
            className="group overflow-hidden p-0 transition-shadow hover:shadow-lg"
          >
            <div className="relative aspect-[16/10] overflow-hidden bg-surface">
              <img
                src={illustration}
                alt=""
                className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                loading="lazy"
                decoding="async"
              />
            </div>
            <CardHeader className="p-6">
              <div
                className={`mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl ${iconBg}`}
              >
                <Icon className={`h-5 w-5 ${iconColor}`} aria-hidden="true" />
              </div>
              <CardTitle className="text-lg">
                {t(`valueProps.cards.${i18nKey}.title`)}
              </CardTitle>
              <CardDescription className="mt-2 leading-relaxed">
                {t(`valueProps.cards.${i18nKey}.body`)}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </section>
  )
}
