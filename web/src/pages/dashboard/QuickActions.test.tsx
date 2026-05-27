import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import QuickActions from './QuickActions'

const trackMock = vi.fn()
vi.mock('../../lib/analytics', () => ({
  track: (...args: unknown[]) => trackMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

function render_() {
  return render(
    <MemoryRouter>
      <QuickActions />
    </MemoryRouter>,
  )
}

describe('<QuickActions>', () => {
  it('links to current canonical learning routes', async () => {
    render_()

    expect(screen.getByRole('link', { name: /quickActions\.daily\.title/ }))
      .toHaveAttribute('href', '/learn/daily')
    expect(screen.getByRole('link', { name: /quickActions\.review\.title/ }))
      .toHaveAttribute('href', '/learn/review')
    expect(screen.getByRole('link', { name: /quickActions\.writing\.title/ }))
      .toHaveAttribute('href', '/practice/writing')
    expect(screen.getByRole('link', { name: /quickActions\.reading\.title/ }))
      .toHaveAttribute('href', '/practice/reading')

    await userEvent.click(screen.getByRole('link', { name: /quickActions\.review\.title/ }))
    expect(trackMock).toHaveBeenCalledWith('dashboard_quick_action_click', {
      action: 'review',
    })
  })
})
