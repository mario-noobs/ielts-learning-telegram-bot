import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import DailyWordsPage, { __resetDailyWordsCacheForTest } from './DailyWordsPage'

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

function streamWithPause(events: unknown[]) {
  const chunks = events.map((event) =>
    new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`),
  )
  let index = 0
  let release: (() => void) | null = null
  const wait = new Promise<void>((resolve) => {
    release = resolve
  })
  return {
    release: () => release?.(),
    response: {
      body: {
        getReader: () => ({
          read: async () => {
            if (index < chunks.length) return { done: false, value: chunks[index++] }
            await wait
            return { done: true, value: undefined }
          },
        }),
      },
    },
  }
}

describe('<DailyWordsPage>', () => {
  beforeEach(() => {
    __resetDailyWordsCacheForTest()
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

  it('shows generation progress and interpolates word count without raw template text', async () => {
    const stream = streamWithPause([
      {
        type: 'start',
        count: 2,
        topic: 'education',
        date: '2026-05-27',
        status: {
          reviewed_count: 0,
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
          reviewed: false,
          definition_en: 'ability to grow',
          definition_vi: '',
          ipa: '',
          part_of_speech: 'noun',
          example_en: '',
          example_vi: '',
        },
      },
    ])
    apiStreamMock.mockResolvedValue(stream.response)

    const { unmount } = render(
      <MemoryRouter>
        <DailyWordsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText(/daily\.generation\.stages\./)).toBeInTheDocument()
    expect(screen.getByText(/daily\.generation\.count/)).toHaveTextContent('"current":1')
    expect(screen.getByText(/daily\.generating/)).not.toHaveTextContent('{{count}}')

    stream.release()
    unmount()
  })

  it('adds extra daily words and updates remaining allowance', async () => {
    apiStreamMock.mockResolvedValue(streamFromEvents([
      {
        type: 'start',
        count: 1,
        topic: 'technology',
        date: '2026-05-27',
        status: {
          reviewed_count: 1,
          total_count: 1,
          timezone: 'Asia/Ho_Chi_Minh',
          next_reset_at: '2026-05-28T00:00:00+07:00',
          extra_limit: 5,
          extra_used: 0,
          extra_remaining: 5,
        },
      },
      {
        type: 'word',
        word: {
          word: 'base',
          word_id: 'w1',
          reviewed: true,
          definition_en: 'base definition',
          definition_vi: '',
          ipa: '',
          part_of_speech: 'noun',
          example_en: '',
          example_vi: '',
        },
      },
      { type: 'done' },
    ]))
    apiFetchMock.mockResolvedValue({
      date: '2026-05-27',
      topic: 'technology',
      reviewed_count: 1,
      total_count: 2,
      timezone: 'Asia/Ho_Chi_Minh',
      next_reset_at: '2026-05-28T00:00:00+07:00',
      extra_limit: 5,
      extra_used: 1,
      extra_remaining: 4,
      words: [
        {
          word: 'base',
          word_id: 'w1',
          reviewed: true,
          definition_en: 'base definition',
          definition_vi: '',
          ipa: '',
          part_of_speech: 'noun',
          example_en: '',
          example_vi: '',
        },
        {
          word: 'resilient',
          word_id: 'w2',
          daily_source: 'extra',
          reviewed: false,
          definition_en: 'able to recover',
          definition_vi: '',
          ipa: '',
          part_of_speech: 'adjective',
          example_en: '',
          example_vi: '',
        },
      ],
    })

    render(
      <MemoryRouter>
        <DailyWordsPage />
      </MemoryRouter>,
    )

    const learnMore = await screen.findByRole('button', {
      name: /daily\.learnMore\.cta/,
    })
    expect(screen.getByText(/daily\.learnMore\.description/)).toHaveTextContent('"remaining":5')

    await userEvent.click(learnMore)

    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/vocabulary/daily/extra', {
      method: 'POST',
      body: JSON.stringify({ count: 5 }),
    })
    expect(await screen.findByText('resilient')).toBeInTheDocument()
    expect(screen.getByText('daily.learnMore.badge')).toBeInTheDocument()
    expect(screen.getByText(/daily\.learnMore\.added/)).toHaveTextContent('"count":1')
    expect(trackMock).toHaveBeenCalledWith('daily_vocab_learn_more_clicked', {
      count: 5,
      remaining: 5,
    })
    expect(trackMock).toHaveBeenCalledWith('daily_vocab_extra_words_added', {
      count: 1,
      remaining: 4,
    })
  })

  it('shows the extra-word limit state when allowance is used', async () => {
    apiStreamMock.mockResolvedValue(streamFromEvents([
      {
        type: 'start',
        count: 1,
        topic: 'technology',
        date: '2026-05-27',
        status: {
          reviewed_count: 1,
          total_count: 1,
          timezone: 'Asia/Ho_Chi_Minh',
          next_reset_at: '2026-05-28T00:00:00+07:00',
          extra_limit: 5,
          extra_used: 5,
          extra_remaining: 0,
        },
      },
      {
        type: 'word',
        word: {
          word: 'base',
          word_id: 'w1',
          reviewed: true,
          definition_en: 'base definition',
          definition_vi: '',
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

    expect(await screen.findByText(/daily\.learnMore\.limit/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /daily\.learnMore\.cta/ })).not.toBeInTheDocument()
  })
})
