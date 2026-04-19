import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import AudioPlayer from '../components/AudioPlayer'
import Icon from '../components/Icon'
import DictationExercise from '../components/DictationExercise'
import GapFillExercise from '../components/GapFillExercise'
import ComprehensionExercise from '../components/ComprehensionExercise'
import {
  EXERCISE_ICONS,
  ListeningExerciseResult,
  ListeningExerciseView,
  formatDuration,
} from '../lib/listening'

export default function ListeningExercisePage() {
  const { t } = useTranslation('listening')
  const { id = '' } = useParams<{ id: string }>()
  const [exercise, setExercise] = useState<ListeningExerciseView | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    apiFetch<ListeningExerciseView>(`/api/v1/listening/${id}`)
      .then(setExercise)
      .catch((e) => setError((e as Error).message))
  }, [id])

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-4 space-y-4">
        <Link to="/listening" className="text-sm text-muted-fg hover:text-fg">
          ← {t('heading')}
        </Link>
        <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-danger">
          {error}
        </div>
      </div>
    )
  }

  if (!exercise) {
    return (
      <div className="max-w-2xl mx-auto p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-border rounded w-1/3"></div>
          <div className="h-32 bg-surface rounded-xl"></div>
          <div className="h-48 bg-surface rounded-xl"></div>
        </div>
      </div>
    )
  }

  const handleSubmitted = (_r: ListeningExerciseResult) => {
    // Optional: could refresh history list
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/listening" className="text-sm text-muted-fg hover:text-fg">
          {t('heading')}
        </Link>
        <Link
          to="/listening/history"
          className="text-sm text-primary hover:text-primary-hover font-medium"
        >
          {t('historyLink')}
        </Link>
      </div>

      <div>
        <p className="text-sm text-muted-fg inline-flex items-center gap-1.5">
          <Icon name={EXERCISE_ICONS[exercise.exercise_type]} size="sm" variant="primary" />
          {t(`types.${exercise.exercise_type}.title`)} · {t('exercise.band', { band: exercise.band })}
        </p>
        <h1 className="text-2xl font-bold text-fg">{exercise.title}</h1>
        <p className="text-sm text-muted-fg mt-1">
          {t('exercise.estimated', { time: formatDuration(exercise.duration_estimate_sec) })}
          {exercise.topic ? ` · ${exercise.topic}` : ''}
        </p>
      </div>

      <AudioPlayer audioUrl={exercise.audio_url} />

      {exercise.exercise_type === 'dictation' && (
        <DictationExercise exercise={exercise} onSubmitted={handleSubmitted} />
      )}
      {exercise.exercise_type === 'gap_fill' && (
        <GapFillExercise exercise={exercise} onSubmitted={handleSubmitted} />
      )}
      {exercise.exercise_type === 'comprehension' && (
        <ComprehensionExercise exercise={exercise} onSubmitted={handleSubmitted} />
      )}
    </div>
  )
}
