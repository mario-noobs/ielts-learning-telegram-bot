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
        <Route path="/learn/vocab/pools" element={<PublicVocabPoolsPage />} />
        <Route path="/learn/vocab/pools/:poolId" element={<PublicVocabPoolsPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('<PublicVocabPoolsPage>', () => {
  it('lists read-only public pools with provenance summary', async () => {
    apiFetchMock.mockResolvedValue({
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

    renderAt('/learn/vocab/pools')

    const card = await screen.findByRole('link', { name: /Cambridge IELTS 18/ })
    expect(card).toHaveAttribute('href', '/learn/vocab/pools/pool-1')
    expect(screen.getByText(/publicPools\.card\.source/)).toBeInTheDocument()
    expect(screen.getByText('CC BY 4.0')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument()
    expect(trackMock).toHaveBeenCalledWith('public_vocab_pools_opened')
  })

  it('opens pool detail and keeps words read-only', async () => {
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
          difficulty: 5,
          topic: 'technology',
          source_ref: 'unit-1',
        },
      ],
    })

    renderAt('/learn/vocab/pools/pool-1')

    expect(await screen.findByText('scalability')).toBeInTheDocument()
    expect(screen.getByText('ability to be enlarged or increased')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'publicPools.detail.sourceLink' }))
      .toHaveAttribute('href', 'https://example.test/source')
    expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument()
    expect(trackMock).toHaveBeenCalledWith('public_vocab_pool_detail_opened', { pool_id: 'pool-1' })
  })

  it('applies difficulty and topic filters through the query string', async () => {
    apiFetchMock.mockResolvedValue({
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

    renderAt('/learn/vocab/pools')
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
