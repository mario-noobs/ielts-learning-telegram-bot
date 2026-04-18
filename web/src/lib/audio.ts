import { auth } from './firebase'

const API_URL = import.meta.env.VITE_API_URL || ''
const blobCache = new Map<string, string>()

async function fetchAudioBlob(word: string): Promise<string> {
  const cached = blobCache.get(word)
  if (cached) return cached

  const token = await auth.currentUser?.getIdToken()
  const res = await fetch(`${API_URL}/api/v1/audio/${encodeURIComponent(word)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`audio ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  blobCache.set(word, url)
  return url
}

function speechFallback(word: string): void {
  if (!('speechSynthesis' in window)) return
  const u = new SpeechSynthesisUtterance(word)
  u.lang = 'en-US'
  window.speechSynthesis.speak(u)
}

export async function playPronunciation(word: string): Promise<void> {
  try {
    const url = await fetchAudioBlob(word)
    await new Audio(url).play()
  } catch {
    speechFallback(word)
  }
}
