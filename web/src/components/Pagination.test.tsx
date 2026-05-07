import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Pagination from './Pagination'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) => {
      if (key === 'pagination.nav') return 'Pagination'
      if (key === 'pagination.prev') return 'Prev'
      if (key === 'pagination.next') return 'Next'
      if (key === 'pagination.pageOf') {
        return `${opts?.current} / ${opts?.total}`
      }
      return key
    },
  }),
}))

describe('<Pagination>', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders current/total label', () => {
    render(
      <Pagination page={2} totalPages={5} onPrev={() => {}} onNext={() => {}} />,
    )
    expect(screen.getByText('2 / 5')).toBeInTheDocument()
  })

  it('disables Prev on first page', () => {
    render(
      <Pagination page={1} totalPages={3} onPrev={() => {}} onNext={() => {}} />,
    )
    expect(screen.getByRole('button', { name: 'Prev' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).not.toBeDisabled()
  })

  it('disables Next on last page', () => {
    render(
      <Pagination page={3} totalPages={3} onPrev={() => {}} onNext={() => {}} />,
    )
    expect(screen.getByRole('button', { name: 'Prev' })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('fires onPrev / onNext callbacks on click', async () => {
    const onPrev = vi.fn()
    const onNext = vi.fn()
    render(
      <Pagination page={2} totalPages={5} onPrev={onPrev} onNext={onNext} />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Prev' }))
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(onPrev).toHaveBeenCalledTimes(1)
    expect(onNext).toHaveBeenCalledTimes(1)
  })
})
