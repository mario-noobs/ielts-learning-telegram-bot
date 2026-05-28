import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import VocabHubPage from './VocabHubPage'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const trackMock = vi.fn()
vi.mock('../lib/analytics', () => ({
  track: (...args: unknown[]) => trackMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k: string, vars?: Record<string, unknown>) =>
      vars ? `${k}|${JSON.stringify(vars)}` : k,
  }),
}))

beforeEach(() => {
  apiFetchMock.mockReset()
  trackMock.mockReset()
})

function render_() {
  return render(
    <MemoryRouter>
      <VocabHubPage />
    </MemoryRouter>,
  )
}

describe('<VocabHubPage>', () => {
  it('shows focused vocabulary entry points', async () => {
    render_()

    expect(screen.getByRole('link', { name: /hub\.today\.title/ }))
      .toHaveAttribute('href', '/learn/daily')
    expect(screen.getByRole('link', { name: /hub\.review\.title/ }))
      .toHaveAttribute('href', '/learn/review')
    expect(screen.getByRole('link', { name: /hub\.myWords\.title/ }))
      .toHaveAttribute('href', '/learn/vocab/my-words')
    expect(screen.getByText(/hub\.review\.meta/)).toBeInTheDocument()
    expect(screen.getByText(/hub\.myWords\.meta/)).toBeInTheDocument()
    expect(apiFetchMock).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('link', { name: /hub\.myWords\.title/ }))
    expect(trackMock).toHaveBeenCalledWith('vocab_hub_my_words_opened')
  })

  it('does not load public pools inside the personalized vocab hub', async () => {
    render_()

    expect(screen.getByRole('link', { name: /hub\.today\.title/ }))
      .toHaveAttribute('href', '/learn/daily')
    expect(apiFetchMock).not.toHaveBeenCalled()
    expect(screen.queryByRole('link', { name: /hub\.publicPools\.title/ }))
      .not.toBeInTheDocument()
  })
})
