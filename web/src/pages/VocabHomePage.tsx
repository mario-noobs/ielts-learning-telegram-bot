import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import EmptyState from '../components/EmptyState'
import PronunciationButton from '../components/PronunciationButton'

type Strength = 'New' | 'Weak' | 'Learning' | 'Good' | 'Mastered'

interface VocabularyWord {
  id: string
  word: string
  definition: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  topic: string
  strength: Strength
  srs_next_review: string | null
  added_at: string | null
}

interface WordListResponse {
  items: VocabularyWord[]
  next_cursor: string | null
}

interface TopicSummary {
  id: string
  name: string
  word_count: number
  subtopics: string[]
}

interface TopicsResponse {
  items: TopicSummary[]
  total_words: number
}

const STRENGTH_FILTER_KEYS: Strength[] = ['Weak', 'Learning', 'Good', 'Mastered']

const TOPIC_NAMES_VI: Record<string, string> = {
  education: 'Giáo dục & Học tập',
  environment: 'Môi trường & Thiên nhiên',
  technology: 'Công nghệ & Đổi mới',
  health: 'Sức khỏe & Wellbeing',
  society: 'Xã hội & Văn hóa',
  economy: 'Kinh tế & Kinh doanh',
  government: 'Chính phủ & Pháp luật',
  media: 'Truyền thông & Giao tiếp',
  science: 'Khoa học & Nghiên cứu',
  travel: 'Du lịch',
  food: 'Ẩm thực & Nông nghiệp',
  arts: 'Nghệ thuật & Sáng tạo',
}

const STRENGTH_STYLES: Record<Strength, string> = {
  New: 'bg-surface text-muted-fg',
  Weak: 'bg-danger/10 text-danger',
  Learning: 'bg-warning/10 text-warning',
  Good: 'bg-success/10 text-success',
  Mastered: 'bg-primary/10 text-primary',
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-surface-raised rounded-xl shadow-sm p-4">
      <p className="text-sm text-muted-fg">{label}</p>
      <p className="text-2xl font-semibold mt-1 text-fg">{value}</p>
    </div>
  )
}

function TopicCard({
  topic,
  count,
  masteredPct,
  selected,
  onClick,
  t,
}: {
  topic: TopicSummary
  count: number
  masteredPct: number
  selected: boolean
  onClick: () => void
  t: (k: string, o?: Record<string, unknown>) => string
}) {
  const nameVi = TOPIC_NAMES_VI[topic.id] ?? topic.name
  return (
    <button
      onClick={onClick}
      className={`text-left bg-surface-raised rounded-xl shadow-sm p-4 border transition ${
        selected ? 'border-primary ring-2 ring-primary/30' : 'border-transparent hover:border-border'
      }`}
    >
      <p className="font-medium text-fg">{nameVi}</p>
      <p className="text-xs text-muted-fg">{topic.name}</p>
      <p className="text-sm text-muted-fg mt-2">{t('wordCount', { count })}</p>
      <div className="mt-3 h-1.5 bg-surface rounded-full overflow-hidden">
        <div
          className="h-full bg-primary"
          style={{ width: `${masteredPct}%` }}
        />
      </div>
      <p className="text-xs text-muted-fg mt-1">
        {t('masteryPct', { pct: Math.round(masteredPct) })}
      </p>
    </button>
  )
}

