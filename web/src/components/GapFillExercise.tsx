import { ListeningExerciseResult, ListeningExerciseView } from '../lib/listening'

interface Props {
  exercise: ListeningExerciseView
  onSubmitted?: (result: ListeningExerciseResult) => void
}

export default function GapFillExercise(_props: Props) {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm text-gray-600">
      Gap fill UI sẽ có trong US-3.4.
    </div>
  )
}
