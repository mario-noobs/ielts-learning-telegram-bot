import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import FlagsPage from './FlagsPage'

const apiFetchMock = vi.fn()
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}))

describe('<FlagsPage>', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('lists flag rows', async () => {
    apiFetchMock.mockResolvedValue([
      {
        name: 'design_system_v2', enabled: true, rollout_pct: 50,
        uid_allowlist: ['u1'], description: 'New DS', updated_at: null,
      },
    ])
    render(<FlagsPage />)
    await waitFor(() =>
      expect(screen.getByText('design_system_v2')).toBeInTheDocument(),
    )
    expect(screen.getByText('50%')).toBeInTheDocument()
  })

  it('PUTs the edited flag and refreshes', async () => {
    apiFetchMock
      .mockResolvedValueOnce([
        {
          name: 'reading_lab', enabled: false, rollout_pct: 0,
          uid_allowlist: [], description: '', updated_at: null,
        },
      ])
      .mockResolvedValueOnce({ ok: true, audit_log_id: 1 })  // PUT
      .mockResolvedValueOnce([                                // refresh
        {
          name: 'reading_lab', enabled: true, rollout_pct: 0,
          uid_allowlist: [], description: '', updated_at: null,
        },
      ])

    render(<FlagsPage />)
    await waitFor(() => screen.getByText('reading_lab'))

    await userEvent.click(screen.getByRole('button', { name: 'actions.edit' }))
    // Toggle the enabled checkbox.
    await userEvent.click(screen.getByRole('checkbox'))
    // The "Save" button inside the form (not the create CTA at top) —
    // by the time the form is open both have the same name; pick the
    // last one (form button).
    const saveButtons = screen.getAllByRole('button', { name: 'flags.form.save' })
    await userEvent.click(saveButtons[saveButtons.length - 1])

    await waitFor(() => {
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/flags/reading_lab',
        expect.objectContaining({ method: 'PUT' }),
      )
    })
  })
})
