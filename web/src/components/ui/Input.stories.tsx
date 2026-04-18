import type { Meta, StoryObj } from '@storybook/react'
import { Input } from './Input'

/**
 * Input stories — default/error variants, sm/md sizes, addon slots,
 * and label+helper+error wiring (htmlFor / aria-describedby).
 */
const meta = {
  title: 'UI/Input',
  component: Input,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  argTypes: {
    variant: {
      control: 'inline-radio',
      options: ['default', 'error'],
    },
    inputSize: {
      control: 'inline-radio',
      options: ['sm', 'md'],
    },
  },
} satisfies Meta<typeof Input>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    label: 'Email',
    placeholder: 'you@example.com',
  },
  render: (args) => (
    <div className="w-72">
      <Input {...args} />
    </div>
  ),
}

export const WithHelper: Story = {
  render: () => (
    <div className="w-72">
      <Input
        label="Tên hiển thị"
        placeholder="Mario"
        helperText="Tối đa 40 ký tự, không dấu."
      />
    </div>
  ),
}

export const ErrorState: Story = {
  render: () => (
    <div className="w-72">
      <Input
        label="Email"
        defaultValue="không-hợp-lệ"
        errorText="Email không hợp lệ."
      />
    </div>
  ),
}

export const WithAddons: Story = {
  render: () => (
    <div className="flex flex-col gap-4 w-72">
      <Input
        label="Tìm kiếm"
        placeholder="tìm từ vựng…"
        leadingAddon={<span>🔍</span>}
      />
      <Input
        label="Kích thước (phút)"
        placeholder="20"
        trailingAddon={<span className="text-sm">phút</span>}
      />
    </div>
  ),
}

export const AllSizes: Story = {
  render: () => (
    <div className="flex flex-col gap-4 w-72">
      <Input inputSize="sm" label="Nhỏ" placeholder="sm" />
      <Input inputSize="md" label="Vừa (mặc định)" placeholder="md" />
    </div>
  ),
}

export const Disabled: Story = {
  render: () => (
    <div className="w-72">
      <Input label="Khóa" defaultValue="read only" disabled />
    </div>
  ),
}
