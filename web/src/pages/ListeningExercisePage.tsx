import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import AudioPlayer from '../components/AudioPlayer'
import DictationExercise from '../components/DictationExercise'
import GapFillExercise from '../components/GapFillExercise'
import ComprehensionExercise from '../components/ComprehensionExercise'
import {
  EXERCISE_LABELS,
  ListeningExerciseResult,
  ListeningExerciseView,
  formatDuration,
} from '../lib/listening'

export default function ListeningExercisePage() {
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
        <Link to="/listening" className="text-sm text-gray-500 hover:text-gray-700">
          ← Listening
        </Link>
        <div className="bg-red-50 border-l-4 border-red-500 p-3 rounded text-red-700">
          {error}
        </div>
      </div>
    )
  }

  if (!exercise) {
    return (
      <div className="max-w-2xl mx-auto p-4">
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-32 bg-gray-100 rounded-xl"></div>
          <div className="h-48 bg-gray-100 rounded-xl"></div>
        </div>
      </div>
    )
  }

  const label = EXERCISE_LABELS[exercise.exercise_type]

  const handleSubmitted = (_r: ListeningExerciseResult) => {
    // Optional: could refresh history list
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/listening" className="text-sm text-gray-500 hover:text-gray-700">
          ← Listening
        </Link>
        <Link
          to="/listening/history"
          className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
        >
          Lịch sử
        </Link>
      </div>

      <div>
        <p className="text-sm text-gray-500">
          {label.emoji} {label.title} · Band {exercise.band}
        </p>
        <h1 className="text-2xl font-bold text-gray-900">{exercise.title}</h1>
        <p className="text-sm text-gray-500 mt-1">
          Dự kiến {formatDuration(exercise.duration_estimate_sec)}
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
