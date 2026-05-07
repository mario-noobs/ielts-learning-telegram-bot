import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import AdminGate from './components/AdminGate'
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
const AdminLandingPage = lazy(() => import('./pages/admin/AdminLandingPage'))
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
            <Route
              path="/admin"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminLandingPage />
                  </Suspense>
                </AdminGate>
              }
            />
            <Route
              path="/admin/users"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminUsersPage />
                  </Suspense>
                </AdminGate>
              }
            />
            <Route
              path="/admin/users/:id"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminUserDetailPage />
                  </Suspense>
                </AdminGate>
              }
            />
            <Route
              path="/admin/plans"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminPlansPage />
                  </Suspense>
                </AdminGate>
              }
            />
            <Route
              path="/admin/flags"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminFlagsPage />
                  </Suspense>
                </AdminGate>
              }
            />
            <Route
              path="/admin/teams"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminTeamsPage />
                  </Suspense>
                </AdminGate>
              }
            />
            <Route
              path="/admin/teams/:id"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminTeamDetailPage />
                  </Suspense>
                </AdminGate>
              }
            />
            <Route
              path="/admin/orgs"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminOrgsPage />
                  </Suspense>
                </AdminGate>
              }
            />
            <Route
              path="/admin/orgs/:id"
              element={
                <AdminGate>
                  <Suspense fallback={<AdminFallback />}>
                    <AdminOrgDetailPage />
                  </Suspense>
                </AdminGate>
              }
            />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
