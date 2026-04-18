import { useState } from 'react'
import { apiFetch } from '../lib/api'

interface UserProfile {
  id: string
  total_words: number
}

export default function LinkTelegramCard({ onLinked }: { onLinked: () => void }) {
  const [code, setCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const valid = /^\d{6}$/.test(code)

  const submit = async () => {
    if (!valid || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const profile = await apiFetch<UserProfile>('/api/v1/users/link', {
        method: 'POST',
        body: JSON.stringify({ code }),
      })
      setSuccess(true)
      setCode('')
      if (profile.total_words >= 0) onLinked()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  if (success) {
    return (
      <div className="bg-green-50 border-l-4 border-green-500 rounded-xl p-4">
        <p className="text-green-800 font-medium">Liên kết thành công!</p>
        <p className="text-green-700 text-sm mt-1">
          Dữ liệu từ vựng Telegram của bạn đã được đồng bộ.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-5">
      <h2 className="font-semibold text-gray-900">Liên kết Telegram</h2>
      <p className="text-sm text-gray-600 mt-1">
        Gõ <code className="bg-gray-100 px-1 rounded">/link</code> trong chat riêng
        với bot để nhận mã 6 chữ số, sau đó nhập vào đây.
      </p>
      <div className="flex flex-col sm:flex-row gap-2 mt-3">
        <input
          type="text"
          inputMode="numeric"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submit()
          }}
          placeholder="123456"
          className="flex-1 px-4 py-2 border-2 border-gray-200 rounded-lg font-mono tracking-widest text-center focus:border-indigo-400 focus:outline-none"
        />
        <button
          onClick={submit}
          disabled={!valid || submitting}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {submitting ? 'Đang liên kết...' : 'Liên kết'}
        </button>
      </div>
      {error && <p className="text-red-700 text-sm mt-2">{error}</p>}
    </div>
  )
}
