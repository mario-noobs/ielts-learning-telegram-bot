import type { Meta, StoryObj } from '@storybook/react'
import type { ButtonHTMLAttributes } from 'react'

/**
 * Minimal inline Button used to prove Tailwind + design tokens render inside
 * Storybook. The real `<Button>` primitive ships in #121 under the shadcn-ui
 * import — at that point this story should be repointed at the real component
 * and the inline definition removed.
 */
function Button({
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={[
        'inline-flex items-center justify-center rounded-md px-4 py-2',
        'text-sm font-medium',
        'bg-primary text-primary-fg hover:bg-primary-hover',
        'transition-colors duration-base ease-out-soft',
        'focus-visible:outline-none',
        'disabled:opacity-50 disabled:pointer-events-none',
        className,
      ].join(' ')}
      {...props}
    />
  )
}

const meta = {
  title: 'UI/Button',
  component: Button,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    children: { control: 'text' },
    disabled: { control: 'boolean' },
  },
} satisfies Meta<typeof Button>

export default meta
type Story = StoryObj<typeof meta>

export const Primary: Story = {
  args: {
    children: 'Continue',
  },
}

export const Disabled: Story = {
  args: {
    children: 'Continue',
    disabled: true,
  },
}

/**
 * Renders three buttons side-by-side so the themes addon toggle exercises
 * light vs dark token values in a single snapshot.
 */
export const TokenShowcase: Story = {
  args: { children: 'Primary' },
  render: (args) => (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-6">
      <Button {...args} />
      <Button {...args} disabled>
        Disabled
      </Button>
      <span className="text-sm text-muted-fg">token-driven</span>
    </div>
  ),
}
