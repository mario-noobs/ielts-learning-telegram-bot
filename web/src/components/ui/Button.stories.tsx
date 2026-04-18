import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './Button'

/**
 * Button primitive stories — #121 US-M6.2.
 *
 * Covers:
 *   - Default (primary/md)
 *   - All variants  (primary / secondary / ghost / destructive)
 *   - All sizes     (sm 36 / md 44 / lg 56)
 *   - Loading       (spinner + aria-busy + disabled)
 *   - With icons    (leftIcon / rightIcon slots)
 *   - asChild       (Slot pattern renders <a> with button classes)
 *   - Dark mode is exercised via the @storybook/addon-themes toolbar toggle.
 */
const meta = {
  title: 'UI/Button',
  component: Button,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  argTypes: {
    variant: {
      control: 'inline-radio',
      options: ['primary', 'secondary', 'ghost', 'destructive'],
    },
    size: {
      control: 'inline-radio',
      options: ['sm', 'md', 'lg'],
    },
    loading: { control: 'boolean' },
    disabled: { control: 'boolean' },
    children: { control: 'text' },
  },
} satisfies Meta<typeof Button>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { children: 'Tiếp tục' },
}

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="destructive">Destructive</Button>
    </div>
  ),
}

export const AllSizes: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="sm">Small 36</Button>
      <Button size="md">Medium 44</Button>
      <Button size="lg">Large 56</Button>
    </div>
  ),
}

export const States: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button>Default</Button>
      <Button disabled>Disabled</Button>
      <Button loading>Đang xử lý</Button>
    </div>
  ),
}

export const WithIcons: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button leftIcon={<span aria-hidden>←</span>}>Quay lại</Button>
      <Button rightIcon={<span aria-hidden>→</span>}>Tiếp tục</Button>
    </div>
  ),
}

export const AsChild: Story = {
  render: () => (
    <Button asChild>
      <a href="#link">Liên kết dạng button</a>
    </Button>
  ),
}
