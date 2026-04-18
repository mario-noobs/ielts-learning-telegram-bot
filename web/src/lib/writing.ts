export type TaskType = 'task1' | 'task2'

export type IssueType = 'grammar' | 'weak_vocab' | 'good'

export interface WritingScores {
  task_achievement: number
  coherence_cohesion: number
  lexical_resource: number
  grammatical_range_accuracy: number
}

export interface CriterionFeedback {
  task_achievement: string
  coherence_cohesion: string
  lexical_resource: string
  grammatical_range_accuracy: string
}

export interface ParagraphAnnotation {
  paragraph_index: number
  excerpt: string
  issue_type: IssueType
  issue: string
  suggestion: string
  explanation_vi: string
}

export interface WritingSubmission {
  id: string
  text: string
  task_type: TaskType
  prompt: string
  overall_band: number
  scores: WritingScores
  criterion_feedback: CriterionFeedback
  paragraph_annotations: ParagraphAnnotation[]
  summary_vi: string
  word_count: number
  created_at: string | null
  original_id: string | null
  delta_band: number | null
}

export interface WritingHistoryItem {
  id: string
  task_type: TaskType
  prompt_preview: string
  overall_band: number
  word_count: number
  created_at: string | null
  original_id: string | null
}

export const CRITERIA: { key: keyof WritingScores; label: string }[] = [
  { key: 'task_achievement', label: 'Task Achievement' },
  { key: 'coherence_cohesion', label: 'Coherence & Cohesion' },
  { key: 'lexical_resource', label: 'Lexical Resource' },
  { key: 'grammatical_range_accuracy', label: 'Grammar' },
]

export function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0')
  const s = Math.floor(seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}
