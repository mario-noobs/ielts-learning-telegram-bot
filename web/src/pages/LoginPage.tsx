import { useAuth } from '../contexts/AuthContext'
import { Navigate } from 'react-router-dom'

export default function LoginPage() {
  const { user, loading, signInWithGoogle } = useAuth()

  if (loading) {
    return <div className="flex items-center justify-center h-screen text-muted-fg">Loading...</div>
  }
  if (user) return <Navigate to="/" replace />

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-surface px-4">
      <h1 className="text-3xl font-bold mb-2 text-fg">IELTS Coach</h1>
      <p className="text-muted-fg mb-8">Luyện IELTS cùng AI</p>
      <button
        onClick={signInWithGoogle}
        className="bg-primary text-primary-fg px-6 py-3 rounded-lg font-medium hover:bg-primary-hover transition"
      >
        Đăng nhập với Google
      </button>
    </div>
  )
}
