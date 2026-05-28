import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import PublicVocabPoolsPage from './PublicVocabPoolsPage'

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

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/learn/pools" element={<PublicVocabPoolsPage />} />
        <Route path="/learn/pools/:poolId" element={<PublicVocabPoolsPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('<PublicVocabPoolsPage>', () => {
  it('lists read-only public pools with provenance summary', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/vocabulary/public-pools/recommendations') {
        return Promise.resolve({ enabled: true, target_difficulty: 4, items: [] })
      }
      if (url === '/api/v1/vocabulary/public-pools') {
        return Promise.resolve({
          enabled: true,
          items: [
            {
              id: 'pool-1',
              title: 'Cambridge IELTS 18',
              source: 'cambridge',
              source_theme: 'ielts_18',
              word_count: 30,
              difficulty: 4,
              difficulty_min: 3,
              difficulty_max: 5,
              topics: ['education'],
              source_url: 'https://example.test/source',
              license: 'CC BY 4.0',
              provenance: 'Cambridge import',
            },
          ],
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderAt('/learn/pools')

    const card = await screen.findByRole('link', { name: /Cambridge IELTS 18/ })
    expect(card).toHaveAttribute('href', '/learn/pools/pool-1')
    expect(screen.getByText(/publicPools\.card\.source/)).toBeInTheDocument()
    expect(screen.getByText('CC BY 4.0')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument()
    expect(trackMock).toHaveBeenCalledWith('public_vocab_pools_opened')
  })

  it('shows recommended roadmap pools with visible reasons', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/vocabulary/public-pools/recommendations') {
        return Promise.resolve({
          enabled: true,
          target_difficulty: 3,
          items: [
            {
              id: 'rec-1',
              title: 'Upper Intermediate',
              source: 'cambridge',
              source_theme: 'upper_intermediate',
              word_count: 101,
              difficulty: 3,
              difficulty_min: 3,
              difficulty_max: 3,
              topics: ['environment'],
              source_url: '',
              license: 'CC BY 4.0',
              provenance: 'Seed import',
              reasons: [
                { code: 'target_band_match' },
                { code: 'weak_topic', topic: 'environment' },
              ],
            },
          ],
        })
      }
      if (url === '/api/v1/vocabulary/public-pools') {
        return Promise.resolve({ enabled: true, items: [] })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderAt('/learn/pools')

    expect(await screen.findByText('publicPools.recommendations.heading')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Upper Intermediate/ }))
      .toHaveAttribute('href', '/learn/pools/rec-1')
    expect(screen.getByText(/publicPools\.recommendations\.reasons\.weak_topic/))
      .toBeInTheDocument()
    expect(trackMock).toHaveBeenCalledWith('public_vocab_roadmap_recommendations_viewed', {
      count: 1,
      pool_ids: ['rec-1'],
    })
  })

  it('requests an AI roadmap consult only when the user asks', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/vocabulary/public-pools/recommendations') {
        return Promise.resolve({ enabled: true, target_difficulty: 3, items: [] })
      }
      if (url === '/api/v1/vocabulary/public-pools') {
        return Promise.resolve({ enabled: true, items: [] })
      }
      if (url === '/api/v1/vocabulary/roadmap/consult') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({
          status: 'ready',
          disclaimer: 'Not official.',
          confidence: 'medium',
          readiness_range: '6.0-6.5',
          summary: 'Review consistency is the next gap.',
          data_used: [{ label: 'My Words', value: '40 saved, 12 reviewed' }],
          missing_requirements: [],
          strengths: [{ title: 'Coverage', detail: 'Education is covered.', evidence: '12 words' }],
          gaps: [{ title: 'Reviews', detail: 'Weak words remain.', evidence: '4 due' }],
          next_actions: [
            {
              title: 'Review due words',
              detail: "Clear today's due cards.",
              route: '/learn/review',
              priority: 'high',
            },
          ],
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderAt('/learn/pools')

    await screen.findByText('publicPools.empty.title')
    expect(apiFetchMock).not.toHaveBeenCalledWith('/api/v1/vocabulary/roadmap/consult', expect.anything())

    await userEvent.click(screen.getByRole('button', { name: 'publicPools.consult.cta' }))

    expect(await screen.findByText('Review consistency is the next gap.')).toBeInTheDocument()
    expect(screen.getByText('Not official.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Review due words/ })).toHaveAttribute('href', '/learn/review')
    expect(trackMock).toHaveBeenCalledWith('vocab_roadmap_consult_requested')
    expect(trackMock).toHaveBeenCalledWith('vocab_roadmap_consult_completed', {
      status: 'ready',
      confidence: 'medium',
      action_count: 1,
    })
  })

  it('opens pool detail with save state', async () => {
    apiFetchMock.mockResolvedValue({
      enabled: true,
      pool: {
        id: 'pool-1',
        title: 'Vocabulary In Use Advanced',
        source: 'cambridge',
        source_theme: 'advanced',
        word_count: 1,
        difficulty: 5,
        difficulty_min: 5,
        difficulty_max: 5,
        topics: ['technology'],
        source_url: 'https://example.test/source',
        license: 'CC BY 4.0',
        provenance: 'Seed import',
      },
      words: [
        {
          id: 'w1',
          word: 'scalability',
          definition_en: 'ability to be enlarged or increased',
          definition_vi: 'kha nang mo rong',
          ipa: 'skaelability',
          part_of_speech: 'noun',
          example_en: 'Scalability matters.',
          example_vi: 'Kha nang mo rong rat quan trong.',
          difficulty: 5,
          topic: 'technology',
          source_ref: 'unit-1',
          already_saved: false,
          existing_word_id: null,
        },
      ],
    })

    renderAt('/learn/pools/pool-1')

    expect(await screen.findByText('scalability')).toBeInTheDocument()
    expect(screen.getByText('ability to be enlarged or increased')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'publicPools.detail.sourceLink' }))
      .toHaveAttribute('href', 'https://example.test/source')
    expect(screen.getByRole('button', { name: 'publicPools.word.save' })).toBeEnabled()
    expect(trackMock).toHaveBeenCalledWith('public_vocab_pool_detail_opened', { pool_id: 'pool-1' })
  })

  it('saves a pool word into My Words and disables duplicate saves', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/vocabulary/public-pools/pool-1' && !options) {
        return Promise.resolve({
          enabled: true,
          pool: {
            id: 'pool-1',
            title: 'Vocabulary In Use Advanced',
            source: 'cambridge',
            source_theme: 'advanced',
            word_count: 1,
            difficulty: 5,
            difficulty_min: 5,
            difficulty_max: 5,
            topics: ['technology'],
            source_url: '',
            license: 'CC BY 4.0',
            provenance: 'Seed import',
          },
          words: [
            {
              id: 'w1',
              word: 'scalability',
              definition_en: 'ability to be enlarged or increased',
              definition_vi: '',
              ipa: '',
              part_of_speech: 'noun',
              example_en: '',
              example_vi: '',
              difficulty: 5,
              topic: 'technology',
              source_ref: 'unit-1',
              already_saved: false,
              existing_word_id: null,
            },
          ],
        })
      }
      if (url === '/api/v1/vocabulary/public-pools/pool-1/words/w1/save') {
        expect(options?.method).toBe('POST')
        return Promise.resolve({
          created: true,
          already_saved: false,
          word: { id: 'user-word-1', word: 'scalability' },
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderAt('/learn/pools/pool-1')

    await userEvent.click(await screen.findByRole('button', { name: 'publicPools.word.save' }))

    expect(await screen.findByRole('button', { name: 'publicPools.word.alreadySaved' }))
      .toBeDisabled()
    expect(trackMock).toHaveBeenCalledWith('public_vocab_pool_word_saved', {
      pool_id: 'pool-1',
      word_id: 'w1',
      created: true,
      already_saved: false,
    })
  })

  it('applies difficulty and topic filters through the query string', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/vocabulary/public-pools/recommendations') {
        return Promise.resolve({ enabled: true, target_difficulty: 3, items: [] })
      }
      if (url.startsWith('/api/v1/vocabulary/public-pools')) {
        return Promise.resolve({
          enabled: true,
          items: [
            {
              id: 'pool-1',
              title: 'Education Pool',
              source: 'seed',
              source_theme: 'education',
              word_count: 4,
              difficulty: 3,
              difficulty_min: 3,
              difficulty_max: 3,
              topics: ['education'],
              source_url: '',
              license: '',
              provenance: 'Seed',
            },
          ],
        })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderAt('/learn/pools')
    await screen.findByText('Education Pool')

    await userEvent.selectOptions(
      screen.getByLabelText('publicPools.filters.difficulty'),
      '3',
    )
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenLastCalledWith('/api/v1/vocabulary/public-pools?difficulty=3')
    })

    await userEvent.selectOptions(
      screen.getByLabelText('publicPools.filters.topic'),
      'education',
    )
    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenLastCalledWith(
        '/api/v1/vocabulary/public-pools?difficulty=3&topic=education',
      )
    })
  })
})
