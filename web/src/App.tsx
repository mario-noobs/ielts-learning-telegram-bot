import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import AdminGate from './components/AdminGate'
import AdminShell from './components/AdminShell'
import AppShell from './components/AppShell'
import PublicLayout from './layouts/PublicLayout'
import LandingPage from './pages/LandingPage'
import LegalPage from './pages/LegalPage'
import LoginPage from './pages/LoginPage'
import PricingPage from './pages/PricingPage'
import DashboardPage from './pages/DashboardPage'
import VocabHomePage from './pages/VocabHomePage'
import VocabTopicPage from './pages/VocabTopicPage'
import WordDetailPage from './pages/WordDetailPage'
import FlashcardReviewPage from './pages/FlashcardReviewPage'
import DailyWordsPage from './pages/DailyWordsPage'
import DailyFlipCardPage from './pages/DailyFlipCardPage'
import DailyFillBlankPage from './pages/DailyFillBlankPage'
import WritingPage from './pages/WritingPage'
import WritingHistoryPage from './pages/WritingHistoryPage'
import WritingDetailPage from './pages/WritingDetailPage'
import ListeningHomePage from './pages/ListeningHomePage'
import ListeningExercisePage from './pages/ListeningExercisePage'
import ListeningHistoryPage from './pages/ListeningHistoryPage'
import ReadingHomePage from './pages/ReadingHomePage'
import ReadingExercisePage from './pages/ReadingExercisePage'
import ProgressPage from './pages/ProgressPage'
import SettingsPage from './pages/SettingsPage'
import LinkRedeemPage from './pages/LinkRedeemPage'
import LinkTelegramPage from './pages/settings/LinkTelegramPage'
import GroupsPage from './pages/settings/GroupsPage'
import GroupDetailPage from './pages/settings/GroupDetailPage'
import UsagePage from './pages/settings/UsagePage'

// Admin subtree — lazy-loaded so end-user bundles don't carry it.
const AdminDashboardPage = lazy(() => import('./pages/admin/DashboardPage'))
const AdminAuditLogPage = lazy(() => import('./pages/admin/AuditLogPage'))
const AdminUsersPage = lazy(() => import('./pages/admin/UsersPage'))
const AdminUserDetailPage = lazy(() => import('./pages/admin/UserDetailPage'))
const AdminPlansPage = lazy(() => import('./pages/admin/PlansPage'))
const AdminFlagsPage = lazy(() => import('./pages/admin/FlagsPage'))
const AdminTeamsPage = lazy(() => import('./pages/admin/TeamsPage'))
const AdminTeamDetailPage = lazy(() => import('./pages/admin/TeamDetailPage'))
const AdminOrgsPage = lazy(() => import('./pages/admin/OrgsPage'))
const AdminOrgDetailPage = lazy(() => import('./pages/admin/OrgDetailPage'))

function AdminFallback() {
  return (
    <div className="flex items-center justify-center h-[60vh] text-muted-fg">
      Loading…
    </div>
  )
}

function ProtectedShell() {
  const { user, profile, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex items-center justify-center h-dvh text-muted-fg">
        Đang tải...
      </div>
    )
  }
  if (!user && !profile) return <Navigate to="/login" replace />
  const accountKey = profile?.id ?? user?.uid ?? 'authenticated'
  return <AppShell key={accountKey} />
}

function ProtectedAdminShell() {
  return (
    <AdminGate>
      <AdminShell />
    </AdminGate>
  )
}

// Legacy `:id` route redirects — preserve the param when forwarding.
function LegacyVocabRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/learn/vocab/${id}`} replace />
}
function LegacyWriteRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/practice/writing/${id}`} replace />
}
function LegacyListeningRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/practice/listening/${id}`} replace />
}
function LegacyReadingRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/practice/reading/${id}`} replace />
}

