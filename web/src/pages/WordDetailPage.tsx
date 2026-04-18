import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import Icon from '../components/Icon'
import { apiFetch } from '../lib/api'
import { playPronunciation } from '../lib/audio'

interface EnrichedExample {
  en: string
  vi: string
}

interface Collocation {
  phrase: string
  label: string
}

interface EnrichedWord {
  word: string
  ipa: string
  syllable_stress: string
  part_of_speech: string
  definition_en: string
  definition_vi: string
  word_family: string[]
  collocations: Collocation[]
  examples_by_band: Record<string, EnrichedExample>
  ielts_tip: string
}

interface UserProfile {
  target_band: number
}

function bandTier(band: number): string {
  const rounded = Math.round(band)
  return `band-${rounded}`
}

function PlayButton({ word }: { word: string }) {
  const [playing, setPlaying] = useState(false)
  const onClick = async () => {
    if (playing) return
    setPlaying(true)
    try {
      await playPronunciation(word)
    } finally {
      setTimeout(() => setPlaying(false), 600)
    }
  }
  return (
    <button
      onClick={onClick}
      disabled={playing}
      aria-label="Phát âm"
      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-60"
    >
      <Icon name="Play" size="md" variant="primary" />
      <span className="text-sm">Phát âm</span>
    </button>
  )
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-8 bg-gray-200 rounded w-1/2" />
      <div className="h-4 bg-gray-200 rounded w-1/3" />
      <div className="h-20 bg-gray-200 rounded" />
      <div className="h-32 bg-gray-200 rounded" />
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-xl shadow-sm p-5">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">{title}</h2>
      {children}
    </section>
  )
}

function Chips({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((it) => (
        <span key={it} className="px-3 py-1 rounded-full bg-gray-100 text-gray-700 text-sm">
          {it}
        </span>
      ))}
    </div>
  )
}

function CollocationList({ items }: { items: Collocation[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((c, i) => (
        <span
          key={`${c.phrase}-${i}`}
          className="inline-flex items-center gap-1 pl-3 pr-1 py-1 rounded-full bg-gray-100 text-gray-700 text-sm"
        >
          {c.phrase}
          {c.label && (
            <span className="px-2 py-0.5 rounded-full bg-white text-xs text-gray-500">
              {c.label}
            </span>
          )}
        </span>
      ))}
    </div>
  )
}

function ExamplesByBand({
  examples,
  highlighted,
}: {
  examples: Record<string, EnrichedExample>
  highlighted: string
}) {
  const tiers = Object.keys(examples).sort()
  return (
    <div className="space-y-3">
      {tiers.map((tier) => {
        const ex = examples[tier]
        const isActive = tier === highlighted
        return (
          <div
            key={tier}
            className={
              isActive
                ? 'border-2 border-blue-400 bg-blue-50 p-4 rounded-lg'
                : 'border border-gray-200 p-4 rounded-lg'
            }
          >
            <div className="text-xs font-semibold text-gray-500 mb-1">{tier.toUpperCase()}</div>
            {ex.en && <p className="text-gray-900">{ex.en}</p>}
            {ex.vi && <p className="text-gray-500 text-sm mt-1">{ex.vi}</p>}
          </div>
        )
      })}
    </div>
  )
}

export default function WordDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [data, setData] = useState<EnrichedWord | null>(null)
  const [band, setBand] = useState<number>(6.5)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => setBand(p.target_band))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!id) return
    setData(null)
    setError(null)
    apiFetch<EnrichedWord>(`/api/v1/words/${encodeURIComponent(id)}`)
      .then(setData)
      .catch((e) => setError(e.message))
  }, [id, tick])

  const highlighted = bandTier(band)

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-5">
      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-lg flex items-center justify-between">
          <p className="text-red-700">{error}</p>
          <button
            onClick={() => setTick((t) => t + 1)}
            className="text-red-700 underline text-sm"
          >
            Thử lại
          </button>
        </div>
      )}

      {!data && !error && <Skeleton />}

      {data && (
        <>
          <div className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold">{data.word}</h1>
                {data.ipa && <p className="text-gray-500 mt-1">/{data.ipa}/</p>}
                {data.syllable_stress && (
                  <p className="text-gray-400 text-sm">{data.syllable_stress}</p>
                )}
              </div>
              <PlayButton word={data.word} />
            </div>
            {data.part_of_speech && (
              <span className="inline-block mt-3 px-2 py-0.5 rounded bg-purple-100 text-purple-700 text-xs font-medium">
                {data.part_of_speech}
              </span>
            )}
          </div>

          {(data.definition_en || data.definition_vi) && (
            <Section title="Nghĩa">
              {data.definition_en && <p className="text-gray-900">{data.definition_en}</p>}
              {data.definition_vi && (
                <p className="text-gray-600 mt-2">{data.definition_vi}</p>
              )}
            </Section>
          )}

          {data.collocations.length > 0 && (
            <Section title="Collocations">
              <CollocationList items={data.collocations} />
            </Section>
          )}

          {Object.keys(data.examples_by_band).length > 0 && (
            <Section title="Ví dụ theo band">
              <ExamplesByBand examples={data.examples_by_band} highlighted={highlighted} />
            </Section>
          )}

          {data.word_family.length > 0 && (
            <Section title="Word family">
              <Chips items={data.word_family} />
            </Section>
          )}

          {data.ielts_tip && (
            <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-lg">
              <p className="text-sm font-semibold text-amber-800 mb-1">IELTS tip</p>
              <p className="text-amber-900">{data.ielts_tip}</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
