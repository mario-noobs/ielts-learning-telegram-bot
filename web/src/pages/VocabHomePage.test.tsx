import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import VocabHomePage from './VocabHomePage'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

const trackMock = vi.fn()
vi.mock('../lib/analytics', () => ({
  track: (...args: unknown[]) => trackMock(...args),
}))

const useProfileMock = vi.fn(() => null as unknown)
vi.mock('../contexts/AuthContext', () => ({
  useProfile: () => useProfileMock(),
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
  useProfileMock.mockReset()
  useProfileMock.mockReturnValue(null)
})

function render_() {
  return render(
    <MemoryRouter>
      <VocabHomePage />
    </MemoryRouter>,
  )
}

describe('<VocabHomePage>', () => {
  it('previews and saves an AI word card', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/topics') return Promise.resolve({ items: [], total_words: 0 })
      if (url === '/api/v1/me') return Promise.resolve({ topics: [] })
      if (url === '/api/v1/me/ai-usage') {
        return Promise.resolve({
          plan: 'free',
          quota_daily: 10,
          used_today: 3,
          by_feature: [{ feature: 'vocab', count: 3 }],
          reset_at: '2026-05-28T00:00:00+00:00',
        })
      }
      if (url === '/api/v1/vocabulary?limit=100') {
        return Promise.resolve({ items: [], next_cursor: null })
      }
      if (url === '/api/v1/vocabulary/draft') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({
          word: 'latency',
          definition: 'delay before transfer',
          definition_vi: 'do tre',
          ipa: 'leɪtənsi',
          part_of_speech: 'noun',
          topic: 'technology',
          example_en: 'Latency affects video calls.',
          example_vi: 'Do tre anh huong cuoc goi video.',
          ielts_tip: 'Use it for technology systems.',
          already_exists: false,
          existing_word_id: null,
        })
      }
      if (url === '/api/v1/vocabulary') {
        expect(options?.method).toBe('POST')
        expect(JSON.parse(String(options?.body))).toMatchObject({
          word: 'latency',
          definition: 'delay before transfer',
          use_ai: false,
        })
        return Promise.resolve({
          id: 'w-latency',
          word: 'latency',
          definition: 'delay before transfer',
          definition_vi: 'do tre',
          ipa: 'leɪtənsi',
          part_of_speech: 'noun',
          topic: 'technology',
          strength: 'New',
          source: 'manual',
          is_favourite: false,
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    render_()

    await userEvent.type(await screen.findByLabelText(/addWord\.inputLabel/), 'latency')
    expect(await screen.findByText(/limits\.aiUsage/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /addWord\.generate/ }))

    expect(await screen.findByText('delay before transfer')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /addWord\.save/ }))

    expect(await screen.findByRole('link', { name: /latency/ })).toBeInTheDocument()
    expect(trackMock).toHaveBeenCalledWith('vocab_ai_word_saved', {
      word: 'latency',
      used_draft: true,
    })
  })

  it('imports candidates from text and saves selected non-duplicates', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/topics') return Promise.resolve({ items: [], total_words: 0 })
      if (url === '/api/v1/me') return Promise.resolve({ topics: [] })
      if (url === '/api/v1/vocabulary?limit=100') {
        return Promise.resolve({ items: [], next_cursor: null })
      }
      if (url === '/api/v1/vocabulary/import/draft') {
        expect(options?.method).toBe('POST')
        expect(JSON.parse(String(options?.body))).toMatchObject({
          mode: 'text',
          input: 'Cities need resilience and adaptation.',
          count: 5,
        })
        return Promise.resolve({
          mode: 'text',
          input: 'Cities need resilience and adaptation.',
          candidates: [
            {
              word: 'resilience',
              definition: 'ability to recover',
              definition_vi: 'kha nang phuc hoi',
              ipa: '',
              part_of_speech: 'noun',
              topic: '',
              example_en: '',
              example_vi: '',
              ielts_tip: '',
              already_exists: true,
              existing_word_id: 'w-existing',
            },
            {
              word: 'adaptation',
              definition: 'change to fit conditions',
              definition_vi: 'su thich nghi',
              ipa: '',
              part_of_speech: 'noun',
              topic: '',
              example_en: '',
              example_vi: '',
              ielts_tip: '',
              already_exists: false,
              existing_word_id: null,
            },
          ],
          duplicate_count: 1,
          max_candidates: 5,
          max_input_chars: 1000,
        })
      }
      if (url === '/api/v1/vocabulary') {
        expect(options?.method).toBe('POST')
        expect(JSON.parse(String(options?.body))).toMatchObject({
          word: 'adaptation',
          use_ai: false,
        })
        return Promise.resolve({
          id: 'w-adaptation',
          word: 'adaptation',
          definition: 'change to fit conditions',
          definition_vi: 'su thich nghi',
          ipa: '',
          part_of_speech: 'noun',
          topic: '',
          strength: 'New',
          source: 'manual',
          is_favourite: false,
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    render_()

    await userEvent.click(await screen.findByRole('button', { name: /importWords\.modes\.text/ }))
    await userEvent.type(screen.getByLabelText(/importWords\.textLabel/), 'Cities need resilience and adaptation.')
    await userEvent.click(screen.getByRole('button', { name: /importWords\.generate/ }))

    expect(await screen.findByText('adaptation')).toBeInTheDocument()
    expect(screen.getByText(/importWords\.duplicate/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /importWords\.saveSelected/ }))

    expect(await screen.findByRole('link', { name: /adaptation/ })).toBeInTheDocument()
    expect(apiFetchMock).not.toHaveBeenCalledWith(
      '/api/v1/vocabulary',
      expect.objectContaining({ body: expect.stringContaining('resilience') }),
    )
  })

  it('renders My Words by default and filters by source/status', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/topics') {
        return Promise.resolve({ items: [], total_words: 2 })
      }
      if (url === '/api/v1/me') {
        return Promise.resolve({ topics: [] })
      }
      if (url === '/api/v1/vocabulary?limit=100') {
        return Promise.resolve({
          items: [
            {
              id: 'w1',
              word: 'scalability',
              definition: 'ability to grow',
              definition_vi: 'kha nang mo rong',
              ipa: '',
              part_of_speech: 'noun',
              topic: 'technology',
              strength: 'Weak',
              source: 'daily',
              is_favourite: false,
            },
            {
              id: 'w2',
              word: 'resilience',
              definition: 'ability to recover',
              definition_vi: 'kha nang phuc hoi',
              ipa: '',
              part_of_speech: 'noun',
              topic: 'society',
              strength: 'Mastered',
              source: 'manual',
              is_favourite: true,
            },
          ],
          next_cursor: null,
        })
      }
      if (url === '/api/v1/vocabulary?limit=100&source=manual') {
        return Promise.resolve({
          items: [
            {
              id: 'w2',
              word: 'resilience',
              definition: 'ability to recover',
              definition_vi: 'kha nang phuc hoi',
              ipa: '',
              part_of_speech: 'noun',
              topic: 'society',
              strength: 'Mastered',
              source: 'manual',
              is_favourite: true,
            },
          ],
          next_cursor: null,
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    render_()

    expect(await screen.findByRole('link', { name: /scalability/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /resilience/ })).toBeInTheDocument()
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/vocabulary?limit=100')

    await userEvent.selectOptions(screen.getByLabelText(/myWords\.filters\.source/), 'manual')

    expect(await screen.findByRole('link', { name: /resilience/ })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /scalability/ })).not.toBeInTheDocument()
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/vocabulary?limit=100&source=manual')

    await userEvent.selectOptions(screen.getByLabelText(/myWords\.filters\.status/), 'Weak')

    expect(screen.getByText(/empty\.myWordsFiltered\.title/)).toBeInTheDocument()
  })

  it('renders topic cards sorted by least-mastered first', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/topics') {
        return Promise.resolve({
          items: [
            { id: 'education', name: 'Education', word_count: 10, mastered_count: 8, subtopics: [] },
            { id: 'environment', name: 'Environment', word_count: 10, mastered_count: 2, subtopics: [] },
            { id: 'technology', name: 'Technology', word_count: 0, mastered_count: 0, subtopics: [] },
          ],
          total_words: 20,
        })
      }
      if (url === '/api/v1/me') return Promise.resolve({ topics: [] })
      if (url === '/api/v1/vocabulary?limit=100') return Promise.resolve({ items: [], next_cursor: null })
      throw new Error(`Unexpected API call: ${url}`)
    })

    render_()
    await userEvent.click(await screen.findByRole('button', { name: /byTopic\.tabs\.topics/ }))
    // Topics with words are linked. Empty topics (Technology) aren't.
    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: /topicNames\.education/ }),
      ).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('link', { name: /topicNames\.technology/ }),
    ).not.toBeInTheDocument()
    // Environment (20% mastered) should appear before Education (80%).
    const links = screen.getAllByRole('link')
    const envIdx = links.findIndex((l) =>
      l.getAttribute('href')?.includes('environment'),
    )
    const eduIdx = links.findIndex((l) =>
      l.getAttribute('href')?.includes('education'),
    )
    expect(envIdx).toBeGreaterThanOrEqual(0)
    expect(envIdx).toBeLessThan(eduIdx)
  })

  it('topic card links to /learn/vocab/topic/:slug', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/topics') {
        return Promise.resolve({
          items: [
            { id: 'education', name: 'Education', word_count: 5, mastered_count: 1, subtopics: [] },
          ],
          total_words: 5,
        })
      }
      if (url === '/api/v1/me') return Promise.resolve({ topics: [] })
      if (url === '/api/v1/vocabulary?limit=100') return Promise.resolve({ items: [], next_cursor: null })
      throw new Error(`Unexpected API call: ${url}`)
    })
    render_()
    await userEvent.click(await screen.findByRole('button', { name: /byTopic\.tabs\.topics/ }))
    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: /topicNames\.education/ }),
      ).toBeInTheDocument()
    })
    const link = screen.getByRole('link', { name: /topicNames\.education/ })
    expect(link).toHaveAttribute('href', '/learn/vocab/topic/education')
  })

  it('shows empty state when user has no words', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/topics') {
        return Promise.resolve({
          items: [
            { id: 'education', name: 'Education', word_count: 0, mastered_count: 0, subtopics: [] },
          ],
          total_words: 0,
        })
      }
      if (url === '/api/v1/me') return Promise.resolve({ topics: [] })
      if (url === '/api/v1/vocabulary?limit=100') return Promise.resolve({ items: [], next_cursor: null })
      throw new Error(`Unexpected API call: ${url}`)
    })
    render_()
    await waitFor(() =>
      expect(screen.getByText(/empty\.myWords\.title/)).toBeInTheDocument(),
    )
  })

  // #242: Telegram-link prompt banner.
  it('shows the link banner when profile.id starts with web_ and hides when linked', async () => {
    apiFetchMock.mockResolvedValue({ items: [], total_words: 0 })

    useProfileMock.mockReturnValue({ id: 'web_abc', role: 'user', plan: 'free' })
    const { unmount } = render_()
    await waitFor(() => {
      const banner = screen.getByRole('region', { name: 'linkPrompt.title' })
      expect(banner).toBeInTheDocument()
    })
    expect(screen.getByText('linkPrompt.cta').closest('a'))
      .toHaveAttribute('href', '/settings/link-telegram')
    unmount()

    useProfileMock.mockReturnValue({ id: '4242', role: 'user', plan: 'free' })
    render_()
    await waitFor(() =>
      expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/topics'),
    )
    expect(
      screen.queryByRole('region', { name: 'linkPrompt.title' }),
    ).not.toBeInTheDocument()
  })

  it('loads favourite words with the favourite filter and tracks detail opens', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/topics') {
        return Promise.resolve({ items: [], total_words: 0 })
      }
      if (url === '/api/v1/me') {
        return Promise.resolve({ topics: [] })
      }
      if (url === '/api/v1/vocabulary?limit=100') {
        return Promise.resolve({ items: [], next_cursor: null })
      }
      if (url === '/api/v1/vocabulary?favourite=true&limit=100') {
        return Promise.resolve({
          items: [
            {
              id: 'w1',
              word: 'scalability',
              definition: 'ability to grow',
              definition_vi: 'kha nang mo rong',
              ipa: 'ska-luh-bi-li-tee',
              part_of_speech: 'noun',
            },
          ],
          next_cursor: null,
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    render_()

    await userEvent.click(
      await screen.findByRole('button', { name: /byTopic\.tabs\.favourites/ }),
    )

    const favouriteLink = await screen.findByRole('link', {
      name: /scalability/,
    })
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/vocabulary?favourite=true&limit=100')
    expect(trackMock).toHaveBeenCalledWith('vocab_favourites_tab_viewed')

    await userEvent.click(favouriteLink)
    expect(favouriteLink).toHaveAttribute('href', '/learn/vocab/scalability')
    expect(trackMock).toHaveBeenCalledWith('vocab_favourite_detail_opened', {
      word: 'scalability',
      word_id: 'w1',
    })
  })

  it('loads daily history and tracks history interactions', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/topics') {
        return Promise.resolve({ items: [], total_words: 0 })
      }
      if (url === '/api/v1/me') {
        return Promise.resolve({ topics: [] })
      }
      if (url === '/api/v1/vocabulary?limit=100') {
        return Promise.resolve({ items: [], next_cursor: null })
      }
      if (url === '/api/v1/vocabulary/daily/history?limit=30') {
        return Promise.resolve({
          timezone: 'Asia/Ho_Chi_Minh',
          items: [
            {
              date: '2026-05-27',
              topic: 'Technology',
              total_count: 2,
              reviewed_count: 1,
              favourite_count: 1,
              weak_count: 1,
              mastered_count: 0,
              words: [],
            },
          ],
        })
      }
      if (url === '/api/v1/vocabulary/daily/2026-05-27') {
        return Promise.resolve({
          date: '2026-05-27',
          topic: 'Technology',
          total_count: 2,
          reviewed_count: 1,
              words: [
                {
                  word: 'scalability',
                  word_id: 'w1',
                  reviewed: true,
                  is_favourite: true,
                  strength: 'Weak',
                  definition_en: 'ability to grow',
                  definition_vi: 'kha nang mo rong',
                  ipa: '',
                  part_of_speech: 'noun',
                },
              ],
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    render_()

    await userEvent.click(
      await screen.findByRole('button', { name: /byTopic\.tabs\.history/ }),
    )

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/vocabulary/daily/history?limit=30')
    })

    expect(screen.queryByRole('link', { name: /scalability/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /history\.showDetails/ }))

    const wordLink = await screen.findByRole('link', { name: /scalability/ })
    const reviewLink = screen.getByRole('link', { name: /history\.reviewCta/ })

    expect(trackMock).toHaveBeenCalledWith('vocab_history_tab_viewed')
    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/vocabulary/daily/2026-05-27')
    expect(screen.getByText('2026-05-27')).toBeInTheDocument()
    expect(screen.getByText('history.stats.favourites')).toBeInTheDocument()
    expect(wordLink).toHaveAttribute('href', '/learn/vocab/scalability')

    await userEvent.click(wordLink)
    expect(trackMock).toHaveBeenCalledWith('vocab_history_word_detail_opened', {
      date: '2026-05-27',
      word: 'scalability',
      word_id: 'w1',
    })

    await userEvent.click(reviewLink)
    expect(reviewLink).toHaveAttribute('href', '/learn/daily/quiz?date=2026-05-27')
    expect(trackMock).toHaveBeenCalledWith('vocab_history_review_started', {
      date: '2026-05-27',
      total: 2,
    })
  })
})
