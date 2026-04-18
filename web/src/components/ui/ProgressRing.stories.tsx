import type { Meta, StoryObj } from '@storybook/react'
import ProgressRing from './ProgressRing'

/**
 * ProgressRing stories — preserved API from its pre-#121 location.
 * Sizes and completion ratios below cover the main home-screen use (64px)
 * plus a large variant used in progress views.
 */
const meta = {
  title: 'UI/ProgressRing',
  component: ProgressRing,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  argTypes: {
    completed: { control: { type: 'number', min: 0, max: 20 } },
    total: { control: { type: 'number', min: 1, max: 20 } },
    size: { control: { type: 'number', min: 32, max: 240, step: 8 } },
  },
} satisfies Meta<typeof ProgressRing>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { completed: 3, total: 4 },
}

export const Progressions: Story = {
  args: { completed: 0, total: 4 },
  render: () => (
    <div className="flex items-center gap-4">
      <ProgressRing completed={0} total={4} />
      <ProgressRing completed={1} total={4} />
      <ProgressRing completed={3} total={4} />
      <ProgressRing completed={4} total={4} />
    </div>
  ),
}

export const Large: Story = {
  args: { completed: 7, total: 10, size: 128 },
}
