import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router-dom'
import EmptyState from './EmptyState'

/**
 * EmptyState shows the four variants we integrate in M1-M5. Toggle the theme
 * switcher in the Storybook toolbar to verify light + dark rendering.
 *
 * Stories use `MemoryRouter` because EmptyState's primary/secondary actions
 * may render `<Link>` when a `to` is provided.
 */
const meta = {
  title: 'Components/EmptyState',
  component: EmptyState,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story) => (
      <MemoryRouter>
        <div className="bg-bg p-6 min-h-[360px] w-full flex items-center justify-center">
          <Story />
        </div>
      </MemoryRouter>
    ),
  ],
} satisfies Meta<typeof EmptyState>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    illustration: 'empty-vocab',
    title: 'Chưa có từ vựng nào',
    description: 'Bắt đầu học từ đầu tiên để theo dõi tiến độ IELTS của bạn.',
    primaryAction: { label: 'Thêm từ', to: '/vocab/add' },
  },
}

export const Celebration: Story = {
  args: {
    illustration: 'plan-complete',
    title: 'Hoàn thành kế hoạch hôm nay!',
    description: 'Mai quay lại để tiếp tục streak nhé.',
    variant: 'celebration',
    primaryAction: { label: 'Xem tiến độ', to: '/progress' },
  },
}

export const WithBothActions: Story = {
  args: {
    illustration: 'empty-writing',
    title: 'Chưa có bài viết nào',
    description: 'Viết thử một đoạn Task 2 để nhận chấm band chi tiết.',
    primaryAction: { label: 'Viết bài mới', to: '/write' },
    secondaryAction: { label: 'Xem mẫu', onClick: () => alert('Samples') },
  },
}

export const ErrorVariant: Story = {
  args: {
    illustration: 'error-network',
    title: 'Không kết nối được',
    description: 'Kiểm tra kết nối mạng rồi thử lại.',
    variant: 'error',
    primaryAction: { label: 'Thử lại', onClick: () => alert('Retry') },
  },
}
