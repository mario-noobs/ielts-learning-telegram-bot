import { useTranslation } from 'react-i18next'

/** Placeholder — full CRUD UI lands in commit 9. */
export default function PlansPage() {
  const { t } = useTranslation('admin')
  return (
    <div className="px-4 md:px-6 py-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">{t('plans.title')}</h1>
      <p className="text-muted-fg">{t('common.loading')}</p>
    </div>
  )
}
