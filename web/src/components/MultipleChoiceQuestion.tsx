import { useEffect } from 'react'

interface Props {
  options: string[]
  onSubmit: (letter: string) => void
  disabled?: boolean
  mcqOptionAria: (o: { letter: string; text: string }) => string
  keyboardHint: (keys: string) => string
}

export default function MultipleChoiceQuestion({
  options,
  onSubmit,
  disabled = false,
  mcqOptionAria,
  keyboardHint,
}: Props) {
  useEffect(() => {
    if (disabled) return
    const handler = (e: KeyboardEvent) => {
      const k = parseInt(e.key, 10)
      if (k >= 1 && k <= options.length) {
        onSubmit(String.fromCharCode(65 + k - 1))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [options, onSubmit, disabled])

  return (
    <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {options.map((opt, i) => {
          const letter = String.fromCharCode(65 + i)
          return (
            <button
              key={letter}
              onClick={() => onSubmit(letter)}
              disabled={disabled}
              aria-label={mcqOptionAria({ letter, text: opt })}
              className="text-left p-4 min-h-[44px] rounded-xl border-2 border-border bg-surface-raised hover:border-primary hover:bg-primary/5 transition-colors duration-base disabled:opacity-50 disabled:hover:border-border disabled:hover:bg-surface-raised"
            >
              <span className="font-semibold text-primary mr-2">{letter}.</span>
              {opt}
            </button>
          )
        })}
      </div>
      <p className="text-xs text-muted-fg mt-3 text-center">
        {keyboardHint(options.map((_, i) => i + 1).join(' / '))}
      </p>
    </>
  )
}
