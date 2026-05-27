import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import FlashcardReviewPage from './FlashcardReviewPage'

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
      <FlashcardReviewPage />
    </MemoryRouter>,
  )
}

describe('<FlashcardReviewPage>', () => {
  it('starts flip review with My Words filters', async () => {
    apiFetchMock.mockResolvedValue({
      items: [
        {
          word_id: 'w1',
          word: 'resilience',
          ipa: '',
          part_of_speech: 'noun',
          definition_en: 'ability to recover',
          definition_vi: '',
          example_en: '',
          example_vi: '',
          source: 'manual',
          topic: 'society',
          strength: 'New',
        },
      ],
    })

    render_()

    await userEvent.selectOptions(screen.getByLabelText(/review\.filters\.source/), 'manual')
    await userEvent.selectOptions(screen.getByLabelText(/review\.filters\.status/), 'New')
    await userEvent.type(screen.getByLabelText(/review\.filters\.topic/), 'society')
    await userEvent.click(screen.getByRole('button', { name: /review\.modePicker\.flip/ }))

    expect(apiFetchMock).toHaveBeenCalledWith('/api/v1/review/due', {
      method: 'POST',
      body: JSON.stringify({
        limit: 10,
        source: 'manual',
        status: 'New',
        topic: 'society',
      }),
    })
  })
})
