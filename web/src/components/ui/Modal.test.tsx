import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  Modal,
  ModalTrigger,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalClose,
} from './Modal'

function openModal() {
  render(
    <Modal>
      <ModalTrigger>Mở</ModalTrigger>
      <ModalContent>
        <ModalHeader>
          <ModalTitle>Tiêu đề</ModalTitle>
        </ModalHeader>
        <p>Nội dung</p>
        <ModalClose>Đóng</ModalClose>
      </ModalContent>
    </Modal>,
  )
}

describe('<Modal>', () => {
  it('opens when trigger is clicked', async () => {
    openModal()
    expect(screen.queryByText('Nội dung')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Mở' }))
    expect(await screen.findByText('Nội dung')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Tiêu đề')
  })

  it('closes on Escape', async () => {
    openModal()
    await userEvent.click(screen.getByRole('button', { name: 'Mở' }))
    await screen.findByText('Nội dung')
    await userEvent.keyboard('{Escape}')
    // Radix unmounts content on close
    expect(screen.queryByText('Nội dung')).not.toBeInTheDocument()
  })

  it('closes when explicit Close is clicked', async () => {
    openModal()
    await userEvent.click(screen.getByRole('button', { name: 'Mở' }))
    await screen.findByText('Nội dung')
    await userEvent.click(screen.getByRole('button', { name: 'Đóng' }))
    expect(screen.queryByText('Nội dung')).not.toBeInTheDocument()
  })
})
