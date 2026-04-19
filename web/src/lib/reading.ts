import { apiFetch } from './api'

// ─── Types ───────────────────────────────────────────────────────────

export type Band = 5.5 | 6.0 | 6.5 | 7.0 | 7.5 | 8.0 | 8.5

export interface PassageSummary {
  id: string
  title: string
  topic: string
  band: number
  word_count: number
  attribution: string
  ai_assisted: boolean
}

export interface PassageDetail extends PassageSummary {
  body: string
}

export type QuestionType = 'gap-fill' | 'tfng' | 'matching-headings' | 'mcq'

export interface QuestionOption {
  id: string
  text: string
}

export interface ReadingQuestion {
  id: string
  type: QuestionType
  stem: string
  options?: QuestionOption[]
}

export type SessionStatus = 'in_progress' | 'submitted' | 'expired'

export interface ReadingSession {
  id: string
  passage_id: string
  status: SessionStatus
  started_at: string
  expires_at: string
  submitted_at: string | null
  questions: ReadingQuestion[]
  duration_seconds: number
}

export interface QuestionResult {
  id: string
  user_answer: string | null
  correct_answer: string
  is_correct: boolean
  explanation: string
}

export interface SessionGrade {
  correct: number
  total: number
  band: number
  per_question: QuestionResult[]
}

export interface SessionSubmitResponse {
  session_id: string
  passage_id: string
  submitted_at: string
  grade: SessionGrade
}

// ─── API helpers ─────────────────────────────────────────────────────

export function listPassages(params: {
  band?: number
  topic?: string
}): Promise<{ items: PassageSummary[] }> {
  const qs = new URLSearchParams()
  if (params.band !== undefined) qs.set('band', String(params.band))
  if (params.topic) qs.set('topic', params.topic)
  const suffix = qs.toString() ? `?${qs}` : ''
  return apiFetch(`/api/v1/reading/passages${suffix}`)
}

export function getPassage(id: string): Promise<PassageDetail> {
  return apiFetch(`/api/v1/reading/passages/${encodeURIComponent(id)}`)
}

export function startSession(passageId: string): Promise<ReadingSession> {
  return apiFetch('/api/v1/reading/sessions', {
    method: 'POST',
    body: JSON.stringify({ passage_id: passageId }),
  })
}

export function submitSession(
  sessionId: string,
  answers: Record<string, string>,
  idempotencyKey: string,
): Promise<SessionSubmitResponse> {
  return apiFetch(
    `/api/v1/reading/sessions/${encodeURIComponent(sessionId)}/submit`,
    {
      method: 'POST',
      body: JSON.stringify({ answers, idempotency_key: idempotencyKey }),
    },
  )
}

// ─── Utilities ───────────────────────────────────────────────────────

export const BAND_TIERS: Band[] = [5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5]

export function formatTimer(remainingSec: number): string {
  const safe = Math.max(0, Math.floor(remainingSec))
  const m = Math.floor(safe / 60)
  const s = safe % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export const QUESTION_TYPE_LABEL: Record<QuestionType, string> = {
  'gap-fill': 'Điền từ',
  tfng: 'Đúng / Sai / Không rõ',
  'matching-headings': 'Ghép đoạn',
  mcq: 'Trắc nghiệm',
}

// localStorage helpers for highlight persistence (AC3).
const HIGHLIGHT_KEY = (sessionId: string) => `reading_hl_v1:${sessionId}`

export function loadHighlights(sessionId: string): string[] {
  try {
    const raw = localStorage.getItem(HIGHLIGHT_KEY(sessionId))
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

export function saveHighlights(sessionId: string, texts: string[]): void {
  try {
    localStorage.setItem(HIGHLIGHT_KEY(sessionId), JSON.stringify(texts))
  } catch {
    // storage full / disabled — silently drop
  }
}

export function clearHighlights(sessionId: string): void {
  try {
    localStorage.removeItem(HIGHLIGHT_KEY(sessionId))
  } catch {
    // ignore
  }
}