function WordCard({ word, t }: { word: VocabularyWord; t: (k: string) => string }) {
  return (
    <Link
      to={`/vocab/${encodeURIComponent(word.word)}`}
      className="bg-surface-raised rounded-xl shadow-sm p-4 border border-transparent hover:border-primary/30 transition block"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold truncate text-fg">{word.word}</p>
          {word.ipa && <p className="text-xs text-muted-fg truncate">/{word.ipa}/</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <PronunciationButton word={word.word} compact />
          <span className={`text-xs px-2 py-0.5 rounded-full ${STRENGTH_STYLES[word.strength]}`}>
            {t(`strength.${word.strength}`)}
          </span>
        </div>
      </div>
      {word.definition_vi && (
        <p className="text-sm text-muted-fg mt-2 line-clamp-2">{word.definition_vi}</p>
      )}
      {word.topic && (
        <span className="inline-block mt-2 text-xs bg-surface text-muted-fg px-2 py-0.5 rounded">
          {TOPIC_NAMES_VI[word.topic] ?? word.topic}
        </span>
      )}
    </Link>
  )
}

export default function VocabHomePage() {
  const { t } = useTranslation('vocab')
  const [words, setWords] = useState<VocabularyWord[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [topics, setTopics] = useState<TopicSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [searchRaw, setSearchRaw] = useState('')
  const [search, setSearch] = useState('')
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null)
  const [selectedStrength, setSelectedStrength] = useState<Strength | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchRaw.trim().toLowerCase()), 150)
    return () => clearTimeout(t)
  }, [searchRaw])

  useEffect(() => {
    let cancelled = false
    Promise.all([
      apiFetch<WordListResponse>('/api/v1/vocabulary?limit=100'),
      apiFetch<TopicsResponse>('/api/v1/topics'),
    ])
      .then(([wordsRes, topicsRes]) => {
        if (cancelled) return
        setWords(wordsRes.items)
        setNextCursor(wordsRes.next_cursor)
        setTopics(topicsRes.items)
      })
      .catch((e) => !cancelled && setError((e as Error).message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return
    setLoadingMore(true)
    try {
      const res = await apiFetch<WordListResponse>(
        `/api/v1/vocabulary?limit=100&cursor=${encodeURIComponent(nextCursor)}`,
      )
      setWords((prev) => [...prev, ...res.items])
      setNextCursor(res.next_cursor)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoadingMore(false)
    }
  }

  const stats = useMemo(() => {
    const now = Date.now()
    const due = words.filter(
      (w) => w.srs_next_review && new Date(w.srs_next_review).getTime() <= now,
    ).length
    const mastered = words.filter((w) => w.strength === 'Mastered').length
    return { total: words.length, due, mastered }
  }, [words])

  const topicCounts = useMemo(() => {
    const map = new Map<string, { count: number; mastered: number }>()
    for (const w of words) {
      if (!w.topic) continue
      const entry = map.get(w.topic) ?? { count: 0, mastered: 0 }
      entry.count += 1
      if (w.strength === 'Mastered') entry.mastered += 1
      map.set(w.topic, entry)
    }
    return map
  }, [words])

  const filteredWords = useMemo(() => {
    return words.filter((w) => {
      if (selectedTopic && w.topic !== selectedTopic) return false
      if (selectedStrength && w.strength !== selectedStrength) return false
      if (search) {
        const hay = `${w.word} ${w.definition} ${w.definition_vi}`.toLowerCase()
        if (!hay.includes(search)) return false
      }
      return true
    })
  }, [words, search, selectedTopic, selectedStrength])

  return (
    <div className="max-w-5xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-6">{t('heading')}</h1>

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-4 rounded-lg mb-4">
          <p className="text-danger">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard label={t('stats.total')} value={loading ? '—' : stats.total} />
        <StatCard label={t('stats.due')} value={loading ? '—' : stats.due} />
        <StatCard label={t('stats.streak')} value="—" />
        <StatCard label={t('stats.mastered')} value={loading ? '—' : stats.mastered} />
      </div>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">{t('topicsHeading')}</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {topics.map((topic) => {
            const entry = topicCounts.get(topic.id) ?? { count: 0, mastered: 0 }
            const pct = entry.count === 0 ? 0 : (entry.mastered / entry.count) * 100
            return (
              <TopicCard
                key={topic.id}
                topic={topic}
                count={entry.count}
                masteredPct={pct}
                selected={selectedTopic === topic.id}
                onClick={() => setSelectedTopic((cur) => (cur === topic.id ? null : topic.id))}
                t={t}
              />
            )
          })}
        </div>
      </section>

      <section>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
          <h2 className="text-lg font-semibold">{t('listHeading')}</h2>
          <input
            type="search"
            value={searchRaw}
            onChange={(e) => setSearchRaw(e.target.value)}
            placeholder={t('search.placeholder')}
            className="w-full md:w-72 px-3 py-2 border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/30 bg-surface-raised text-fg"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-4">
          {STRENGTH_FILTER_KEYS.map((key) => (
            <button
              key={key}
              onClick={() =>
                setSelectedStrength((cur) => (cur === key ? null : key))
              }
              aria-pressed={selectedStrength === key}
              className={`text-sm px-3 py-2 min-h-[44px] rounded-full border transition-colors duration-base ${
                selectedStrength === key
                  ? 'bg-primary text-primary-fg border-primary'
                  : 'bg-surface-raised text-fg border-border hover:border-primary/60'
              }`}
            >
              {t(`strength.${key}`)}
            </button>
          ))}
          {selectedTopic && (
            <button
              onClick={() => setSelectedTopic(null)}
              className="text-sm px-3 py-1 rounded-full bg-surface text-fg hover:bg-border"
            >
              {t('filters.clearTopic', {
                name: TOPIC_NAMES_VI[selectedTopic] ?? selectedTopic,
              })} ×
            </button>
          )}
          <span className="text-sm text-muted-fg ml-auto">
            {t('filters.countOfTotal', {
              filtered: filteredWords.length,
              total: words.length,
            })}
          </span>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-surface-raised rounded-xl shadow-sm p-4 animate-pulse">
                <div className="h-4 bg-border rounded w-1/3 mb-2" />
                <div className="h-3 bg-border rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : filteredWords.length === 0 ? (
          words.length === 0 ? (
            <EmptyState
              illustration="empty-vocab"
              title={t('empty.noWords.title')}
              description={t('empty.noWords.description')}
              primaryAction={{ label: t('empty.noWords.cta'), to: '/review' }}
            />
          ) : (
            <EmptyState
              illustration="empty-vocab"
              title={t('empty.noMatch.title')}
              description={t('empty.noMatch.description')}
              primaryAction={{
                label: t('empty.noMatch.cta'),
                onClick: () => {
                  setSelectedTopic(null)
                  setSelectedStrength(null)
                  setSearchRaw('')
                },
              }}
            />
          )
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredWords.map((w) => (
              <WordCard key={w.id} word={w} t={t} />
            ))}
          </div>
        )}

        {nextCursor && (
          <div className="flex justify-center mt-6">
            <button
              onClick={loadMore}
              disabled={loadingMore}
              className="px-4 py-2 bg-primary text-primary-fg rounded-lg hover:bg-primary-hover disabled:opacity-50"
            >
              {loadingMore ? t('loadingMore') : t('loadMore')}
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
