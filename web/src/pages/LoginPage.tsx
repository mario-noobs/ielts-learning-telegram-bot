import { useAuth } from '../contexts/AuthContext'
import { Navigate } from 'react-router-dom'

export default function LoginPage() {
  const { user, loading, signInWithGoogle } = useAuth()

  if (loading) {
    return <div className="flex items-center justify-center h-screen text-gray-500">Loading...</div>
  }
  if (user) return <Navigate to="/" replace />

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-50 px-4">
      <h1 className="text-3xl font-bold mb-2">IELTS Coach</h1>
      <p className="text-gray-500 mb-8">Luyện IELTS cùng AI</p>
      <button
        onClick={signInWithGoogle}
        className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition"
      >
        Đăng nhập với Google
      </button>
    </div>
  )
}
