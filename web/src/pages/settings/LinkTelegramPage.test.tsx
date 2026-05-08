import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import LinkTelegramPage from './LinkTelegramPage'

const useAuthMock = vi.fn()

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

const startLinkMock = vi.fn()
const unlinkMock = vi.fn()
vi.mock('../../lib/link', async () => {
  const actual = await vi.importActual<typeof import('../../lib/link')>(
    '../../lib/link',
  )
  return {
    ...actual,
    startLink: (...args: unknown[]) => startLinkMock(...args),
    unlinkTelegram: (...args: unknown[]) => unlinkMock(...args),
  }
})

beforeEach(() => {
  startLinkMock.mockReset()
  unlinkMock.mockReset()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <LinkTelegramPage />
    </MemoryRouter>,
  )
}

describe('<LinkTelegramPage>', () => {
  it('renders the not-linked state when profile.id starts with web_', () => {
    useAuthMock.mockReturnValue({
      profile: { id: 'web_abc', name: 'U', target_band: 7, topics: [], role: 'user', plan: 'free' },
      refreshProfile: vi.fn(),
    })
    renderPage()
    expect(screen.getByText('settings.notLinked.stepsTitle')).toBeInTheDocument()
    expect(screen.getByText('settings.notLinked.openBotCta')).toBeInTheDocument()
  })

  it('renders the linked state when profile.id is numeric', () => {
    useAuthMock.mockReturnValue({
      profile: { id: '4242', name: 'U', target_band: 7, topics: [], role: 'user', plan: 'free' },
      refreshProfile: vi.fn(),
    })
    renderPage()
    expect(screen.getByText('settings.linked.title')).toBeInTheDocument()
    expect(screen.getByText('settings.linked.unlinkCta')).toBeInTheDocument()
  })

  it('opens the unlink confirm modal and calls the API on confirm', async () => {
    const refresh = vi.fn().mockResolvedValue(undefined)
    useAuthMock.mockReturnValue({
      profile: { id: '4242', name: 'U', target_band: 7, topics: [], role: 'user', plan: 'free' },
      refreshProfile: refresh,
    })
    unlinkMock.mockResolvedValue(undefined)
    renderPage()

    await userEvent.click(screen.getByText('settings.linked.unlinkCta'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await userEvent.click(screen.getByText('settings.linked.unlinkConfirm'))

    await waitFor(() => {
      expect(unlinkMock).toHaveBeenCalled()
      expect(refresh).toHaveBeenCalled()
    })
  })

  it('calls startLink and redirects when the open-bot CTA is clicked', async () => {
    useAuthMock.mockReturnValue({
      profile: { id: 'web_abc', name: 'U', target_band: 7, topics: [], role: 'user', plan: 'free' },
      refreshProfile: vi.fn(),
    })
    startLinkMock.mockResolvedValue({
      token: 't',
      bot_deep_link: 'https://t.me/ielts_bot?start=link_t',
      expires_at: '2026-05-08T12:00:00Z',
    })

    // jsdom doesn't allow location reassignment by default; stub it.
    const original = window.location
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
    })
    try {
      renderPage()
      await userEvent.click(screen.getByText('settings.notLinked.openBotCta'))
      await waitFor(() => {
        expect(startLinkMock).toHaveBeenCalled()
      })
      expect(window.location.href).toBe('https://t.me/ielts_bot?start=link_t')
    } finally {
      Object.defineProperty(window, 'location', { value: original })
    }
  })
})
