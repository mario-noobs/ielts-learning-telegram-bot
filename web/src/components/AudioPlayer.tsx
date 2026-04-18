import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchListeningAudioUrl, formatDuration } from '../lib/listening'

const SPEEDS = [0.75, 1.0, 1.25, 1.5] as const

export default function AudioPlayer({ audioUrl }: { audioUrl: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [objectUrl, setObjectUrl] = useState<string | null>(null)
  const [playing, setPlaying] = useState(false)
  const [current, setCurrent] = useState(0)
  const [duration, setDuration] = useState(0)
  const [speed, setSpeed] = useState<number>(1.0)
  const [plays, setPlays] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setError(null)
    fetchListeningAudioUrl(audioUrl)
      .then((url) => {
        if (!cancelled) setObjectUrl(url)
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message)
      })
    return () => {
      cancelled = true
    }
  }, [audioUrl])

  useEffect(() => {
    const el = audioRef.current
    if (!el) return
    el.playbackRate = speed
  }, [speed, objectUrl])

  const togglePlay = useCallback(() => {
    const el = audioRef.current
    if (!el) return
    if (el.paused) {
      el.play()
      setPlays((p) => p + 1)
    } else {
      el.pause()
    }
  }, [])

  const restart = useCallback(() => {
    const el = audioRef.current
    if (!el) return
    el.currentTime = 0
    el.play()
    setPlays((p) => p + 1)
  }, [])

  const onSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const el = audioRef.current
    if (!el) return
    const t = Number(e.target.value)
    el.currentTime = t
    setCurrent(t)
  }

  if (error) {
    return (
      <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded text-sm text-red-700">
        Không tải được audio: {error}
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
      {objectUrl && (
        <audio
          ref={audioRef}
          src={objectUrl}
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
          onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
        />
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={togglePlay}
          disabled={!objectUrl}
          className="w-12 h-12 rounded-full bg-indigo-600 text-white flex items-center justify-center hover:bg-indigo-700 disabled:opacity-50"
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? (
            <svg viewBox="0 0 20 20" className="w-6 h-6" fill="currentColor">
              <rect x="5" y="4" width="3" height="12" rx="1" />
              <rect x="12" y="4" width="3" height="12" rx="1" />
            </svg>
          ) : (
            <svg viewBox="0 0 20 20" className="w-6 h-6" fill="currentColor">
              <path d="M5 4l12 6-12 6V4z" />
            </svg>
          )}
        </button>

        <button
          onClick={restart}
          disabled={!objectUrl}
          className="text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50"
          aria-label="Replay from start"
        >
          ⟲ Nghe lại
        </button>

        <span className="text-xs text-gray-500 ml-auto font-mono">
          {formatDuration(current)} / {formatDuration(duration)}
        </span>
      </div>

      <input
        type="range"
        min={0}
        max={Math.max(0, duration)}
        value={current}
        step={0.1}
        onChange={onSeek}
        disabled={!objectUrl}
        className="w-full accent-indigo-600"
      />

      <div className="flex items-center justify-between">
        <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden text-xs">
          {SPEEDS.map((s) => (
            <button
              key={s}
              onClick={() => setSpeed(s)}
              className={`px-2.5 py-1 ${
                speed === s
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              {s}×
            </button>
          ))}
        </div>
        <span className="text-xs text-gray-500">Đã nghe {plays} lần</span>
      </div>
    </div>
  )
}
