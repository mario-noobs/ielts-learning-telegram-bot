import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Icon from '../components/Icon'
import { apiFetch } from '../lib/api'
import { playPronunciation } from '../lib/audio'
import { localizeError } from '../lib/apiError'

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
  synonyms?: string[]
  antonyms?: string[]
  image_url?: string | null
}

interface UserProfile {
  target_band: number
}

function bandTier(band: number): string {
  if (band >= 8) return '8'
  if (band >= 7) return '7'
  if (band >= 6) return '6'
  return '5'
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
      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-60"
    >
      <Icon name="Play" size="md" variant="primary" />
      <span className="text-sm">Phát âm</span>
    </button>
  )
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-4">
      <div className="h-8 bg-border rounded w-1/2" />
      <div className="h-4 bg-border rounded w-1/3" />
      <div className="h-20 bg-border rounded" />
      <div className="h-32 bg-border rounded" />
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-surface-raised rounded-xl shadow-sm p-5">
      <h2 className="text-sm font-semibold text-muted-fg uppercase tracking-wide mb-3">{title}</h2>
      {children}
    </section>
  )
}

function WordImage({ url, word }: { url: string; word: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return <div aria-hidden="true" className="w-24 h-24 rounded-xl bg-surface shrink-0" />
  }
  return (
    <img
      src={url}
      alt={word}
      loading="lazy"
      onError={() => setFailed(true)}
      className="w-24 h-24 rounded-xl object-cover shrink-0"
    />
  )
}

function SynonymChips({ items }: { items: string[] }) {
  const navigate = useNavigate()
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((w) => (
        <button
          key={w}
          onClick={() => navigate(`/learn/vocab/${encodeURIComponent(w)}`)}
          className="px-3 py-1 rounded-full bg-surface text-fg text-sm hover:bg-primary/10 hover:text-primary transition-colors"
        >
          {w}
        </button>
      ))}
    </div>
  )
}

function Chips({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((it) => (
        <span key={it} className="px-3 py-1 rounded-full bg-surface text-fg text-sm">
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
          className="inline-flex items-center gap-1 pl-3 pr-1 py-1 rounded-full bg-surface text-fg text-sm"
        >
          {c.phrase}
          {c.label && (
            <span className="px-2 py-0.5 rounded-full bg-surface-raised text-xs text-muted-fg">
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
                ? 'border-2 border-primary/60 bg-primary/10 p-4 rounded-lg'
                : 'border border-border p-4 rounded-lg'
            }
          >
            <div className="text-xs font-semibold text-muted-fg mb-1">{tier.toUpperCase()}</div>
            {ex.en && <p className="text-fg">{ex.en}</p>}
            {ex.vi && <p className="text-muted-fg text-sm mt-1">{ex.vi}</p>}
          </div>
        )
      })}
    </div>
  )
}

export default function WordDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
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
      .catch((e) => setError(localizeError(e)))
  }, [id, tick])

  const highlighted = bandTier(band)

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-5">
      <button
        onClick={() => navigate(-1)}
        className="text-sm text-muted-fg hover:text-fg inline-flex items-center gap-1"
      >
        <Icon name="ArrowLeft" size="sm" /> Quay lại
      </button>

      {error && (
        <div className="bg-danger/10 border-l-4 border-danger p-4 rounded-lg flex items-center justify-between">
          <p className="text-danger">{error}</p>
          <button
            onClick={() => setTick((t) => t + 1)}
            className="text-danger underline text-sm"
          >
            Thử lại
          </button>
        </div>
      )}

      {!data && !error && <Skeleton />}

      {data && (
        <>
          <div className="bg-surface-raised rounded-xl shadow-sm p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold text-fg">{data.word}</h1>
                {data.ipa && <p className="text-muted-fg mt-1">/{data.ipa}/</p>}
                {data.syllable_stress && (
                  <p className="text-muted-fg text-sm">{data.syllable_stress}</p>
                )}
              </div>
              {data.image_url && (
                <div className="flex flex-col items-end">
                  <WordImage url={data.image_url} word={data.word} />
                  <p className="text-xs text-muted-fg mt-1 text-right">📷 Unsplash</p>
                </div>
              )}
              <PlayButton word={data.word} />
            </div>
            {data.part_of_speech && (
              <span className="inline-block mt-3 px-2 py-0.5 rounded bg-primary/10 text-primary text-xs font-medium">
                {data.part_of_speech}
              </span>
            )}
          </div>

          {(data.definition_en || data.definition_vi) && (
            <Section title="Nghĩa">
              {data.definition_en && <p className="text-fg">{data.definition_en}</p>}
              {data.definition_vi && (
                <p className="text-muted-fg mt-2">{data.definition_vi}</p>
              )}
            </Section>
          )}

          {(data.synonyms ?? []).length > 0 && (
            <Section title="Đồng nghĩa">
              <SynonymChips items={(data.synonyms ?? []).slice(0, 5)} />
            </Section>
          )}

          {(data.antonyms ?? []).length > 0 && (
            <Section title="Trái nghĩa">
              <SynonymChips items={(data.antonyms ?? []).slice(0, 5)} />
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
            <div className="bg-warning/10 border-l-4 border-warning p-4 rounded-lg">
              <p className="text-sm font-semibold text-warning mb-1">IELTS tip</p>
              <p className="text-fg">{data.ielts_tip}</p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
