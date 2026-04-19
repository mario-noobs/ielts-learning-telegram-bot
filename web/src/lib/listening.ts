import { auth } from './firebase'

const API_URL = import.meta.env.VITE_API_URL || ''

export type ListeningType = 'dictation' | 'gap_fill' | 'comprehension'

export interface ListeningExerciseView {
  id: string
  exercise_type: ListeningType
  band: number
  topic: string
  title: string
  duration_estimate_sec: number
  audio_url: string
  created_at: string | null
  submitted: boolean
  score: number | null
  display_text: string
  questions: { question: string; options: string[] }[]
}

export interface DictationDiffItem {
  type: 'correct' | 'wrong' | 'missed' | 'extra'
  text: string
  expected?: string
}

export interface GapFillResultItem {
  index: number
  user_answer: string
  correct_answer: string
  is_correct: boolean
}

export interface ComprehensionResultItem {
  index: number
  user_index: number
  correct_index: number
  is_correct: boolean
  explanation_vi: string
}

export interface ComprehensionQuestionFull {
  question: string
  options: string[]
  correct_index: number
  explanation_vi: string
}

export interface GapBlank {
  index: number
  answer: string
}

export interface ListeningExerciseResult {
  id: string
  exercise_type: ListeningType
  band: number
  topic: string
  title: string
  duration_estimate_sec: number
  audio_url: string
  created_at: string | null
  submitted: boolean
  score: number | null
  transcript: string
  display_text: string
  blanks: GapBlank[]
  questions: ComprehensionQuestionFull[]
  dictation_diff: DictationDiffItem[]
  gap_fill_results: GapFillResultItem[]
  comprehension_results: ComprehensionResultItem[]
  misheard_words: string[]
}

export interface ListeningHistoryItem {
  id: string
  exercise_type: ListeningType
  title: string
  band: number
  score: number | null
  submitted: boolean
  created_at: string | null
}

const blobCache = new Map<string, string>()

export async function fetchListeningAudioUrl(pathSuffix: string): Promise<string> {
  const cached = blobCache.get(pathSuffix)
  if (cached) return cached
  const token = await auth.currentUser?.getIdToken()
  const res = await fetch(`${API_URL}${pathSuffix}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error(`audio ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  blobCache.set(pathSuffix, url)
  return url
}

export function formatDuration(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  const m = Math.floor(safe / 60).toString().padStart(2, '0')
  const s = Math.floor(safe % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

import type { IconName } from '../components/Icon'

/**
 * Icon + translation-key map for each listening exercise type.
 * Labels come from the `listening` i18n bundle via `types.<type>.title` /
 * `types.<type>.hint`, so rendering depends on the active locale.
 */
export const EXERCISE_ICONS: Record<ListeningType, IconName> = {
  dictation: 'PenLine',
  gap_fill: 'SquarePen',
  comprehension: 'Headphones',
}
