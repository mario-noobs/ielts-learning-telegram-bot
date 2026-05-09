import { Outlet } from 'react-router-dom'
import PublicFooter from '../components/PublicFooter'

/** Shell for public-but-not-landing pages (Login, Pricing, Privacy,
 *  Terms). Renders the page via Outlet then a slim PublicFooter
 *  below — gives every public surface a consistent footer with
 *  brand mark, legal links, and language switcher. */

export default function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <div className="flex-1">
        <Outlet />
      </div>
      <PublicFooter />
    </div>
  )
}
