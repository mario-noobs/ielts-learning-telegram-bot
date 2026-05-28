import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import WordDetailPage from './WordDetailPage'

const apiFetchMock = vi.fn()
vi.mock('../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('../lib/audio', () => ({
  playPronunciation: vi.fn(),
}))

const wordDetail = {
  word: 'scalability',
  ipa: 'skæləbɪlɪti',
  syllable_stress: 'scal · a · BIL · i · ty',
  part_of_speech: 'noun',
  definition_en: 'ability to grow',
  definition_vi: 'kha nang mo rong',
  word_family: ['scale', 'scalable', 'scalability'],
  collocations: [],
  examples_by_band: {
    7: {
      en: 'The platform needs scalability.',
      vi: 'Nen tang can kha nang mo rong.',
    },
  },
  ielts_tip: 'Use it for systems or products.',
  synonyms: ['expandability'],
  antonyms: ['rigidity'],
  image_url: null,
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/learn/vocab/scalability']}>
      <Routes>
        <Route path="/learn/vocab/:id" element={<WordDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  apiFetchMock.mockReset()
})

describe('<WordDetailPage>', () => {
  it('prefills ask-team context and cancels without creating a post', async () => {
    apiFetchMock.mockImplementation((url: string) => {
      if (url === '/api/v1/me') return Promise.resolve({ target_band: 7 })
      if (url === '/api/v1/teams/me') return Promise.resolve({ team: { id: 'team-1', name: 'Band 7 Crew' } })
      if (url === '/api/v1/words/scalability') return Promise.resolve(wordDetail)
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    await screen.findByRole('heading', { name: 'scalability' })
    await userEvent.click(screen.getByRole('button', { name: 'Hỏi team' }))

    expect(screen.getByDisplayValue('How can I use "scalability" naturally?')).toBeInTheDocument()
    expect(screen.getByDisplayValue(/Word detail: \/learn\/vocab\/scalability/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Hủy' }))

    expect(screen.queryByDisplayValue('How can I use "scalability" naturally?')).not.toBeInTheDocument()
    expect(apiFetchMock).not.toHaveBeenCalledWith(
      '/api/v1/teams/team-1/knowledge/posts',
      expect.anything(),
    )
  })

  it('creates a team question from word detail after confirmation', async () => {
    apiFetchMock.mockImplementation((url: string, options?: RequestInit) => {
      if (url === '/api/v1/me') return Promise.resolve({ target_band: 7 })
      if (url === '/api/v1/teams/me') return Promise.resolve({ team: { id: 'team-1', name: 'Band 7 Crew' } })
      if (url === '/api/v1/words/scalability') return Promise.resolve(wordDetail)
      if (url === '/api/v1/teams/team-1/knowledge/posts') {
        expect(options?.method).toBe('POST')
        expect(JSON.parse(String(options?.body))).toMatchObject({
          type: 'question',
          category: 'vocabulary',
          title: 'How can I use "scalability" naturally?',
          word_context: {
            word: 'scalability',
            definition_en: 'ability to grow',
          },
        })
        return Promise.resolve({ post: { id: 'post-1' } })
      }
      throw new Error(`Unexpected API call: ${url}`)
    })

    renderPage()

    await screen.findByRole('heading', { name: 'scalability' })
    await userEvent.click(screen.getByRole('button', { name: 'Hỏi team' }))
    await userEvent.click(screen.getByRole('button', { name: 'Đăng câu hỏi' }))

    await waitFor(() => {
      expect(screen.getByText('Đã đăng câu hỏi cho team. Post: post-1')).toBeInTheDocument()
    })
  })
})
