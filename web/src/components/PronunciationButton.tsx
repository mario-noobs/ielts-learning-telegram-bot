import { useState } from 'react'
import Icon from './Icon'
import { playPronunciation } from '../lib/audio'

export default function PronunciationButton({
  word,
  compact = false,
}: {
  word: string
  compact?: boolean
}) {
  const [playing, setPlaying] = useState(false)

  const onClick = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (playing) return
    setPlaying(true)
    try {
      await playPronunciation(word)
    } finally {
      setTimeout(() => setPlaying(false), 600)
    }
  }

  const base =
    'inline-flex items-center gap-1 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-60'
  const size = compact ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm'

  return (
    <button onClick={onClick} disabled={playing} aria-label="Phát âm" className={`${base} ${size}`}>
      <Icon name="Play" size={compact ? 'sm' : 'md'} variant="primary" />
      {!compact && <span>Phát âm</span>}
    </button>
  )
}
