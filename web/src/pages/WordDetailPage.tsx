import { FormEvent, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Icon from '../components/Icon'
import LoadingScreen from '../components/LoadingScreen'
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

interface TeamMeResponse {
  team: {
    id: string
    name: string
  } | null
}

interface TeamCreateKnowledgePostResponse {
  post: {
    id: string
  }
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
  const [team, setTeam] = useState<TeamMeResponse['team']>(null)
  const [error, setError] = useState<string | null>(null)
  const [shareMessage, setShareMessage] = useState('')
  const [sharing, setSharing] = useState(false)
  const [askTeamOpen, setAskTeamOpen] = useState(false)
  const [askTitle, setAskTitle] = useState('')
  const [askBody, setAskBody] = useState('')
  const [askingTeam, setAskingTeam] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    apiFetch<UserProfile>('/api/v1/me')
      .then((p) => setBand(p.target_band))
      .catch(() => {})
  }, [])

  useEffect(() => {
    apiFetch<TeamMeResponse>('/api/v1/teams/me')
      .then((res) => setTeam(res.team))
      .catch(() => setTeam(null))
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

  const buildAskTeamDraft = (word: EnrichedWord) => {
    const example = word.examples_by_band[highlighted] || Object.values(word.examples_by_band)[0]
    const detailPath = `/learn/vocab/${encodeURIComponent(word.word)}`
    return {
      title: `How can I use "${word.word}" naturally?`,
      body: [
        `I'm reviewing "${word.word}" and want help using it in IELTS answers.`,
        word.definition_en ? `English meaning: ${word.definition_en}` : '',
        word.definition_vi ? `Vietnamese meaning: ${word.definition_vi}` : '',
        example?.en ? `Example: ${example.en}` : '',
        `Word detail: ${detailPath}`,
      ].filter(Boolean).join('\n'),
    }
  }

  const shareWordToTeam = async () => {
    if (!team || !data || sharing) return
    const note = window.prompt(`Ghi chú tùy chọn cho team về "${data.word}"`)
    if (note === null) return
    setSharing(true)
    setShareMessage('')
    setError(null)
    try {
      await apiFetch(`/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts/share-word`, {
        method: 'POST',
        body: JSON.stringify({ word: data.word, note }),
      })
      setShareMessage('Đã chia sẻ từ này với team.')
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setSharing(false)
    }
  }

  const openAskTeam = () => {
    if (!data) return
    const draft = buildAskTeamDraft(data)
    setAskTitle(draft.title)
    setAskBody(draft.body)
    setAskTeamOpen(true)
    setShareMessage('')
  }

  const submitAskTeam = async (event: FormEvent) => {
    event.preventDefault()
    if (!team || !data || askingTeam) return
    const title = askTitle.trim()
    const body = askBody.trim()
    if (!title || !body) return
    setAskingTeam(true)
    setShareMessage('')
    setError(null)
    try {
      const res = await apiFetch<TeamCreateKnowledgePostResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts`,
        {
          method: 'POST',
          body: JSON.stringify({
            type: 'question',
            category: 'vocabulary',
            title,
            body,
            word_context: {
              word: data.word,
              definition_en: data.definition_en,
              definition_vi: data.definition_vi,
              ipa: data.ipa,
              part_of_speech: data.part_of_speech,
              example_en: data.examples_by_band[highlighted]?.en || '',
              example_vi: data.examples_by_band[highlighted]?.vi || '',
              topic: '',
            },
          }),
        },
      )
      setAskTeamOpen(false)
      setShareMessage(`Đã đăng câu hỏi cho team. Post: ${res.post.id}`)
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setAskingTeam(false)
    }
  }

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

      {!data && !error && <LoadingScreen compact title="Loading word" />}

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
            {team && (
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => void shareWordToTeam()}
                  disabled={sharing}
                  className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40 disabled:opacity-60"
                >
                  <Icon name="Users" size="sm" variant="muted" />
                  {sharing ? 'Đang chia sẻ...' : 'Chia sẻ với team'}
                </button>
                <button
                  type="button"
                  onClick={openAskTeam}
                  className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40"
                >
                  <Icon name="Lightbulb" size="sm" variant="muted" />
                  Hỏi team
                </button>
              </div>
            )}
            {askTeamOpen && (
              <form
                onSubmit={submitAskTeam}
                className="mt-4 rounded-lg border border-border bg-bg p-3"
              >
                <label className="block text-sm font-medium text-fg" htmlFor="ask-team-title">
                  Câu hỏi
                  <input
                    id="ask-team-title"
                    value={askTitle}
                    onChange={(event) => setAskTitle(event.target.value)}
                    maxLength={160}
                    className="mt-1 min-h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg"
                  />
                </label>
                <label className="mt-3 block text-sm font-medium text-fg" htmlFor="ask-team-body">
                  Ngữ cảnh
                  <textarea
                    id="ask-team-body"
                    value={askBody}
                    onChange={(event) => setAskBody(event.target.value)}
                    maxLength={2000}
                    rows={6}
                    className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg"
                  />
                </label>
                <div className="mt-3 flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setAskTeamOpen(false)}
                    className="inline-flex min-h-10 items-center rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:bg-surface"
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    disabled={askingTeam || !askTitle.trim() || !askBody.trim()}
                    className="inline-flex min-h-10 items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-60"
                  >
                    {askingTeam && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
                    {askingTeam ? 'Đang đăng...' : 'Đăng câu hỏi'}
                  </button>
                </div>
              </form>
            )}
            {shareMessage && (
              <p className="mt-3 rounded-md border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
                {shareMessage}
              </p>
            )}
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
