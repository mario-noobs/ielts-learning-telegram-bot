import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Tabs, TabsList, TabsTrigger, TabsContent } from './Tabs'

function Harness() {
  return (
    <Tabs defaultValue="a">
      <TabsList>
        <TabsTrigger value="a">A</TabsTrigger>
        <TabsTrigger value="b">B</TabsTrigger>
        <TabsTrigger value="c">C</TabsTrigger>
      </TabsList>
      <TabsContent value="a">Panel A</TabsContent>
      <TabsContent value="b">Panel B</TabsContent>
      <TabsContent value="c">Panel C</TabsContent>
    </Tabs>
  )
}

describe('<Tabs>', () => {
  it('shows the default tab content', () => {
    render(<Harness />)
    expect(screen.getByText('Panel A')).toBeInTheDocument()
  })

  it('activates another tab when clicked', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('tab', { name: 'B' }))
    expect(screen.getByText('Panel B')).toBeInTheDocument()
  })

  it('navigates triggers with Right/Home/End keys', async () => {
    render(<Harness />)
    const tabA = screen.getByRole('tab', { name: 'A' })
    tabA.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'B' })).toHaveFocus()
    await userEvent.keyboard('{End}')
    expect(screen.getByRole('tab', { name: 'C' })).toHaveFocus()
    await userEvent.keyboard('{Home}')
    expect(screen.getByRole('tab', { name: 'A' })).toHaveFocus()
  })
})
