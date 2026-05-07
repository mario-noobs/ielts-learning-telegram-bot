import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import AdminButton from './AdminButton'

describe('<AdminButton>', () => {
  it('renders children and fires onClick', async () => {
    const onClick = vi.fn()
    render(<AdminButton onClick={onClick}>Save</AdminButton>)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('renders the primary variant by default', () => {
    render(<AdminButton>Save</AdminButton>)
    const btn = screen.getByRole('button', { name: 'Save' })
    expect(btn.className).toMatch(/bg-primary/)
  })

  it('renders the danger variant when requested', () => {
    render(<AdminButton variant="danger">Delete</AdminButton>)
    const btn = screen.getByRole('button', { name: 'Delete' })
    expect(btn.className).toMatch(/text-danger/)
  })

  it('disables the button via the disabled prop', () => {
    render(<AdminButton disabled>Save</AdminButton>)
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
  })
})
