import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import AdminGate from './components/AdminGate'
import AdminShell from './components/AdminShell'
import AppShell from './components/AppShell'
import LandingPage from './pages/LandingPage'
import LegalPage from './pages/LegalPage'
import LoginPage from './pages/LoginPage'
import PricingPage from './pages/PricingPage'
import DashboardPage from './pages/DashboardPage'
import VocabHomePage from './pages/VocabHomePage'
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
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex items-center justify-center h-dvh text-muted-fg">
        Đang tải...
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <AppShell />
}

function ProtectedAdminShell() {
  return (
    <AdminGate>
      <AdminShell />
    </AdminGate>
  )
}

function RootRoute() {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex items-center justify-center h-dvh text-muted-fg">
        Đang tải...
      </div>
    )
  }
  if (!user) return <LandingPage />
  return <AppShell />
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/privacy" element={<LegalPage kind="privacy" />} />
          <Route path="/terms" element={<LegalPage kind="terms" />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/" element={<RootRoute />}>
            <Route index element={<DashboardPage />} />
          </Route>
          <Route element={<ProtectedShell />}>
            <Route path="/vocab" element={<VocabHomePage />} />
            <Route path="/vocab/:id" element={<WordDetailPage />} />
            <Route path="/review" element={<FlashcardReviewPage />} />
            <Route path="/daily" element={<DailyWordsPage />} />
            <Route path="/daily/flip" element={<DailyFlipCardPage />} />
            <Route path="/daily/quiz" element={<DailyFillBlankPage />} />
            <Route path="/write" element={<WritingPage />} />
            <Route path="/write/history" element={<WritingHistoryPage />} />
            <Route path="/write/:id" element={<WritingDetailPage />} />
            <Route path="/listening" element={<ListeningHomePage />} />
            <Route path="/listening/history" element={<ListeningHistoryPage />} />
            <Route path="/listening/:id" element={<ListeningExercisePage />} />
            <Route path="/reading" element={<ReadingHomePage />} />
            <Route path="/reading/:id" element={<ReadingExercisePage />} />
            <Route path="/progress" element={<ProgressPage />} />
            <Route path="/settings" element={<SettingsPage />} />
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
