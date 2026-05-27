import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DailyFillBlankPage from './DailyFillBlankPage'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k: string, vars?: Record<string, unknown>) =>
      vars ? `${k}|${JSON.stringify(vars)}` : k,
  }),
}))

function render_(entry = '/learn/daily/quiz') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/learn/daily/quiz" element={<DailyFillBlankPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('<DailyFillBlankPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('starts a quiz from one selected history day', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/vocabulary/daily/2026-05-27') {
        return Promise.resolve({
          date: '2026-05-27',
          topic: 'Technology',
          words: [
            { word: 'scalability', word_id: 'w1' },
            { word: 'latency', word_id: 'w2' },
          ],
        })
      }
      if (url === '/api/v1/quiz/start') {
        return Promise.resolve({
          session_id: 's1',
          questions: [
            {
              id: 'q0',
              type: 'fill_blank',
              question: 'The system has strong ____.',
              options: ['A. scalability', 'B. latency'],
              word_id: 'w1',
            },
          ],
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    render_('/learn/daily/quiz?date=2026-05-27')

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/vocabulary/daily/2026-05-27', undefined)
    })
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/quiz/start', {
      method: 'POST',
      body: JSON.stringify({
        count: 2,
        types: ['fill_blank'],
        word_ids: ['w1', 'w2'],
      }),
    })
    expect(await screen.findByText('The system has strong ____.')).toBeInTheDocument()
  })
})
