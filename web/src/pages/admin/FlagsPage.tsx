import { useTranslation } from 'react-i18next'

/** Placeholder — full toggle list lands in commit 10. */
export default function FlagsPage() {
  const { t } = useTranslation('admin')
  return (
    <div className="px-4 md:px-6 py-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">{t('flags.title')}</h1>
      <p className="text-muted-fg">{t('common.loading')}</p>
    </div>
  )
}
