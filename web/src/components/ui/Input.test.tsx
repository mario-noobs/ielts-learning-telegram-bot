import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Input } from './Input'

describe('<Input>', () => {
  it('associates label with input via htmlFor/id', () => {
    render(<Input label="Email" />)
    const input = screen.getByLabelText('Email')
    expect(input).toBeInTheDocument()
    expect(input.tagName).toBe('INPUT')
  })

  it('applies aria-invalid when errorText is set', () => {
    render(<Input label="Email" errorText="Sai rồi" />)
    expect(screen.getByLabelText('Email')).toHaveAttribute(
      'aria-invalid',
      'true',
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Sai rồi')
  })

  it('wires helper text via aria-describedby', () => {
    render(<Input label="Tên" helperText="Tối đa 40 ký tự" />)
    const input = screen.getByLabelText('Tên')
    const describedBy = input.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    const helper = document.getElementById(describedBy!)
    expect(helper).toHaveTextContent('Tối đa 40 ký tự')
  })
})
