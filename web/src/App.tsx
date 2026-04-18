import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
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

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/vocab" element={<ProtectedRoute><VocabHomePage /></ProtectedRoute>} />
          <Route path="/vocab/:id" element={<ProtectedRoute><WordDetailPage /></ProtectedRoute>} />
          <Route path="/review" element={<ProtectedRoute><FlashcardReviewPage /></ProtectedRoute>} />
          <Route path="/write" element={<ProtectedRoute><WritingPage /></ProtectedRoute>} />
          <Route path="/write/history" element={<ProtectedRoute><WritingHistoryPage /></ProtectedRoute>} />
          <Route path="/write/:id" element={<ProtectedRoute><WritingDetailPage /></ProtectedRoute>} />
          <Route path="/listening" element={<ProtectedRoute><ListeningHomePage /></ProtectedRoute>} />
          <Route path="/listening/:id" element={<ProtectedRoute><ListeningExercisePage /></ProtectedRoute>} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
