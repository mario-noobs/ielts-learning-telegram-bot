import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import AppShell from './components/AppShell'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import VocabHomePage from './pages/VocabHomePage'
import WordDetailPage from './pages/WordDetailPage'
import FlashcardReviewPage from './pages/FlashcardReviewPage'
import WritingPage from './pages/WritingPage'
import WritingHistoryPage from './pages/WritingHistoryPage'
import WritingDetailPage from './pages/WritingDetailPage'
import ListeningHomePage from './pages/ListeningHomePage'
import ListeningExercisePage from './pages/ListeningExercisePage'
import ListeningHistoryPage from './pages/ListeningHistoryPage'
import ProgressPage from './pages/ProgressPage'
import SettingsPage from './pages/SettingsPage'

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

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/vocab" element={<VocabHomePage />} />
            <Route path="/vocab/:id" element={<WordDetailPage />} />
            <Route path="/review" element={<FlashcardReviewPage />} />
            <Route path="/write" element={<WritingPage />} />
            <Route path="/write/history" element={<WritingHistoryPage />} />
            <Route path="/write/:id" element={<WritingDetailPage />} />
            <Route path="/listening" element={<ListeningHomePage />} />
            <Route path="/listening/history" element={<ListeningHistoryPage />} />
            <Route path="/listening/:id" element={<ListeningExercisePage />} />
            <Route path="/progress" element={<ProgressPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
