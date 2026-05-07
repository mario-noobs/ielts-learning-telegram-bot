import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

/** Default landing for `/admin` — pointers to the three sub-sections. */
export default function AdminLandingPage() {
  const { t } = useTranslation('admin')
  return (
    <div className="px-4 md:px-6 py-6 max-w-3xl mx-auto space-y-4">
      <h1 className="text-2xl font-semibold">{t('landing.title')}</h1>
      <p className="text-muted-fg">{t('landing.subtitle')}</p>
      <ul className="space-y-2">
        <li>
          <Link to="/admin/users" className="text-primary underline">
            {t('users.title')}
          </Link>
        </li>
        <li>
          <Link to="/admin/teams" className="text-primary underline">
            {t('teams.title')}
          </Link>
        </li>
        <li>
          <Link to="/admin/orgs" className="text-primary underline">
            {t('orgs.title')}
          </Link>
        </li>
        <li>
          <Link to="/admin/plans" className="text-primary underline">
            {t('plans.title')}
          </Link>
        </li>
        <li>
          <Link to="/admin/flags" className="text-primary underline">
            {t('flags.title')}
          </Link>
        </li>
      </ul>
    </div>
  )
}
