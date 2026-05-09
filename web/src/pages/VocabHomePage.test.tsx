import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

const TOPICS = {
  items: [
    { id: 'education', name: 'Education', word_count: 0, subtopics: [] },
    { id: 'environment', name: 'Environment', word_count: 0, subtopics: [] },
  ],
  total_words: 0,
}

function makeWord(over: Partial<{
  id: string; word: string; topic: string; strength: string;
  srs_next_review: string | null; ipa: string;
}> = {}): unknown {
  return {
    id: over.id ?? `w-${Math.random()}`,
    word: over.word ?? 'sample',
    definition: '',
    definition_vi: '',
    ipa: over.ipa ?? '',
    part_of_speech: '',
    topic: over.topic ?? 'education',
    strength: over.strength ?? 'Weak',
    srs_next_review: over.srs_next_review ?? null,
    added_at: null,
  }
}

beforeEach(() => {
  apiFetchMock.mockReset()
  localStorage.clear()
})

function render_() {
  return render(
    <MemoryRouter>
      <VocabHomePage />
    </MemoryRouter>,
  )
}

describe('<VocabHomePage>', () => {
  it('groups words by topic and sorts by strength within each topic', async () => {
    apiFetchMock
      .mockResolvedValueOnce({
        items: [
          makeWord({ id: 'a', word: 'mastered_word', topic: 'education', strength: 'Mastered' }),
          makeWord({ id: 'b', word: 'weak_word', topic: 'education', strength: 'Weak' }),
          makeWord({ id: 'c', word: 'env_word', topic: 'environment', strength: 'Learning' }),
        ],
        next_cursor: null,
      })
      .mockResolvedValueOnce(TOPICS)

    render_()
    await waitFor(() =>
      expect(screen.getByText('mastered_word')).toBeInTheDocument(),
    )

    // Within education section, weak_word should appear before mastered_word.
    const weakIdx = screen.getByText('weak_word').compareDocumentPosition(
      screen.getByText('mastered_word'),
    )
    // DOCUMENT_POSITION_FOLLOWING = 4
    expect(weakIdx & 4).toBe(4)
  })

  it('filters words by strength chip', async () => {
    apiFetchMock
      .mockResolvedValueOnce({
        items: [
          makeWord({ id: 'a', word: 'weak_word', strength: 'Weak' }),
          makeWord({ id: 'b', word: 'good_word', strength: 'Good' }),
        ],
        next_cursor: null,
      })
      .mockResolvedValueOnce(TOPICS)

    render_()
    await waitFor(() =>
      expect(screen.getByText('weak_word')).toBeInTheDocument(),
    )

    // Click "Good" filter chip — should hide the Weak word.
    const goodChips = screen.getAllByRole('button', { name: /strength\.Good/ })
    // First match is the filter chip (not the row chip).
    await userEvent.click(goodChips[0])
    expect(screen.queryByText('weak_word')).not.toBeInTheDocument()
    expect(screen.getByText('good_word')).toBeInTheDocument()
  })

  it('paginates topics with > 20 words via show-more button', async () => {
    const many = Array.from({ length: 25 }, (_, i) =>
      makeWord({ id: `w${i}`, word: `word_${i}`, strength: 'Weak' }),
    )
    apiFetchMock
      .mockResolvedValueOnce({ items: many, next_cursor: null })
      .mockResolvedValueOnce(TOPICS)

    render_()
    await waitFor(() => screen.getByText('word_0'))

    // Only first 20 should render initially.
    expect(screen.getByText('word_19')).toBeInTheDocument()
    expect(screen.queryByText('word_20')).not.toBeInTheDocument()

    // Click "Show more" — should reveal the rest.
    const showMore = screen.getByText(/byTopic\.topicSection\.showMore/)
    await userEvent.click(showMore)
    expect(screen.getByText('word_24')).toBeInTheDocument()
  })
})
