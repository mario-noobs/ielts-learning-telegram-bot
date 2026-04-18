import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect, useRef } from 'react'
import { ToastProvider, useToast } from './Toast'

function Trigger() {
  const { toast } = useToast()
  return (
    <button
      onClick={() =>
        toast({
          title: 'Đã lưu',
          description: 'Cài đặt đồng bộ xong.',
          variant: 'success',
        })
      }
    >
      Show
    </button>
  )
}

// Imperative trigger — lets us spawn a toast without userEvent, so we can
// drive the dismissal timeline purely through vi.advanceTimersByTime without
// fighting userEvent's async queue.
function ImperativeTrigger({
  onReady,
  duration,
}: {
  onReady: (fire: () => void) => void
  duration?: number
}) {
  const { toast } = useToast()
  const fired = useRef(false)
  useEffect(() => {
    if (fired.current) return
    fired.current = true
    onReady(() =>
      toast({
        title: 'Đã lưu',
        description: 'Cài đặt đồng bộ xong.',
        duration,
      }),
    )
  }, [toast, onReady, duration])
  return null
}

afterEach(() => {
  vi.useRealTimers()
})

describe('<Toast>', () => {
  it('shows a toast when useToast().toast() is called', async () => {
    const user = userEvent.setup()
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'Show' }))
    expect(await screen.findByText('Đã lưu')).toBeInTheDocument()
    expect(screen.getByText('Cài đặt đồng bộ xong.')).toBeInTheDocument()
  })

  it('auto-dismisses after the default duration', async () => {
    vi.useFakeTimers()
    let fire: (() => void) | null = null
    render(
      <ToastProvider defaultDuration={3000}>
        <ImperativeTrigger onReady={(fn) => (fire = fn)} duration={3000} />
      </ToastProvider>,
    )
    act(() => {
      if (fire) fire()
    })
    expect(screen.getByText('Đã lưu')).toBeInTheDocument()

    // Advance past duration + close animation cleanup
    act(() => {
      vi.advanceTimersByTime(3500)
    })
    expect(screen.queryByText('Đã lưu')).not.toBeInTheDocument()
  })
})
