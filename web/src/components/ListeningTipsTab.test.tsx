import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import ListeningTipsTab from './ListeningTipsTab'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const t = (key: string) => key
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t, i18n: { language: 'en' } }),
}))

const MOCK_TIPS = {
  tips: [
    { id: 'tip_1', title: 'Preview questions first', body: 'Read before listening.', category: 'strategy' },
    { id: 'tip_2', title: 'Build topic vocab', body: 'Learn **academic** terms.', category: 'vocabulary' },
    { id: 'tip_3', title: 'Train connected speech', body: '- gonna\n- wanna', category: 'pronunciation' },
    { id: 'tip_4', title: 'Anticipate answer types', body: 'Note if you need a date.', category: 'exam_technique' },
    { id: 'tip_5', title: 'Stay calm', body: 'Miss one? Move on.', category: 'mindset' },
  ],
}

function renderTab() {
  return render(
    <MemoryRouter>
      <ListeningTipsTab locale="en" />
    </MemoryRouter>,
  )
}

describe('<ListeningTipsTab> (US-M15.6)', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('renders 5 tip cards after loading', async () => {
    apiFetchMock.mockResolvedValueOnce(MOCK_TIPS)
    renderTab()
    // Loading skeletons present initially (aria-busy)
    expect(screen.getByRole('list').closest('[aria-busy="true"]')).toBeTruthy()
    await waitFor(() => {
      expect(screen.getByText('Preview questions first')).toBeInTheDocument()
    })
    expect(screen.getAllByRole('listitem')).toHaveLength(5)
  })

  it('renders a list with role="list"', async () => {
    apiFetchMock.mockResolvedValueOnce(MOCK_TIPS)
    renderTab()
    await waitFor(() => screen.getByText('Preview questions first'))
    expect(screen.getByRole('list')).toBeInTheDocument()
  })

  it('refresh button triggers re-fetch with fresh=true', async () => {
    apiFetchMock.mockResolvedValue(MOCK_TIPS)
    const user = userEvent.setup()
    renderTab()
    await waitFor(() => screen.getByText('Preview questions first'))

    const refreshBtn = screen.getByRole('button', { name: 'tips.refreshAriaLabel' })
    await user.click(refreshBtn)

    expect(apiFetchMock).toHaveBeenCalledTimes(2)
    const secondCall = apiFetchMock.mock.calls[1][0] as string
    expect(secondCall).toContain('fresh=true')
  })

  it('shows error state with retry button on failure', async () => {
    apiFetchMock.mockRejectedValueOnce({ code: 'common.unknown_error', httpStatus: 500 })
    renderTab()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /tips.retryBtn/ })).toBeInTheDocument()
    })
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })

  it('retry button re-fetches after error', async () => {
    apiFetchMock
      .mockRejectedValueOnce({ code: 'common.unknown_error', httpStatus: 500 })
      .mockResolvedValueOnce(MOCK_TIPS)
    const user = userEvent.setup()
    renderTab()
    await waitFor(() => screen.getByRole('button', { name: /tips.retryBtn/ }))
    await user.click(screen.getByRole('button', { name: /tips.retryBtn/ }))
    await waitFor(() => screen.getByText('Preview questions first'))
    expect(screen.getAllByRole('listitem')).toHaveLength(5)
  })
})
