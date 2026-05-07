import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

/** Placeholder — full edit form + usage chart land in commit 8. */
export default function UserDetailPage() {
  const { t } = useTranslation('admin')
  const { id } = useParams<{ id: string }>()
  return (
    <div className="px-4 md:px-6 py-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold">{t('users.title')}</h1>
      <p className="text-muted-fg">{id}</p>
      <p className="text-muted-fg mt-4">{t('common.loading')}</p>
    </div>
  )
}