function RootRoute() {
  const { user, profile, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex items-center justify-center h-dvh text-muted-fg">
        Đang tải...
      </div>
    )
  }
  if (!user && !profile) return <LandingPage />
  const accountKey = profile?.id ?? user?.uid ?? 'authenticated'
  return <AppShell key={accountKey} />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public pages with shared footer (US-#211). */}
          <Route element={<PublicLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/privacy" element={<LegalPage kind="privacy" />} />
            <Route path="/terms" element={<LegalPage kind="terms" />} />
            <Route path="/pricing" element={<PricingPage />} />
          </Route>
          {/* US-M12.3: public so the bot's deep-link works pre-auth;
              the page itself prompts Google sign-in when needed. */}
          <Route path="/link" element={<LinkRedeemPage />} />
          <Route path="/" element={<RootRoute />}>
            <Route index element={<DashboardPage />} />
          </Route>
          <Route element={<ProtectedShell />}>
            {/* New paths under /learn/* and /practice/* (US-#211 IA). */}
            <Route path="/learn" element={<Navigate to="/learn/daily" replace />} />
            <Route path="/learn/vocab" element={<VocabHomePage />} />
            {/* Topic drill-down — must precede `:id` so /topic/:slug
                doesn't get matched as a word id. */}
            <Route path="/learn/vocab/topic/:slug" element={<VocabTopicPage />} />
            <Route path="/learn/vocab/:id" element={<WordDetailPage />} />
            <Route path="/learn/review" element={<FlashcardReviewPage />} />
            <Route path="/learn/daily" element={<DailyWordsPage />} />
            <Route path="/learn/daily/flip" element={<DailyFlipCardPage />} />
            <Route path="/learn/daily/quiz" element={<DailyFillBlankPage />} />
            <Route path="/practice" element={<Navigate to="/practice/writing" replace />} />
            <Route path="/practice/writing" element={<WritingPage />} />
            <Route path="/practice/writing/history" element={<WritingHistoryPage />} />
            <Route path="/practice/writing/:id" element={<WritingDetailPage />} />
            <Route path="/practice/listening" element={<ListeningHomePage />} />
            <Route path="/practice/listening/history" element={<ListeningHistoryPage />} />
            <Route path="/practice/listening/:id" element={<ListeningExercisePage />} />
            <Route path="/practice/reading" element={<ReadingHomePage />} />
            <Route path="/practice/reading/:id" element={<ReadingExercisePage />} />

            {/* Legacy redirects — keep bookmarks alive. Drop after 30 days. */}
            <Route path="/vocab" element={<Navigate to="/learn/vocab" replace />} />
            <Route path="/vocab/:id" element={<LegacyVocabRedirect />} />
            <Route path="/review" element={<Navigate to="/learn/review" replace />} />
            <Route path="/daily" element={<Navigate to="/learn/daily" replace />} />
            <Route path="/daily/flip" element={<Navigate to="/learn/daily/flip" replace />} />
            <Route path="/daily/quiz" element={<Navigate to="/learn/daily/quiz" replace />} />
            <Route path="/write" element={<Navigate to="/practice/writing" replace />} />
            <Route path="/write/history" element={<Navigate to="/practice/writing/history" replace />} />
            <Route path="/write/:id" element={<LegacyWriteRedirect />} />
            <Route path="/listening" element={<Navigate to="/practice/listening" replace />} />
            <Route path="/listening/history" element={<Navigate to="/practice/listening/history" replace />} />
            <Route path="/listening/:id" element={<LegacyListeningRedirect />} />
            <Route path="/reading" element={<Navigate to="/practice/reading" replace />} />
            <Route path="/reading/:id" element={<LegacyReadingRedirect />} />

            <Route path="/progress" element={<ProgressPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/settings/link-telegram" element={<LinkTelegramPage />} />
            <Route path="/settings/usage" element={<UsagePage />} />
            <Route path="/settings/groups" element={<GroupsPage />} />
            <Route path="/settings/groups/:id" element={<GroupDetailPage />} />
          </Route>
          {/* Admin subtree — its own shell, no consumer chrome (US-M11.6). */}
          <Route element={<ProtectedAdminShell />}>
            <Route
              path="/admin"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminDashboardPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/audit"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminAuditLogPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/users"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminUsersPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/users/:id"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminUserDetailPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/plans"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminPlansPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/flags"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminFlagsPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/teams"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminTeamsPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/teams/:id"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminTeamDetailPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/orgs"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminOrgsPage />
                </Suspense>
              }
            />
            <Route
              path="/admin/orgs/:id"
              element={
                <Suspense fallback={<AdminFallback />}>
                  <AdminOrgDetailPage />
                </Suspense>
              }
            />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
