import type { Meta, StoryObj } from '@storybook/react'
import { Badge } from './Badge'

/**
 * Badge stories — caption pill used for status and category chips.
 */
const meta = {
  title: 'UI/Badge',
  component: Badge,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  argTypes: {
    variant: {
      control: 'inline-radio',
      options: ['neutral', 'primary', 'success', 'warning', 'danger', 'info'],
    },
  },
} satisfies Meta<typeof Badge>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { children: 'Neutral', variant: 'neutral' },
}

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant="neutral">Neutral</Badge>
      <Badge variant="primary">Primary</Badge>
      <Badge variant="success">Thạo</Badge>
      <Badge variant="warning">Đang học</Badge>
      <Badge variant="danger">Yếu</Badge>
      <Badge variant="info">Info</Badge>
    </div>
  ),
}

export const WithIconAndText: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant="success">
        <span aria-hidden>✓</span> Đạt
      </Badge>
      <Badge variant="warning">
        <span aria-hidden>!</span> Gần hạn
      </Badge>
      <Badge variant="danger">
        <span aria-hidden>×</span> Chưa đạt
      </Badge>
    </div>
  ),
}
