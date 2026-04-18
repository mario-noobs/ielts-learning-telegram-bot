import Icon from './Icon'

/**
 * Loading state shown while AI grades the essay (typically 5-15s).
 * Replaces the prior "button text change only" loading state.
 */
export default function SubmissionSkeleton() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="bg-surface-raised rounded-xl border border-border p-6 space-y-4"
    >
      <div className="flex items-center gap-3">
        <div className="animate-pulse">
          <Icon name="Sparkles" size="lg" variant="primary" />
        </div>
        <div>
          <p className="font-semibold text-fg">AI đang chấm bài…</p>
          <p className="text-sm text-muted-fg">
            Mất khoảng 10 giây. Đừng đóng trang nhé.
          </p>
        </div>
      </div>

      <div
        className="h-2 bg-border rounded-full overflow-hidden"
        aria-hidden
      >
        <div className="h-full w-1/3 bg-primary animate-pulse rounded-full" />
      </div>

      <div className="space-y-2" aria-hidden>
        <div className="h-4 bg-border rounded w-2/3 animate-pulse" />
        <div className="h-3 bg-border rounded w-full animate-pulse" />
        <div className="h-3 bg-border rounded w-5/6 animate-pulse" />
        <div className="h-3 bg-border rounded w-4/6 animate-pulse" />
      </div>

      <span className="sr-only">AI đang chấm bài. Vui lòng chờ.</span>
    </div>
  )
}
