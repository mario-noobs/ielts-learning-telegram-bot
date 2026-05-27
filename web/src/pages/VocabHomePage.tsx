/**
 * /learn/vocab — private vocabulary home.
 *
 * My Words is the primary view for the user's saved cards. Topic cards
 * remain as a drill-down index for mastery-focused review.
 */

import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'
import EmptyState from '../components/EmptyState'
import { useProfile } from '../contexts/AuthContext'
import Icon from '../components/Icon'

interface TopicSummary {
  id: string
  name: string
  word_count: number
  mastered_count: number
  subtopics: string[]
}

interface TopicsResponse {
  items: TopicSummary[]
  total_words: number
}

interface VocabularyWord {
  id: string
  word: string
  definition: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  topic: string
  strength: string
  source: string
  is_favourite: boolean
}

interface WordListResponse {
  items: VocabularyWord[]
  next_cursor: string | null
}

interface WordDraft {
  word: string
  definition: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  topic: string
  example_en: string
  example_vi: string
  ielts_tip: string
  already_exists: boolean
  existing_word_id: string | null
}

type ImportMode = 'topic' | 'text'

interface ImportWordsResponse {
  mode: ImportMode
  input: string
  candidates: WordDraft[]
  duplicate_count: number
  max_candidates: number
  max_input_chars: number
}

interface AiUsage {
  plan: string
  quota_daily: number
  used_today: number
  reset_at: string
}

interface DailyHistoryWord {
  word: string
  word_id: string
  daily_source?: string
  reviewed: boolean
  is_favourite: boolean
  strength: string
  definition_en: string
  definition_vi: string
  ipa: string
  part_of_speech: string
}

interface DailyHistoryEntry {
  date: string
  topic: string
  words: DailyHistoryWord[]
  total_count: number
  reviewed_count: number
  favourite_count: number
  weak_count: number
  mastered_count: number
}

interface DailyHistoryResponse {
  items: DailyHistoryEntry[]
  timezone: string
}

interface DailyWordsResponse {
  date: string
  topic: string
  words: DailyHistoryWord[]
  reviewed_count: number
  total_count: number
}

type VocabTab = 'myWords' | 'topics' | 'favourites' | 'history'
type SourceFilter = 'all' | 'daily' | 'manual' | 'quiz' | 'reading'
type StatusFilter = 'all' | 'New' | 'Weak' | 'Learning' | 'Good' | 'Mastered'

const SOURCE_FILTERS: SourceFilter[] = ['all', 'daily', 'manual', 'quiz', 'reading']
const STATUS_FILTERS: StatusFilter[] = ['all', 'New', 'Weak', 'Learning', 'Good', 'Mastered']

const HISTORY_STATS = [
  ['total', 'total_count'],
  ['reviewed', 'reviewed_count'],
  ['favourites', 'favourite_count'],
  ['weak', 'weak_count'],
  ['mastered', 'mastered_count'],
] as const

interface VocabHomePageProps {
  initialTab?: VocabTab
}

