import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import AdminInput, { AdminField, AdminSelect } from './AdminInput'

describe('<AdminInput>', () => {
  it('forwards typing to the underlying input', async () => {
    render(<AdminInput aria-label="email" placeholder="email" defaultValue="" />)
    const input = screen.getByPlaceholderText('email') as HTMLInputElement
    await userEvent.type(input, 'a@b.test')
    expect(input.value).toBe('a@b.test')
  })

  it('AdminField renders the label and the wrapped control', () => {
    render(
      <AdminField label="Display name">
        <AdminInput defaultValue="" placeholder="name" />
      </AdminField>,
    )
    expect(screen.getByText('Display name')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('name')).toBeInTheDocument()
  })

  it('AdminField surfaces the hint text', () => {
    render(
      <AdminField label="Field" hint="This is a hint">
        <AdminInput defaultValue="" />
      </AdminField>,
    )
    expect(screen.getByText('This is a hint')).toBeInTheDocument()
  })

  it('AdminSelect renders <option> children and reflects value changes', async () => {
    render(
      <AdminSelect aria-label="role" defaultValue="member">
        <option value="member">Member</option>
        <option value="admin">Admin</option>
      </AdminSelect>,
    )
    const select = screen.getByLabelText('role') as HTMLSelectElement
    await userEvent.selectOptions(select, 'admin')
    expect(select.value).toBe('admin')
  })
})
