import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Button } from './Button'

describe('<Button>', () => {
  it('fires onClick when clicked', async () => {
    const handleClick = vi.fn()
    render(<Button onClick={handleClick}>Click</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Click' }))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled and aria-busy when loading', async () => {
    const handleClick = vi.fn()
    render(
      <Button loading onClick={handleClick}>
        Đang xử lý
      </Button>,
    )
    const btn = screen.getByRole('button')
    expect(btn).toBeDisabled()
    expect(btn).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(btn)
    expect(handleClick).not.toHaveBeenCalled()
  })

  it('renders children during loading (no layout shift)', () => {
    render(<Button loading>Đang xử lý</Button>)
    expect(screen.getByText('Đang xử lý')).toBeInTheDocument()
  })

  it('renders as child element with button classes when asChild=true', () => {
    render(
      <Button asChild>
        <a href="/go">Đi tới</a>
      </Button>,
    )
    const link = screen.getByRole('link', { name: 'Đi tới' })
    expect(link).toHaveAttribute('href', '/go')
    // buttonVariants applies rounded-xl as part of its base classes
    expect(link.className).toMatch(/rounded-xl/)
  })
})
