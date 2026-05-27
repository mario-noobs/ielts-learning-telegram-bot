import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import AudioPlayer from '../components/AudioPlayer'
import Icon from '../components/Icon'
import LoadingScreen from '../components/LoadingScreen'
import DictationExercise from '../components/DictationExercise'
import GapFillExercise from '../components/GapFillExercise'
import ComprehensionExercise from '../components/ComprehensionExercise'
import {
  EXERCISE_ICONS,
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
      .catch((e) => setError(localizeError(e)))
  }, [id])

  if (error) {
    return (
      <div className="max-w-2xl mx-auto p-4 space-y-4">
        <Link to="/practice/listening" className="text-sm text-muted-fg hover:text-fg">
          ← {t('heading')}
        </Link>
        <div className="bg-danger/10 border-l-4 border-danger p-3 rounded text-danger">
          {error}
        </div>
      </div>
    )
  }

  if (!exercise) {
    return <LoadingScreen className="mx-auto max-w-2xl p-4" />
  }

  const handleSubmitted = () => {
    // Optional: could refresh history list
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/practice/listening" className="text-sm text-muted-fg hover:text-fg">
          {t('heading')}
        </Link>
        <Link
          to="/practice/listening/history"
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