function AiUsageNote({
  usage,
  t,
}: {
  usage: AiUsage | null
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  if (!usage) return null
  const remaining = Math.max(0, usage.quota_daily - usage.used_today)
  return (
    <p className="mt-3 rounded-md border border-border bg-bg px-3 py-2 text-xs text-muted-fg">
      {t('limits.aiUsage', {
        remaining,
        quota: usage.quota_daily,
        used: usage.used_today,
        reset: usage.reset_at,
      })}
    </p>
  )
}

function topicLabel(
  slug: string,
  apiName: string,
  t: (k: string, o?: Record<string, unknown>) => string,
): string {
  return t(`topicNames.${slug}`, { defaultValue: apiName })
}

function TopicCard({
  topic,
  t,
}: {
  topic: TopicSummary
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  const total = topic.word_count
  const mastered = topic.mastered_count
  const pct = total === 0 ? 0 : (mastered / total) * 100
  return (
    <Link
      to={`/learn/vocab/topic/${encodeURIComponent(topic.id)}`}
      className="block rounded-xl border border-border bg-surface-raised p-4 transition-colors hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold text-fg truncate">
          {topicLabel(topic.id, topic.name, t)}
        </p>
        <span className="shrink-0 text-xs text-muted-fg">
          {t('byTopic.topicSection.count', { count: total })}
        </span>
      </div>
      <div className="mt-3 h-1.5 bg-surface rounded-full overflow-hidden">
        <div
          className="h-full bg-primary transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-muted-fg mt-1.5">
        {t('byTopic.card.masteryLine', {
          mastered, total, pct: Math.round(pct),
        })}
      </p>
    </Link>
  )
}

function FavouriteWordRow({ word }: { word: VocabularyWord }) {
  return (
    <Link
      to={`/learn/vocab/${encodeURIComponent(word.word)}`}
      onClick={() =>
        track('vocab_favourite_detail_opened', {
          word: word.word,
          word_id: word.id,
        })
      }
      className="flex items-center gap-3 rounded-lg border border-transparent bg-surface-raised px-3 py-2.5 hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <Icon name="Heart" size="sm" variant="danger" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-fg truncate">
          {word.word}
          {word.ipa && (
            <span className="ml-1.5 text-xs font-normal text-muted-fg">
              /{word.ipa}/
            </span>
          )}
          {word.part_of_speech && (
            <span className="ml-1.5 text-xs font-normal text-muted-fg">
              {word.part_of_speech}
            </span>
          )}
        </p>
        {(word.definition_vi || word.definition) && (
          <p className="text-xs text-muted-fg truncate mt-0.5">
            {word.definition_vi || word.definition}
          </p>
        )}
      </div>
      <Icon name="ArrowRight" size="sm" variant="muted" />
    </Link>
  )
}

function MyWordRow({
  word,
  t,
}: {
  word: VocabularyWord
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  return (
    <Link
      to={`/learn/vocab/${encodeURIComponent(word.word)}`}
      onClick={() =>
        track('vocab_my_word_detail_opened', {
          word: word.word,
          word_id: word.id,
          source: word.source,
        })
      }
      className="flex items-center gap-3 rounded-lg border border-transparent bg-surface-raised px-3 py-2.5 hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <Icon name="BookOpen" size="sm" variant="primary" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-fg truncate">
          {word.word}
          {word.ipa && (
            <span className="ml-1.5 text-xs font-normal text-muted-fg">
              /{word.ipa}/
            </span>
          )}
          {word.part_of_speech && (
            <span className="ml-1.5 text-xs font-normal text-muted-fg">
              {word.part_of_speech}
            </span>
          )}
        </p>
        {(word.definition_vi || word.definition) && (
          <p className="text-xs text-muted-fg truncate mt-0.5">
            {word.definition_vi || word.definition}
          </p>
        )}
      </div>
      <div className="hidden shrink-0 items-center gap-1.5 sm:flex">
        <span className="rounded-md bg-surface px-2 py-1 text-xs text-muted-fg">
          {t(`myWords.sources.${word.source}`, { defaultValue: word.source })}
        </span>
        <span className="rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
          {t(`strength.${word.strength}`, { defaultValue: word.strength })}
        </span>
      </div>
      {word.is_favourite && <Icon name="Heart" size="sm" variant="danger" />}
      <Icon name="ArrowRight" size="sm" variant="muted" />
    </Link>
  )
}

function AddWordWithAi({
  t,
  onSaved,
}: {
  t: (k: string, o?: Record<string, unknown>) => string
  onSaved: (word: VocabularyWord) => void
}) {
  const [input, setInput] = useState('')
  const [draft, setDraft] = useState<WordDraft | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [savedMessage, setSavedMessage] = useState('')

  const trimmed = input.trim()

  const createDraft = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!trimmed) return
    setLoading(true)
    setError('')
    setSavedMessage('')
    setDraft(null)
    try {
      const nextDraft = await apiFetch<WordDraft>('/api/v1/vocabulary/draft', {
        method: 'POST',
        body: JSON.stringify({ word: trimmed }),
      })
      setDraft(nextDraft)
      if (nextDraft.already_exists) {
        setSavedMessage(t('addWord.alreadyExists', { word: nextDraft.word }))
      } else {
        track('vocab_ai_word_draft_created', { word: nextDraft.word })
      }
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setLoading(false)
    }
  }

  const saveDraft = async (useDraft: boolean) => {
    const wordToSave = (useDraft ? draft?.word : trimmed) || trimmed
    if (!wordToSave.trim()) return
    setSaving(true)
    setError('')
    setSavedMessage('')
    try {
      const payload = useDraft && draft
        ? {
            word: draft.word,
            definition: draft.definition,
            definition_vi: draft.definition_vi,
            ipa: draft.ipa,
            part_of_speech: draft.part_of_speech,
            topic: draft.topic,
            example_en: draft.example_en,
            example_vi: draft.example_vi,
            use_ai: false,
          }
        : { word: wordToSave, use_ai: false }
      const saved = await apiFetch<VocabularyWord>('/api/v1/vocabulary', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      onSaved(saved)
      setInput('')
      setDraft(null)
      setSavedMessage(t('addWord.saved', { word: saved.word }))
      track('vocab_ai_word_saved', { word: saved.word, used_draft: useDraft })
    } catch (e) {
      const msg = localizeError(e)
      setError(msg)
      if (msg.toLowerCase().includes('already')) {
        setDraft((current) => current ? { ...current, already_exists: true } : current)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-surface-raised p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="font-semibold text-fg">{t('addWord.title')}</h2>
          <p className="mt-1 max-w-xl text-sm text-muted-fg">{t('addWord.description')}</p>
        </div>
        <span className="inline-flex w-fit items-center rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
          {t('addWord.badge')}
        </span>
      </div>

      <form onSubmit={createDraft} className="mt-4 flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="ai-word-input">
          {t('addWord.inputLabel')}
        </label>
        <input
          id="ai-word-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={80}
          placeholder={t('addWord.placeholder')}
          className="min-w-0 flex-1 rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg"
        />
        <button
          type="submit"
          disabled={!trimmed || loading || saving}
          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Icon name="Sparkles" size="sm" variant="fg" />
          {loading ? t('addWord.generating') : t('addWord.generate')}
        </button>
      </form>

      {error && (
        <div className="mt-3 rounded-md border border-danger/30 bg-danger/10 p-3">
          <p className="text-sm text-danger">{error}</p>
          <button
            type="button"
            onClick={() => void saveDraft(false)}
            disabled={!trimmed || saving}
            className="mt-2 text-sm font-medium text-danger underline-offset-2 hover:underline disabled:opacity-60"
          >
            {saving ? t('addWord.saving') : t('addWord.saveBasic')}
          </button>
        </div>
      )}

      {savedMessage && (
        <p className="mt-3 rounded-md border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
          {savedMessage}
        </p>
      )}

      {draft && !draft.already_exists && (
        <div className="mt-4 rounded-lg border border-border bg-bg p-4">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-2">
            <h3 className="text-lg font-semibold text-fg">{draft.word}</h3>
            {draft.ipa && <span className="text-sm text-muted-fg">/{draft.ipa}/</span>}
            {draft.part_of_speech && (
              <span className="text-sm text-muted-fg">{draft.part_of_speech}</span>
            )}
          </div>
          <p className="mt-2 text-sm text-fg">{draft.definition}</p>
          {draft.definition_vi && (
            <p className="mt-1 text-sm text-muted-fg">{draft.definition_vi}</p>
          )}
          {draft.example_en && (
            <blockquote className="mt-3 border-l-2 border-primary/40 pl-3 text-sm text-muted-fg">
              {draft.example_en}
            </blockquote>
          )}
          {draft.ielts_tip && (
            <p className="mt-3 text-xs text-muted-fg">{draft.ielts_tip}</p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void saveDraft(true)}
              disabled={saving}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-60"
            >
              <Icon name="Plus" size="sm" variant="fg" />
              {saving ? t('addWord.saving') : t('addWord.save')}
            </button>
            <button
              type="button"
              onClick={() => setDraft(null)}
              disabled={saving}
              className="rounded-md border border-border px-3 py-2 text-sm font-medium text-muted-fg hover:text-fg disabled:opacity-60"
            >
              {t('addWord.cancel')}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}

function ImportWordsPanel({
  t,
  onSaved,
}: {
  t: (k: string, o?: Record<string, unknown>) => string
  onSaved: (word: VocabularyWord) => void
}) {
  const [mode, setMode] = useState<ImportMode>('topic')
  const [input, setInput] = useState('')
  const [count, setCount] = useState(5)
  const [result, setResult] = useState<ImportWordsResponse | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [summary, setSummary] = useState('')

  const trimmed = input.trim()
  const selectable = result?.candidates.filter((candidate) => !candidate.already_exists) ?? []
  const selectedCandidates = selectable.filter((candidate) => selected.has(candidate.word))

  const createCandidates = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!trimmed) return
    setLoading(true)
    setError('')
    setSummary('')
    setResult(null)
    try {
      const next = await apiFetch<ImportWordsResponse>('/api/v1/vocabulary/import/draft', {
        method: 'POST',
        body: JSON.stringify({ mode, input: trimmed, count }),
      })
      setResult(next)
      setSelected(new Set(next.candidates.filter((candidate) => !candidate.already_exists).map((candidate) => candidate.word)))
      track('vocab_import_candidates_created', {
        mode,
        candidate_count: next.candidates.length,
        duplicate_count: next.duplicate_count,
      })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setLoading(false)
    }
  }

  const toggleCandidate = (word: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(word)) {
        next.delete(word)
      } else {
        next.add(word)
      }
      return next
    })
  }

  const saveSelected = async () => {
    if (selectedCandidates.length === 0) return
    setSaving(true)
    setError('')
    setSummary('')
    try {
      const savedWords: VocabularyWord[] = []
      for (const candidate of selectedCandidates) {
        const saved = await apiFetch<VocabularyWord>('/api/v1/vocabulary', {
          method: 'POST',
          body: JSON.stringify({
            word: candidate.word,
            definition: candidate.definition,
            definition_vi: candidate.definition_vi,
            ipa: candidate.ipa,
            part_of_speech: candidate.part_of_speech,
            topic: candidate.topic,
            example_en: candidate.example_en,
            example_vi: candidate.example_vi,
            use_ai: false,
          }),
        })
        savedWords.push(saved)
        onSaved(saved)
      }
      setSummary(t('importWords.savedSummary', { count: savedWords.length }))
      setResult((current) => current
        ? {
            ...current,
            candidates: current.candidates.map((candidate) =>
              selected.has(candidate.word)
                ? { ...candidate, already_exists: true, existing_word_id: candidate.existing_word_id ?? '' }
                : candidate,
            ),
          }
        : current)
      setSelected(new Set())
      track('vocab_import_candidates_saved', { mode, count: savedWords.length })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="rounded-xl border border-border bg-surface-raised p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="font-semibold text-fg">{t('importWords.title')}</h2>
          <p className="mt-1 max-w-xl text-sm text-muted-fg">{t('importWords.description')}</p>
        </div>
        <div className="inline-flex w-fit rounded-md border border-border bg-bg p-1">
          {(['topic', 'text'] as ImportMode[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => {
                setMode(item)
                setResult(null)
                setSummary('')
              }}
              className={`rounded px-3 py-1 text-xs font-medium ${
                mode === item ? 'bg-primary text-on-primary' : 'text-muted-fg hover:text-fg'
              }`}
            >
              {t(`importWords.modes.${item}`)}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={createCandidates} className="mt-4 space-y-3">
        <label className="block text-xs font-medium text-muted-fg" htmlFor="import-words-input">
          {mode === 'topic' ? t('importWords.topicLabel') : t('importWords.textLabel')}
        </label>
        <textarea
          id="import-words-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={mode === 'topic' ? 2 : 5}
          maxLength={5000}
          placeholder={mode === 'topic' ? t('importWords.topicPlaceholder') : t('importWords.textPlaceholder')}
          className="w-full resize-y rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg"
        />
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <label className="flex w-fit flex-col gap-1 text-xs font-medium text-muted-fg">
            {t('importWords.countLabel')}
            <input
              type="number"
              min={1}
              max={30}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="w-24 rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg"
            />
          </label>
          <button
            type="submit"
            disabled={!trimmed || loading || saving}
            className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Icon name="Sparkles" size="sm" variant="fg" />
            {loading ? t('importWords.generating') : t('importWords.generate')}
          </button>
        </div>
      </form>

      {error && (
        <p className="mt-3 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      {summary && (
        <p className="mt-3 rounded-md border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
          {summary}
        </p>
      )}

      {result && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm font-medium text-fg">
              {t('importWords.previewSummary', {
                count: result.candidates.length,
                duplicates: result.duplicate_count,
              })}
            </p>
            <button
              type="button"
              onClick={() => void saveSelected()}
              disabled={selectedCandidates.length === 0 || saving}
              className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-60"
            >
              <Icon name="Plus" size="sm" variant="fg" />
              {saving
                ? t('importWords.saving')
                : t('importWords.saveSelected', { count: selectedCandidates.length })}
            </button>
          </div>

          <div className="space-y-2">
            {result.candidates.map((candidate) => (
              <label
                key={candidate.word}
                className={`flex gap-3 rounded-lg border p-3 ${
                  candidate.already_exists
                    ? 'border-border bg-bg/60 opacity-70'
                    : 'border-border bg-bg'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selected.has(candidate.word)}
                  disabled={candidate.already_exists || saving}
                  onChange={() => toggleCandidate(candidate.word)}
                  className="mt-1"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="font-semibold text-fg">{candidate.word}</span>
                    {candidate.part_of_speech && (
                      <span className="text-xs text-muted-fg">{candidate.part_of_speech}</span>
                    )}
                    {candidate.already_exists && (
                      <span className="rounded-md bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning">
                        {t('importWords.duplicate')}
                      </span>
                    )}
                  </div>
                  {(candidate.definition_vi || candidate.definition) && (
                    <p className="mt-1 text-sm text-muted-fg">
                      {candidate.definition_vi || candidate.definition}
                    </p>
                  )}
                </div>
              </label>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

function DailyHistoryWordRow({
  date,
  word,
  t,
}: {
  date: string
  word: DailyHistoryWord
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  return (
    <Link
      to={`/learn/vocab/${encodeURIComponent(word.word)}`}
      onClick={() =>
        track('vocab_history_word_detail_opened', {
          date,
          word: word.word,
          word_id: word.word_id,
        })
      }
      className="flex items-center gap-3 py-2.5 hover:text-primary"
    >
      <div className="min-w-0 flex-1">
        <p className="font-medium text-fg truncate">
          {word.word}
          {word.reviewed && (
            <span className="ml-2 text-xs font-normal text-success">
              {t('history.reviewedBadge')}
            </span>
          )}
        </p>
        {(word.definition_vi || word.definition_en) && (
          <p className="mt-0.5 truncate text-xs text-muted-fg">
            {word.definition_vi || word.definition_en}
          </p>
        )}
      </div>
      {word.is_favourite && <Icon name="Heart" size="sm" variant="danger" />}
      <span className="hidden rounded-md bg-surface px-2 py-1 text-xs text-muted-fg sm:inline">
        {t(`strength.${word.strength}`, { defaultValue: word.strength })}
      </span>
      <Icon name="ArrowRight" size="sm" variant="muted" />
    </Link>
  )
}

function DailyHistoryCard({
  entry,
  details,
  loadingDetails,
  isOpen,
  onToggle,
  t,
}: {
  entry: DailyHistoryEntry
  details?: DailyWordsResponse
  loadingDetails: boolean
  isOpen: boolean
  onToggle: () => void
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  const detailWords = details?.words ?? []
  return (
    <article className="rounded-xl border border-border bg-surface-raised p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-fg">{entry.date}</h2>
            {entry.topic && (
              <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {entry.topic}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-fg">
            {t('history.summary', {
              reviewed: entry.reviewed_count,
              total: entry.total_count,
            })}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40"
            aria-expanded={isOpen}
          >
            <Icon name={isOpen ? 'ChevronDown' : 'ChevronRight'} size="sm" variant="muted" />
            {isOpen ? t('history.hideDetails') : t('history.showDetails')}
          </button>
          <Link
            to={`/learn/daily/quiz?date=${encodeURIComponent(entry.date)}`}
            onClick={() =>
              track('vocab_history_review_started', {
                date: entry.date,
                total: entry.total_count,
              })
            }
            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40"
          >
            <Icon name="RotateCcw" size="sm" variant="muted" />
            {t('history.reviewCta')}
          </Link>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {HISTORY_STATS.map(([key, field]) => (
          <div key={key} className="rounded-md bg-surface px-3 py-2">
            <p className="text-xs text-muted-fg">{t(`history.stats.${key}`)}</p>
            <p className="text-lg font-semibold text-fg">{entry[field]}</p>
          </div>
        ))}
      </div>

      {isOpen && (
        <div className="mt-4 divide-y divide-border">
          {loadingDetails ? (
            <div className="py-3 text-sm text-muted-fg">{t('history.loadingDetails')}</div>
          ) : detailWords.length === 0 ? (
            <div className="py-3 text-sm text-muted-fg">{t('history.noDetails')}</div>
          ) : (
            detailWords.map((word) => (
              <DailyHistoryWordRow
                key={`${entry.date}-${word.word_id || word.word}`}
                date={entry.date}
                word={word}
                t={t}
              />
            ))
          )}
        </div>
      )}
    </article>
  )
}

export function VocabAddPage() {
  const { t } = useTranslation('vocab')
  const [aiUsage, setAiUsage] = useState<AiUsage | null>(null)
  const [savedWords, setSavedWords] = useState<VocabularyWord[]>([])

  useEffect(() => {
    let cancelled = false
    async function loadAiUsage() {
      try {
        const res = await apiFetch<AiUsage>('/api/v1/me/ai-usage')
        if (!cancelled) setAiUsage(res)
      } catch {
        if (!cancelled) setAiUsage(null)
      }
    }
    void loadAiUsage()
    return () => {
      cancelled = true
    }
  }, [])

  const onSaved = (word: VocabularyWord) => {
    setSavedWords((current) => [word, ...current.filter((item) => item.id !== word.id)])
  }

  return (
    <div className="mx-auto max-w-3xl p-4">
      <header className="mb-6">
        <Link
          to="/learn/vocab"
          className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-muted-fg hover:text-fg"
        >
          <Icon name="ArrowLeft" size="sm" variant="muted" />
          {t('addFlow.backToHub', { defaultValue: 'Vocabulary hub' })}
        </Link>
        <h1 className="text-2xl font-bold text-fg">
          {t('addFlow.heading', { defaultValue: 'Add words' })}
        </h1>
        <p className="mt-2 max-w-xl text-sm text-muted-fg">
          {t('addFlow.subtitle', {
            defaultValue: 'Create one strong card or import a small set. Saved words go into My Words.',
          })}
        </p>
        <AiUsageNote usage={aiUsage} t={t} />
      </header>

      <div className="space-y-4">
        <AddWordWithAi t={t} onSaved={onSaved} />
        <ImportWordsPanel t={t} onSaved={onSaved} />
      </div>

      {savedWords.length > 0 && (
        <section className="mt-6 rounded-xl border border-border bg-surface-raised p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-fg">
                {t('addFlow.savedHeading', { defaultValue: 'Saved this session' })}
              </h2>
              <p className="mt-1 text-sm text-muted-fg">
                {t('addFlow.savedSummary', {
                  count: savedWords.length,
                  defaultValue: `${savedWords.length} saved`,
                })}
              </p>
            </div>
            <Link
              to="/learn/vocab/my-words"
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40"
            >
              {t('addFlow.viewMyWords', { defaultValue: 'View My Words' })}
              <Icon name="ArrowRight" size="sm" variant="muted" />
            </Link>
          </div>
          <div className="mt-3 space-y-1.5">
            {savedWords.map((word) => (
              <MyWordRow key={word.id} word={word} t={t} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

export default function VocabHomePage({ initialTab = 'myWords' }: VocabHomePageProps) {
  const { t } = useTranslation('vocab')
  const profile = useProfile()
  const showLinkPrompt = profile != null && profile.id.startsWith('web_')
  const [topics, setTopics] = useState<TopicSummary[]>([])
  const [preferredSlugs, setPreferredSlugs] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<VocabTab>(initialTab)
  const [myWords, setMyWords] = useState<VocabularyWord[]>([])
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [favouriteWords, setFavouriteWords] = useState<VocabularyWord[]>([])
  const [dailyHistory, setDailyHistory] = useState<DailyHistoryEntry[] | null>(null)
  const [openHistoryDate, setOpenHistoryDate] = useState<string | null>(null)
  const [historyDetails, setHistoryDetails] = useState<Record<string, DailyWordsResponse>>({})
  const [loadingHistoryDetails, setLoadingHistoryDetails] = useState<string | null>(null)
  const [loadingMyWords, setLoadingMyWords] = useState(false)
  const [loadingFavourites, setLoadingFavourites] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([
      apiFetch<TopicsResponse>('/api/v1/topics'),
      apiFetch<{ topics: string[] }>('/api/v1/me'),
    ])
      .then(([res, me]) => {
        if (cancelled) return
        setTopics(res.items)
        setPreferredSlugs(Array.isArray(me.topics) ? me.topics : [])
      })
      .catch((e) => !cancelled && setError(localizeError(e)))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (activeTab !== 'myWords') return
    let cancelled = false
    setLoadingMyWords(true)
    const params = new URLSearchParams({ limit: '100' })
    if (sourceFilter !== 'all') params.set('source', sourceFilter)
    apiFetch<WordListResponse>(`/api/v1/vocabulary?${params.toString()}`)
      .then((res) => {
        if (!cancelled) setMyWords(res.items)
      })
      .catch((e) => !cancelled && setError(localizeError(e)))
      .finally(() => !cancelled && setLoadingMyWords(false))
    return () => {
      cancelled = true
    }
  }, [activeTab, sourceFilter])

  useEffect(() => {
    if (activeTab !== 'favourites') return
    let cancelled = false
    setLoadingFavourites(true)
    apiFetch<WordListResponse>('/api/v1/vocabulary?favourite=true&limit=100')
      .then((res) => {
        if (!cancelled) setFavouriteWords(res.items)
      })
      .catch((e) => !cancelled && setError(localizeError(e)))
      .finally(() => !cancelled && setLoadingFavourites(false))
    return () => {
      cancelled = true
    }
  }, [activeTab])

  useEffect(() => {
    if (activeTab !== 'history' || dailyHistory !== null) return
    let cancelled = false
    setLoadingHistory(true)
    async function loadHistory() {
      try {
        const res = await apiFetch<DailyHistoryResponse>('/api/v1/vocabulary/daily/history?limit=30')
        if (!cancelled) setDailyHistory(res.items)
      } catch (e) {
        if (!cancelled) {
          setError(localizeError(e))
          setDailyHistory([])
        }
      } finally {
        if (!cancelled) setLoadingHistory(false)
      }
    }
    void loadHistory()
    return () => {
      cancelled = true
    }
  }, [activeTab, dailyHistory])

  const toggleHistoryDate = async (date: string) => {
    if (openHistoryDate === date) {
      setOpenHistoryDate(null)
      return
    }
    setOpenHistoryDate(date)
    if (historyDetails[date]) return

    setLoadingHistoryDetails(date)
    try {
      const res = await apiFetch<DailyWordsResponse>(
        `/api/v1/vocabulary/daily/${encodeURIComponent(date)}`,
      )
      setHistoryDetails((prev) => ({ ...prev, [date]: res }))
      track('vocab_history_day_expanded', { date, total: res.total_count })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setLoadingHistoryDetails((current) => (current === date ? null : current))
    }
  }

  const stats = useMemo(() => {
    const total = topics.reduce((sum, tp) => sum + tp.word_count, 0)
    const mastered = topics.reduce((sum, tp) => sum + tp.mastered_count, 0)
    return { total, mastered }
  }, [topics])

  const visibleMyWords = useMemo(() => {
    if (statusFilter === 'all') return myWords
    return myWords.filter((word) => word.strength === statusFilter)
  }, [myWords, statusFilter])

  // Preferred topics: shown even with 0 words so the user sees their
  // settings reflected immediately. Sorted least-mastered first among
  // those that have words; 0-word ones trail alphabetically.
  const preferredTopics = useMemo(() => {
    if (preferredSlugs.length === 0) return []
    const byId = Object.fromEntries(topics.map((tp) => [tp.id, tp]))
    return preferredSlugs
      .map((slug) => byId[slug] ?? { id: slug, name: slug, word_count: 0, mastered_count: 0, subtopics: [] })
      .sort((a, b) => {
        if (a.word_count === 0 && b.word_count === 0)
          return topicLabel(a.id, a.name, t).localeCompare(topicLabel(b.id, b.name, t))
        if (a.word_count === 0) return 1
        if (b.word_count === 0) return -1
        const aPct = a.mastered_count / a.word_count
        const bPct = b.mastered_count / b.word_count
        return aPct - bPct
      })
  }, [preferredSlugs, topics, t])

  // Non-preferred topics with at least one word, sorted least-mastered first.
  const otherTopics = useMemo(() => {
    return [...topics]
      .filter((tp) => tp.word_count > 0 && !preferredSlugs.includes(tp.id))
      .sort((a, b) => {
        const aPct = a.mastered_count / a.word_count
        const bPct = b.mastered_count / b.word_count
        if (aPct !== bPct) return aPct - bPct
        return topicLabel(a.id, a.name, t).localeCompare(topicLabel(b.id, b.name, t))
      })
  }, [topics, preferredSlugs, t])

  // Legacy: when no preferred topics set, fall back to all topics with words.
  const orderedTopics = useMemo(() => {
    if (preferredSlugs.length > 0) return []
    return [...topics]
      .filter((tp) => tp.word_count > 0)
      .sort((a, b) => {
        const aPct = a.mastered_count / a.word_count
        const bPct = b.mastered_count / b.word_count
        if (aPct !== bPct) return aPct - bPct
        return topicLabel(a.id, a.name, t).localeCompare(topicLabel(b.id, b.name, t))
      })
  }, [topics, preferredSlugs, t])

  const masteryPct = stats.total === 0 ? 0 : (stats.mastered / stats.total) * 100

  return (
    <div className="max-w-5xl mx-auto p-4">
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-fg">
            {t('myWords.heading', { defaultValue: 'My Vocabulary' })}{' '}
            <span className="inline-block rounded-md bg-primary/10 px-2 py-0.5 text-primary text-xl md:text-2xl">
              {t('myWords.headingPill', { defaultValue: 'My Words' })}
            </span>
          </h1>
          <p className="mt-2 text-sm text-muted-fg max-w-xl">
            {t('myWords.subtitle', {
              defaultValue: 'Your private IELTS vocabulary. Daily words, manual additions, favourites, and reviews all live here.',
            })}
          </p>
        </div>
        {stats.total > 0 && (
          <div className="flex items-center gap-4">
            <Link
              to="/learn/review"
              className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 transition-colors"
            >
              {t('byTopic.reviewCta')}
            </Link>
            <div className="text-right">
              <p className="text-xs text-muted-fg">
                {t('byTopic.progress.label')}
              </p>
              <p className="text-2xl font-bold text-fg">
                {stats.mastered}<span className="text-base text-muted-fg">/{stats.total}</span>
              </p>
            </div>
            <div
              className="relative h-16 w-16 shrink-0 rounded-full"
              style={{
                background: `conic-gradient(var(--color-primary, #0d9488) ${masteryPct}%, var(--color-surface, #f1f5f9) 0)`,
              }}
              aria-label={t('byTopic.progress.aria', { pct: Math.round(masteryPct) })}
            >
              <div className="absolute inset-1.5 rounded-full bg-bg flex items-center justify-center text-sm font-semibold text-fg">
                {Math.round(masteryPct)}%
              </div>
            </div>
          </div>
        )}
      </header>

      <div className="mb-5 flex w-full overflow-x-auto rounded-lg border border-border bg-surface-raised p-1 sm:inline-flex sm:w-auto">
        <button
          type="button"
          onClick={() => {
            if (activeTab !== 'myWords') {
              track('vocab_my_words_tab_viewed')
            }
            setActiveTab('myWords')
          }}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
            activeTab === 'myWords'
              ? 'bg-primary text-primary-fg'
              : 'text-muted-fg hover:text-fg'
          }`}
        >
          <Icon name="BookOpen" size="sm" variant={activeTab === 'myWords' ? 'fg' : 'muted'} />
          {t('byTopic.tabs.myWords', { defaultValue: 'My Words' })}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('topics')}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
            activeTab === 'topics'
              ? 'bg-primary text-primary-fg'
              : 'text-muted-fg hover:text-fg'
          }`}
        >
          <Icon name="BookOpen" size="sm" variant={activeTab === 'topics' ? 'fg' : 'muted'} />
          {t('byTopic.tabs.topics', { defaultValue: 'Topics' })}
        </button>
        <button
          type="button"
          onClick={() => {
            if (activeTab !== 'favourites') {
              track('vocab_favourites_tab_viewed')
            }
            setActiveTab('favourites')
          }}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
            activeTab === 'favourites'
              ? 'bg-primary text-primary-fg'
              : 'text-muted-fg hover:text-fg'
          }`}
        >
          <Icon name="Heart" size="sm" variant={activeTab === 'favourites' ? 'fg' : 'muted'} />
          {t('byTopic.tabs.favourites', { defaultValue: 'Favourites' })}
        </button>
        <button
          type="button"
          onClick={() => {
            if (activeTab !== 'history') {
              track('vocab_history_tab_viewed')
            }
            setActiveTab('history')
          }}
          className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
            activeTab === 'history'
              ? 'bg-primary text-primary-fg'
              : 'text-muted-fg hover:text-fg'
          }`}
        >
          <Icon name="Clock" size="sm" variant={activeTab === 'history' ? 'fg' : 'muted'} />
          {t('byTopic.tabs.history', { defaultValue: 'History' })}
        </button>
      </div>

      {showLinkPrompt && (
        <div
          role="region"
          aria-label={t('linkPrompt.title')}
          className="mb-6 flex flex-col gap-3 rounded-xl border border-primary/30 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex-1">
            <p className="font-semibold text-fg">{t('linkPrompt.title')}</p>
            <p className="text-sm text-muted-fg mt-1">
              {t('linkPrompt.description')}
            </p>
          </div>
          <Link
            to="/settings/link-telegram"
            className="shrink-0 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            {t('linkPrompt.cta')}
          </Link>
        </div>
      )}

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-4 rounded-lg mb-4">
          <p className="text-danger">{error}</p>
        </div>
      )}

      {activeTab === 'history' ? (
        loadingHistory || dailyHistory === null ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="rounded-xl border border-border bg-surface-raised p-4 animate-pulse"
              >
                <div className="h-4 bg-border rounded w-1/4" />
                <div className="mt-4 h-12 bg-border rounded" />
              </div>
            ))}
          </div>
        ) : dailyHistory.length === 0 ? (
          <EmptyState
            illustration="empty-vocab"
            title={t('empty.history.title', { defaultValue: 'No daily history yet' })}
            description={t('empty.history.description', {
              defaultValue: 'Daily vocab batches you generate will appear here for future review.',
            })}
            primaryAction={{ label: t('empty.history.cta', { defaultValue: 'View daily words' }), to: '/learn/daily' }}
          />
        ) : (
          <div className="space-y-4">
            {dailyHistory.map((entry) => (
              <DailyHistoryCard
                key={entry.date}
                entry={entry}
                details={historyDetails[entry.date]}
                loadingDetails={loadingHistoryDetails === entry.date}
                isOpen={openHistoryDate === entry.date}
                onToggle={() => void toggleHistoryDate(entry.date)}
                t={t}
              />
            ))}
          </div>
        )
      ) : activeTab === 'favourites' ? (
        loadingFavourites ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="rounded-lg border border-border bg-surface-raised p-3 animate-pulse"
              >
                <div className="h-4 bg-border rounded w-1/3" />
              </div>
            ))}
          </div>
        ) : favouriteWords.length === 0 ? (
          <EmptyState
            illustration="empty-vocab"
            title={t('empty.favourites.title', { defaultValue: 'No favourite words yet' })}
            description={t('empty.favourites.description', {
              defaultValue: 'Tap the heart on daily words or vocab rows to collect them here.',
            })}
            primaryAction={{ label: t('empty.favourites.cta', { defaultValue: 'View daily words' }), to: '/learn/daily' }}
          />
        ) : (
          <div className="space-y-1.5">
            {favouriteWords.map((word) => (
              <FavouriteWordRow key={word.id} word={word} />
            ))}
          </div>
        )
      ) : activeTab === 'myWords' ? (
        <section className="space-y-4">
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-raised p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-semibold text-fg">{t('myWords.listHeading', { defaultValue: 'My Words' })}</h2>
              <p className="mt-1 text-sm text-muted-fg">
                {t('myWords.listSummary', {
                  visible: visibleMyWords.length,
                  total: myWords.length,
                  defaultValue: `${visibleMyWords.length}/${myWords.length} words`,
                })}
              </p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Link
                to="/learn/vocab/add"
                className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90"
              >
                <Icon name="Plus" size="sm" variant="fg" />
                {t('myWords.addCta', { defaultValue: 'Add words' })}
              </Link>
              <label className="flex flex-col gap-1 text-xs font-medium text-muted-fg">
                {t('myWords.filters.source', { defaultValue: 'Source' })}
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
                  className="rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg"
                >
                  {SOURCE_FILTERS.map((source) => (
                    <option key={source} value={source}>
                      {t(`myWords.sources.${source}`, { defaultValue: source })}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-muted-fg">
                {t('myWords.filters.status', { defaultValue: 'Status' })}
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                  className="rounded-md border border-border bg-bg px-3 py-2 text-sm text-fg"
                >
                  {STATUS_FILTERS.map((status) => (
                    <option key={status} value={status}>
                      {status === 'all'
                        ? t('myWords.statuses.all', { defaultValue: 'All statuses' })
                        : t(`strength.${status}`, { defaultValue: status })}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {loadingMyWords ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-border bg-surface-raised p-3 animate-pulse"
                >
                  <div className="h-4 bg-border rounded w-1/3" />
                </div>
              ))}
            </div>
          ) : myWords.length === 0 ? (
            <EmptyState
              illustration="empty-vocab"
              title={t('empty.myWords.title', { defaultValue: 'No words in My Words yet' })}
              description={t('empty.myWords.description', {
                defaultValue: 'Daily words you generate will appear here automatically.',
              })}
              primaryAction={{ label: t('empty.myWords.cta', { defaultValue: 'View daily words' }), to: '/learn/daily' }}
            />
          ) : visibleMyWords.length === 0 ? (
            <EmptyState
              illustration="empty-vocab"
              title={t('empty.myWordsFiltered.title', { defaultValue: 'No matching words' })}
              description={t('empty.myWordsFiltered.description', {
                defaultValue: 'Try a different source or status filter.',
              })}
              primaryAction={{
                label: t('empty.myWordsFiltered.cta', { defaultValue: 'Clear filters' }),
                onClick: () => {
                  setSourceFilter('all')
                  setStatusFilter('all')
                },
              }}
            />
          ) : (
            <div className="space-y-1.5">
              {visibleMyWords.map((word) => (
                <MyWordRow key={word.id} word={word} t={t} />
              ))}
            </div>
          )}
        </section>
      ) : loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-surface-raised p-4 animate-pulse"
            >
              <div className="h-4 bg-border rounded w-1/2" />
              <div className="h-2 bg-border rounded mt-4 w-full" />
            </div>
          ))}
        </div>
      ) : preferredSlugs.length > 0 ? (
        <div className="space-y-8">
          <section>
            <div className="flex items-baseline gap-2 mb-3">
              <h2 className="text-base font-semibold text-fg">{t('byTopic.yourTopics')}</h2>
              <p className="text-xs text-muted-fg">{t('byTopic.yourTopicsSubtitle')}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {preferredTopics.map((tp) =>
                tp.word_count === 0 ? (
                  <Link
                    key={tp.id}
                    to={`/learn/vocab/topic/${encodeURIComponent(tp.id)}`}
                    className="block rounded-xl border border-dashed border-primary/40 bg-primary/5 p-4 transition-colors hover:border-primary/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  >
                    <p className="font-semibold text-primary truncate">
                      {topicLabel(tp.id, tp.name, t)}
                    </p>
                    <p className="text-xs text-primary/60 mt-2">{t('byTopic.noWordsYet')}</p>
                    <div className="mt-3 h-1.5 bg-primary/10 rounded-full" />
                  </Link>
                ) : (
                  <TopicCard key={tp.id} topic={tp} t={t} />
                )
              )}
            </div>
          </section>

          {otherTopics.length > 0 && (
            <section>
              <h2 className="text-base font-semibold text-fg mb-3">{t('byTopic.otherTopics')}</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {otherTopics.map((tp) => (
                  <TopicCard key={tp.id} topic={tp} t={t} />
                ))}
              </div>
            </section>
          )}
        </div>
      ) : orderedTopics.length === 0 ? (
        <EmptyState
          illustration="empty-vocab"
          title={t('empty.noWords.title')}
          description={t('empty.noWords.description')}
          primaryAction={{ label: t('empty.noWords.cta'), to: '/review' }}
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {orderedTopics.map((tp) => (
            <TopicCard key={tp.id} topic={tp} t={t} />
          ))}
        </div>
      )}
    </div>
  )
}
