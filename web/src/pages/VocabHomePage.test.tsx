import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import VocabHomePage from './VocabHomePage'

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

beforeEach(() => {
  apiFetchMock.mockReset()
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
})
