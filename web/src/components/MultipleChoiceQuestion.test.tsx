import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MultipleChoiceQuestion from './MultipleChoiceQuestion'

const options = ['alpha', 'bravo', 'charlie', 'delta']

describe('<MultipleChoiceQuestion>', () => {
  it('renders one button per option with letter prefix', () => {
    render(
      <MultipleChoiceQuestion
        options={options}
        onSubmit={() => {}}
        mcqOptionAria={({ letter, text }) => `Option ${letter}: ${text}`}
        keyboardHint={(k) => `Tip ${k}`}
      />,
    )
    expect(screen.getByRole('button', { name: 'Option A: alpha' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Option B: bravo' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Option C: charlie' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Option D: delta' })).toBeInTheDocument()
  })

  it('calls onSubmit with the clicked letter', async () => {
    const onSubmit = vi.fn()
    render(
      <MultipleChoiceQuestion
        options={options}
        onSubmit={onSubmit}
        mcqOptionAria={({ letter, text }) => `Option ${letter}: ${text}`}
        keyboardHint={(k) => `Tip ${k}`}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Option B: bravo' }))
    expect(onSubmit).toHaveBeenCalledWith('B')
  })

  it('maps number keys 1–4 to letters A–D', () => {
    const onSubmit = vi.fn()
    render(
      <MultipleChoiceQuestion
        options={options}
        onSubmit={onSubmit}
        mcqOptionAria={({ letter, text }) => `Option ${letter}: ${text}`}
        keyboardHint={(k) => `Tip ${k}`}
      />,
    )
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: '2' }))
    })
    expect(onSubmit).toHaveBeenCalledWith('B')
  })

  it('disabled state blocks both click and keyboard', async () => {
    const onSubmit = vi.fn()
    render(
      <MultipleChoiceQuestion
        options={options}
        onSubmit={onSubmit}
        disabled
        mcqOptionAria={({ letter, text }) => `Option ${letter}: ${text}`}
        keyboardHint={(k) => `Tip ${k}`}
      />,
    )
    const btn = screen.getByRole('button', { name: 'Option A: alpha' })
    expect(btn).toBeDisabled()
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: '1' }))
    })
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
