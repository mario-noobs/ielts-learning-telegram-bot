import { useTranslation } from 'react-i18next'

/** Placeholder — full table lands in commit 8. */
export default function UsersPage() {
  const { t } = useTranslation('admin')
  return (
    <div className="px-4 md:px-6 py-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">{t('users.title')}</h1>
      <p className="text-muted-fg">{t('common.loading')}</p>
    </div>
  )
}
