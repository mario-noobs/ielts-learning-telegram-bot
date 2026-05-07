import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import AdminCard, { AdminPageHeader } from './AdminCard'

describe('<AdminCard>', () => {
  it('renders children unchanged when no title is given', () => {
    render(
      <AdminCard>
        <p>Body</p>
      </AdminCard>,
    )
    expect(screen.getByText('Body')).toBeInTheDocument()
  })

  it('renders a title and right-aligned actions', () => {
    render(
      <AdminCard title="Section" actions={<button>Action</button>}>
        <p>Body</p>
      </AdminCard>,
    )
    expect(screen.getByText('Section')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument()
  })
})

describe('<AdminPageHeader>', () => {
  it('renders title + subtitle when provided', () => {
    render(<AdminPageHeader title="Users" subtitle="All users" />)
    expect(screen.getByRole('heading', { name: 'Users' })).toBeInTheDocument()
    expect(screen.getByText('All users')).toBeInTheDocument()
  })

  it('renders header actions when provided', () => {
    render(<AdminPageHeader title="Plans" actions={<button>Create</button>} />)
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument()
  })
})
