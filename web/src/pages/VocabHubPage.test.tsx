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
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/topics') {
        return Promise.resolve({
          total_words: 12,
          items: [
            { id: 'technology', name: 'Technology', word_count: 10, mastered_count: 4 },
            { id: 'education', name: 'Education', word_count: 2, mastered_count: 2 },
          ],
        })
      }
      if (url === '/api/v1/review/due') {
        return Promise.resolve({ items: [{ word_id: 'w1' }, { word_id: 'w2' }] })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    render_()

    expect(await screen.findByRole('link', { name: /hub\.today\.title/ }))
      .toHaveAttribute('href', '/learn/daily')
    expect(screen.getByRole('link', { name: /hub\.review\.title/ }))
      .toHaveAttribute('href', '/learn/review')
    expect(screen.getByRole('link', { name: /hub\.myWords\.title/ }))
      .toHaveAttribute('href', '/learn/vocab/my-words')
    expect(screen.getByRole('link', { name: /hub\.explore\.title/ }))
      .toHaveAttribute('href', '/learn/vocab/explore')
    expect(screen.getByRole('link', { name: /hub\.add\.title/ }))
      .toHaveAttribute('href', '/learn/vocab/add')
    expect(screen.getByText(/hub\.review\.meta/)).toBeInTheDocument()
    expect(screen.getByText(/hub\.myWords\.meta/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('link', { name: /hub\.add\.title/ }))
    expect(trackMock).toHaveBeenCalledWith('vocab_hub_add_opened')
  })
})
