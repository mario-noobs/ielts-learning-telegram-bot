import { useEffect, useMemo, useState } from 'react'
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

const STRENGTH_FILTERS: { key: Strength; label: string }[] = [
  { key: 'Weak', label: 'Yếu' },
  { key: 'Learning', label: 'Đang học' },
  { key: 'Good', label: 'Tốt' },
  { key: 'Mastered', label: 'Thạo' },
]

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
  New: 'bg-gray-100 text-gray-700',
  Weak: 'bg-red-100 text-red-700',
  Learning: 'bg-yellow-100 text-yellow-800',
  Good: 'bg-green-100 text-green-700',
  Mastered: 'bg-indigo-100 text-indigo-700',
}

const STRENGTH_LABELS_VI: Record<Strength, string> = {
  New: 'Mới',
  Weak: 'Yếu',
  Learning: 'Đang học',
  Good: 'Tốt',
  Mastered: 'Thạo',
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-semibold mt-1">{value}</p>
    </div>
  )
}

function TopicCard({
  topic,
  count,
  masteredPct,
  selected,
  onClick,
}: {
  topic: TopicSummary
  count: number
  masteredPct: number
  selected: boolean
  onClick: () => void
}) {
  const nameVi = TOPIC_NAMES_VI[topic.id] ?? topic.name
  return (
    <button
      onClick={onClick}
      className={`text-left bg-white rounded-xl shadow-sm p-4 border transition ${
        selected ? 'border-indigo-500 ring-2 ring-indigo-200' : 'border-transparent hover:border-gray-200'
      }`}
    >
      <p className="font-medium">{nameVi}</p>
      <p className="text-xs text-gray-500">{topic.name}</p>
      <p className="text-sm text-gray-600 mt-2">{count} từ</p>
      <div className="mt-3 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-500"
          style={{ width: `${masteredPct}%` }}
        />
      </div>
      <p className="text-xs text-gray-400 mt-1">{Math.round(masteredPct)}% thạo</p>
    </button>
  )
}

function WordCard({ word }: { word: VocabularyWord }) {
  return (
    <Link
      to={`/vocab/${encodeURIComponent(word.word)}`}
      className="bg-white rounded-xl shadow-sm p-4 border border-transparent hover:border-indigo-200 transition block"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-semibold truncate">{word.word}</p>
          {word.ipa && <p className="text-xs text-gray-500 truncate">/{word.ipa}/</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <PronunciationButton word={word.word} compact />
          <span className={`text-xs px-2 py-0.5 rounded-full ${STRENGTH_STYLES[word.strength]}`}>
            {STRENGTH_LABELS_VI[word.strength]}
          </span>
        </div>
      </div>
      {word.definition_vi && (
        <p className="text-sm text-gray-600 mt-2 line-clamp-2">{word.definition_vi}</p>
      )}
      {word.topic && (
        <span className="inline-block mt-2 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
          {TOPIC_NAMES_VI[word.topic] ?? word.topic}
        </span>
      )}
    </Link>
  )
}

export default function VocabHomePage() {
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
      <h1 className="text-2xl font-bold mb-6">Từ vựng</h1>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-lg mb-4">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard label="Tổng số từ" value={loading ? '—' : stats.total} />
        <StatCard label="Đến hạn ôn" value={loading ? '—' : stats.due} />
        <StatCard label="Streak" value="—" />
        <StatCard label="Đã thạo" value={loading ? '—' : stats.mastered} />
      </div>

      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Chủ đề</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {topics.map((t) => {
            const entry = topicCounts.get(t.id) ?? { count: 0, mastered: 0 }
            const pct = entry.count === 0 ? 0 : (entry.mastered / entry.count) * 100
            return (
              <TopicCard
                key={t.id}
                topic={t}
                count={entry.count}
                masteredPct={pct}
                selected={selectedTopic === t.id}
                onClick={() => setSelectedTopic((cur) => (cur === t.id ? null : t.id))}
              />
            )
          })}
        </div>
      </section>

      <section>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
          <h2 className="text-lg font-semibold">Danh sách từ</h2>
          <input
            type="search"
            value={searchRaw}
            onChange={(e) => setSearchRaw(e.target.value)}
            placeholder="Tìm từ, nghĩa..."
            className="w-full md:w-72 px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 mb-4">
          {STRENGTH_FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() =>
                setSelectedStrength((cur) => (cur === f.key ? null : f.key))
              }
              aria-pressed={selectedStrength === f.key}
              className={`text-sm px-3 py-2 min-h-[44px] rounded-full border transition-colors duration-base ${
                selectedStrength === f.key
                  ? 'bg-primary text-primary-fg border-primary'
                  : 'bg-surface-raised text-fg border-border hover:border-primary/60'
              }`}
            >
              {f.label}
            </button>
          ))}
          {selectedTopic && (
            <button
              onClick={() => setSelectedTopic(null)}
              className="text-sm px-3 py-1 rounded-full bg-gray-100 text-gray-700 hover:bg-gray-200"
            >
              Bỏ lọc: {TOPIC_NAMES_VI[selectedTopic] ?? selectedTopic} ×
            </button>
          )}
          <span className="text-sm text-gray-500 ml-auto">
            {filteredWords.length} / {words.length} từ
          </span>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-white rounded-xl shadow-sm p-4 animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-1/3 mb-2" />
                <div className="h-3 bg-gray-200 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : filteredWords.length === 0 ? (
          words.length === 0 ? (
            <EmptyState
              illustration="empty-vocab"
              title="Chưa có từ vựng nào"
              description="Học từ qua Telegram bot hoặc bắt đầu một bài quiz để thêm từ đầu tiên."
              primaryAction={{ label: 'Bắt đầu ôn tập', to: '/review' }}
            />
          ) : (
            <EmptyState
              illustration="empty-vocab"
              title="Không có từ phù hợp"
              description="Thử bỏ bớt bộ lọc hoặc đổi từ khoá tìm kiếm."
              primaryAction={{
                label: 'Xoá bộ lọc',
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
              <WordCard key={w.id} word={w} />
            ))}
          </div>
        )}

        {nextCursor && (
          <div className="flex justify-center mt-6">
            <button
              onClick={loadMore}
              disabled={loadingMore}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {loadingMore ? 'Đang tải...' : 'Tải thêm'}
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
