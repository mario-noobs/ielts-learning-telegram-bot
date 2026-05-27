import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import DailyWordsPage from './DailyWordsPage'

const apiStreamMock = vi.fn()
const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
  apiStream: (...args: unknown[]) => apiStreamMock(...args),
}))

const trackMock = vi.fn()
vi.mock('../lib/analytics', () => ({
  track: (...args: unknown[]) => trackMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: { language: 'en' },
    t: (k: string, vars?: Record<string, unknown>) =>
      vars ? `${k}|${JSON.stringify(vars)}` : k,
  }),
}))

function streamFromEvents(events: unknown[]) {
  const chunks = events.map((event) =>
    new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`),
  )
  let index = 0
  return {
    body: {
      getReader: () => ({
        read: async () => {
          if (index >= chunks.length) return { done: true, value: undefined }
          return { done: false, value: chunks[index++] }
        },
      }),
    },
  }
}

describe('<DailyWordsPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
    apiStreamMock.mockReset()
    trackMock.mockReset()
  })

  it('renders daily progress and reset status from the stream start event', async () => {
    apiStreamMock.mockResolvedValue(streamFromEvents([
      {
        type: 'start',
        count: 2,
        topic: 'education',
        date: '2026-05-27',
        status: {
          reviewed_count: 1,
          total_count: 2,
          timezone: 'Asia/Ho_Chi_Minh',
          next_reset_at: '2026-05-28T00:00:00+07:00',
        },
      },
      {
        type: 'word',
        word: {
          word: 'scalability',
          word_id: 'w1',
          reviewed: true,
          definition_en: 'ability to grow',
          definition_vi: 'kha nang mo rong',
          ipa: '',
          part_of_speech: 'noun',
          example_en: '',
          example_vi: '',
        },
      },
      { type: 'done' },
    ]))

    render(
      <MemoryRouter>
        <DailyWordsPage />
      </MemoryRouter>,
    )

    expect(
      await screen.findByText(/daily\.status\.progress/),
    ).toHaveTextContent('"reviewed":1')
    expect(screen.getByText(/daily\.status\.reset/)).toBeInTheDocument()
    await waitFor(() =>
      expect(trackMock).toHaveBeenCalledWith('daily_vocab_status_viewed', {
        reviewed_count: 1,
        total_count: 2,
        timezone: 'Asia/Ho_Chi_Minh',
      }),
    )
  })
})
