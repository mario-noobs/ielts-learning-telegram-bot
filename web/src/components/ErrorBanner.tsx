import Icon from './Icon'

interface Props {
  error: unknown
  onRetry?: () => void
  className?: string
}

function messageOf(e: unknown): string {
  if (!e) return 'Đã xảy ra lỗi không xác định.'
  if (typeof e === 'string') return e
  if (e instanceof Error) return e.message
  return 'Đã xảy ra lỗi không xác định.'
}

export default function ErrorBanner({ error, onRetry, className = '' }: Props) {
  if (!error) return null
  return (
    <div
      role="alert"
      className={`bg-danger/10 border-l-4 border-danger p-3 rounded flex items-start gap-3 ${className}`}
    >
      <Icon name="AlertCircle" size="md" variant="danger" className="mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-danger">{messageOf(error)}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="text-sm font-medium text-danger hover:underline min-h-[44px] px-3"
        >
          Thử lại
        </button>
      )}
    </div>
  )
}
