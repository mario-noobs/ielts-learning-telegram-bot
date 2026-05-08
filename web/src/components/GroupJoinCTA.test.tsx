import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import GroupJoinCTA from './GroupJoinCTA'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}))

const ORIGINAL_ENV = { ...import.meta.env }

afterEach(() => {
  Object.assign(import.meta.env, ORIGINAL_ENV)
})

describe('<GroupJoinCTA>', () => {
  it('renders nothing when VITE_TELEGRAM_GROUP_INVITE_URL is unset', () => {
    Object.assign(import.meta.env, { VITE_TELEGRAM_GROUP_INVITE_URL: '' })
    const { container } = render(<GroupJoinCTA />)
    expect(container).toBeEmptyDOMElement()
  })

  describe('with VITE_TELEGRAM_GROUP_INVITE_URL set', () => {
    beforeEach(() => {
      Object.assign(import.meta.env, {
        VITE_TELEGRAM_GROUP_INVITE_URL: 'https://t.me/+abc123',
      })
    })

    it('renders the CTA pointing at the configured URL', () => {
      render(<GroupJoinCTA />)
      const link = screen.getByRole('link', { name: 'group.cta' })
      expect(link.getAttribute('href')).toBe('https://t.me/+abc123')
      expect(link.getAttribute('target')).toBe('_blank')
      expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    })
  })
})
