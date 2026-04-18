import type { Meta, StoryObj } from '@storybook/react'
import {
  Modal,
  ModalTrigger,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalFooter,
  ModalClose,
} from './Modal'
import { Button } from './Button'

/**
 * Modal stories — Radix Dialog wrapped with token styling.
 *
 * Focus trap, Escape-to-close, click-outside-to-close, and initial focus
 * behavior come from Radix. Animations tween at --dur-base and clamp to 0ms
 * under prefers-reduced-motion via tokens.css.
 */
const meta = {
  title: 'UI/Modal',
  component: Modal,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
} satisfies Meta<typeof Modal>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Modal>
      <ModalTrigger asChild>
        <Button>Mở modal</Button>
      </ModalTrigger>
      <ModalContent>
        <ModalHeader>
          <ModalTitle>Xác nhận xóa bài viết</ModalTitle>
          <ModalDescription>
            Hành động này không thể hoàn tác. Bài viết sẽ bị xóa vĩnh viễn.
          </ModalDescription>
        </ModalHeader>
        <ModalFooter>
          <ModalClose asChild>
            <Button variant="ghost">Hủy</Button>
          </ModalClose>
          <ModalClose asChild>
            <Button variant="destructive">Xóa bài viết</Button>
          </ModalClose>
        </ModalFooter>
      </ModalContent>
    </Modal>
  ),
}

export const WithBodyContent: Story = {
  render: () => (
    <Modal>
      <ModalTrigger asChild>
        <Button>Chi tiết</Button>
      </ModalTrigger>
      <ModalContent>
        <ModalHeader>
          <ModalTitle>Chi tiết bài nộp</ModalTitle>
          <ModalDescription>
            Tóm tắt ngắn của bài viết gần nhất.
          </ModalDescription>
        </ModalHeader>
        <div className="text-sm text-fg flex flex-col gap-2">
          <p>
            Bạn đã viết 248 từ về chủ đề giáo dục. AI nhận xét đoạn mở bài
            rõ ràng, đoạn kết luận chưa đủ sức thuyết phục.
          </p>
          <p>Band: 6.5 · Task 2 · 18 phút</p>
        </div>
        <ModalFooter>
          <ModalClose asChild>
            <Button variant="ghost">Đóng</Button>
          </ModalClose>
          <Button>Xem đầy đủ</Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  ),
}
