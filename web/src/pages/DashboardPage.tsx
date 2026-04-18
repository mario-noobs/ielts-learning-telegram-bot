import { useAuth } from '../contexts/AuthContext'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import LinkTelegramCard from '../components/LinkTelegramCard'

interface UserProfile {
  id: string
  name: string
  email: string | null
  target_band: number
  topics: string[]
  streak: number
  total_words: number
}

function isWebPlaceholder(profile: UserProfile): boolean {
  return profile.id.startsWith('web_')
}

async function getOrCreateProfile(): Promise<UserProfile> {
  try {
    return await apiFetch<UserProfile>('/api/v1/me')
  } catch {
    // User doesn't exist yet — auto-register
    return await apiFetch<UserProfile>('/api/v1/users', {
      method: 'POST',
      body: JSON.stringify({
        name: 'IELTS Learner',
        target_band: 7.0,
        topics: ['education', 'environment', 'technology'],
      }),
    })
  }
}

export default function DashboardPage() {
  const { logout } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    getOrCreateProfile()
      .then(setProfile)
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="max-w-2xl mx-auto p-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">IELTS Coach</h1>
        <button onClick={logout} className="text-gray-500 hover:text-gray-700 text-sm">
          Đăng xuất
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-lg mb-4">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {profile ? (
        <div className="space-y-4">
          <div className="bg-white rounded-xl shadow-sm p-6">
            <p className="text-lg font-medium">Chào, {profile.name}!</p>
            <p className="text-gray-500 mt-1">Band mục tiêu: {profile.target_band}</p>
            <p className="text-gray-500">Từ vựng: {profile.total_words} từ</p>
            <p className="text-gray-500">Streak: {profile.streak} ngày</p>
            <div className="mt-4 flex flex-wrap gap-4">
              <Link
                to="/vocab"
                className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
              >
                Xem từ vựng →
              </Link>
              <Link
                to="/write"
                className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
              >
                Luyện viết →
              </Link>
              <Link
                to="/write/history"
                className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
              >
                Lịch sử bài viết →
              </Link>
              <Link
                to="/listening"
                className="text-indigo-600 hover:text-indigo-700 text-sm font-medium"
              >
                Luyện nghe →
              </Link>
            </div>
          </div>

          {isWebPlaceholder(profile) && <LinkTelegramCard onLinked={load} />}
        </div>
      ) : !error ? (
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
        </div>
      ) : null}
    </div>
  )
}
