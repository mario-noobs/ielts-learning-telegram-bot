import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import PlanBadge from './PlanBadge'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'plan.badge.free': 'Free',
        'plan.badge.pro': 'Pro',
        'plan.badge.team': 'Team',
        'plan.badge.org': 'Org',
        'plan.badge.upgrade': 'Upgrade',
      }
      return map[key] ?? key
    },
  }),
}))

function renderBadge(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('<PlanBadge>', () => {
  it('renders Free pill + Upgrade CTA for plan=free', () => {
    renderBadge(<PlanBadge plan="free" />)
    expect(screen.getByText('Free')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Upgrade' })).toHaveAttribute(
      'href',
      '/pricing',
    )
  })

  it('renders Pro pill without Upgrade CTA for plan=personal_pro', () => {
    renderBadge(<PlanBadge plan="personal_pro" />)
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Upgrade' })).toBeNull()
  })

  it('hides Upgrade CTA when hideUpgrade prop is set, even on free', () => {
    renderBadge(<PlanBadge plan="free" hideUpgrade />)
    expect(screen.getByText('Free')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Upgrade' })).toBeNull()
  })

  it('renders only the letter chip in compact mode', () => {
    renderBadge(<PlanBadge plan="personal_pro" compact />)
    expect(screen.getByText('P')).toBeInTheDocument()
    expect(screen.queryByText('Pro')).toBeNull()
    // aria-label exposes the full tier name to screen readers
    expect(screen.getByLabelText('Pro')).toBeInTheDocument()
  })

  it('falls back to Free styling for unknown plan ids', () => {
    renderBadge(<PlanBadge plan="some_legacy_value" />)
    expect(screen.getByText('Free')).toBeInTheDocument()
  })
})
