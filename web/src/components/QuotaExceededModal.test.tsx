import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import QuotaExceededModal from './QuotaExceededModal'

vi.mock('../contexts/AuthContext', () => ({
  useProfile: () => ({
    id: 'u1',
    name: 'Test',
    role: 'user',
    plan: 'free',
  }),
}))

const t = (key: string, vars?: Record<string, unknown>) => {
  if (!vars) return key
  return `${key}|${JSON.stringify(vars)}`
}
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t }),
}))

function renderModal() {
  return render(
    <MemoryRouter>
      <QuotaExceededModal />
    </MemoryRouter>,
  )
}

function fireQuotaEvent(detail: Record<string, unknown> = {}) {
  act(() => {
    window.dispatchEvent(new CustomEvent('quota:exceeded', { detail }))
  })
}

describe('<QuotaExceededModal> (US-M13.3)', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('opens on the quota:exceeded window event', async () => {
    renderModal()
    expect(screen.queryByText('aiUsage.modal.title')).not.toBeInTheDocument()
    fireQuotaEvent({ plan_quota: 10, used: 11, feature: 'quiz', plan: 'free' })
    expect(await screen.findByText('aiUsage.modal.title')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toHaveAccessibleName('aiUsage.modal.title')
  })

  it('opens at most once per saturation event (per UTC day)', async () => {
    const user = userEvent.setup()
    renderModal()
    fireQuotaEvent({ plan_quota: 10, used: 11 })
    expect(await screen.findByText('aiUsage.modal.title')).toBeInTheDocument()

    // Close via the secondary "Got it" button so Radix unmounts the content.
    await user.click(screen.getByText('aiUsage.modal.secondary'))
    expect(screen.queryByText('aiUsage.modal.title')).not.toBeInTheDocument()

    // Re-fire same saturation event — should NOT re-open thanks to the
    // sessionStorage guard.
    fireQuotaEvent({ plan_quota: 10, used: 11 })
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.queryByText('aiUsage.modal.title')).not.toBeInTheDocument()
  })
})
