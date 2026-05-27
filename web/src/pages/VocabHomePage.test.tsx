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
  it('renders topic cards sorted by least-mastered first', async () => {
    apiFetchMock.mockResolvedValueOnce({
      items: [
        { id: 'education', name: 'Education', word_count: 10, mastered_count: 8, subtopics: [] },
        { id: 'environment', name: 'Environment', word_count: 10, mastered_count: 2, subtopics: [] },
        { id: 'technology', name: 'Technology', word_count: 0, mastered_count: 0, subtopics: [] },
      ],
      total_words: 20,
    })

    render_()
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
    apiFetchMock.mockResolvedValueOnce({
      items: [
        { id: 'education', name: 'Education', word_count: 5, mastered_count: 1, subtopics: [] },
      ],
      total_words: 5,
    })
    render_()
    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: /topicNames\.education/ }),
      ).toBeInTheDocument()
    })
    const link = screen.getByRole('link', { name: /topicNames\.education/ })
    expect(link).toHaveAttribute('href', '/learn/vocab/topic/education')
  })

  it('shows empty state when user has no words', async () => {
    apiFetchMock.mockResolvedValueOnce({
      items: [
        { id: 'education', name: 'Education', word_count: 0, mastered_count: 0, subtopics: [] },
      ],
      total_words: 0,
    })
    render_()
    await waitFor(() =>
      expect(screen.getByText('empty.noWords.title')).toBeInTheDocument(),
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
})
