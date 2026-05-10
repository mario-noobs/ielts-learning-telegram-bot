import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ReadinessTrack from './ReadinessTrack'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (k: string, vars?: Record<string, unknown>) =>
      vars ? `${k}|${JSON.stringify(vars)}` : k,
  }),
}))

vi.mock('../../lib/analytics', () => ({ track: vi.fn() }))

function render_() {
  return render(
    <MemoryRouter>
      <ReadinessTrack progress={null} />
    </MemoryRouter>,
  )
}

describe('<ReadinessTrack>', () => {
  it('renders the full 4-step track even before an exam date is set', async () => {
    // No-date users used to see a duplicate empty-state CTA here that
    // shadowed PersonalizationCTA above the widget. Track should
    // always render — Step 1 active prompts the user to fill the goal,
    // Step 4 locked because there's no date yet (#dashboard-polish).
    apiFetchMock.mockResolvedValueOnce({
      pct_complete: 0,
      days_until_exam: null,
      urgent: false,
      target_band: 7,
      steps: [
        {
          id: 'goal',
          status: 'active',
          title_key: 'readinessTrack.steps.goal.title',
          rationale_key: 'readinessTrack.steps.goal.rationale',
          rationale_params: {},
          sub_tasks: [],
        },
        {
          id: 'daily_plan',
          status: 'upcoming',
          title_key: 'readinessTrack.steps.daily_plan.title',
          rationale_key: 'readinessTrack.steps.daily_plan.rationale',
          rationale_params: { min: 20 },
          sub_tasks: [],
        },
        {
          id: 'skills',
          status: 'upcoming',
          title_key: 'readinessTrack.steps.skills.title',
          rationale_key: 'readinessTrack.steps.skills.rationale',
          rationale_params: { done: 0, total: 4, target: 7 },
          sub_tasks: [],
        },
        {
          id: 'mock_test',
          status: 'locked',
          title_key: 'readinessTrack.steps.mock_test.title',
          rationale_key: 'readinessTrack.steps.mock_test.locked_no_date',
          rationale_params: {},
          sub_tasks: [],
        },
      ],
    })
    render_()
    await waitFor(() =>
      expect(
        screen.getByText('readinessTrack.steps.goal.title'),
      ).toBeInTheDocument(),
    )
    const rows = screen.getAllByRole('button', { name: /stepAria/ })
    expect(rows).toHaveLength(4)
    // Empty-state CTA must NOT render — duplicate of <PersonalizationCTA>.
    expect(screen.queryByText('readinessTrack.empty.heading'))
      .not.toBeInTheDocument()
  })

  it('renders 4 step rows + auto-expands the active step', async () => {
    apiFetchMock.mockResolvedValueOnce({
      pct_complete: 50,
      days_until_exam: 90,
      urgent: false,
      target_band: 7,
      steps: [
        {
          id: 'goal',
          status: 'done',
          title_key: 'readinessTrack.steps.goal.title',
          rationale_key: 'readinessTrack.steps.goal.rationale',
          rationale_params: {},
          sub_tasks: [],
        },
        {
          id: 'daily_plan',
          status: 'active',
          title_key: 'readinessTrack.steps.daily_plan.title',
          rationale_key: 'readinessTrack.steps.daily_plan.rationale',
          rationale_params: { min: 20 },
          sub_tasks: [
            {
              id: 'weekly_goal',
              label_key: 'readinessTrack.subTasks.weekly_goal',
              href: '/settings#weekly-goal',
              done: false,
            },
          ],
        },
        {
          id: 'skills',
          status: 'upcoming',
          title_key: 'readinessTrack.steps.skills.title',
          rationale_key: 'readinessTrack.steps.skills.rationale',
          rationale_params: { done: 0, total: 4, target: 7 },
          sub_tasks: [],
        },
        {
          id: 'mock_test',
          status: 'locked',
          title_key: 'readinessTrack.steps.mock_test.title',
          rationale_key: 'readinessTrack.steps.mock_test.locked',
          rationale_params: { days: 14 },
          sub_tasks: [],
        },
      ],
    })
    render_()
    // Wait for fetch to land.
    await waitFor(() =>
      expect(
        screen.getAllByText('readinessTrack.steps.daily_plan.title').length,
      ).toBeGreaterThan(0),
    )
    const rows = screen.getAllByRole('button', { name: /stepAria/ })
    expect(rows).toHaveLength(4)
    // Active step (daily_plan) is expanded by default → its sub-task link
    // is rendered.
    expect(
      screen.getByRole('link', { name: /readinessTrack\.subTasks\.weekly_goal/ }),
    ).toHaveAttribute('href', '/settings#weekly-goal')
    // Locked row has aria-disabled.
    const lockedRow = rows[3]
    expect(lockedRow).toHaveAttribute('aria-disabled', 'true')
  })
})
