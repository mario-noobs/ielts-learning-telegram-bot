import type { Meta, StoryObj } from '@storybook/react'
import { ToastProvider, useToast } from './Toast'
import { Button } from './Button'

/**
 * Toast stories — uses the Provider + useToast() hook.
 * Buttons trigger toasts that auto-dismiss after 3s (default).
 */

function Demo() {
  const { toast } = useToast()
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        onClick={() =>
          toast({
            title: 'Đã lưu cài đặt',
            description: 'Thay đổi của bạn đã được đồng bộ.',
            variant: 'success',
          })
        }
      >
        Success toast
      </Button>
      <Button
        variant="secondary"
        onClick={() =>
          toast({
            title: 'Thông báo',
            description: 'Bạn còn 18 ngày đến ngày thi.',
          })
        }
      >
        Default toast
      </Button>
      <Button
        variant="secondary"
        onClick={() =>
          toast({
            title: 'Sắp hết pin',
            description: 'Lưu bài trước khi mất kết nối.',
            variant: 'warning',
            duration: 6000,
          })
        }
      >
        Warning toast (6s)
      </Button>
      <Button
        variant="destructive"
        onClick={() =>
          toast({
            title: 'Không lưu được',
            description: 'Kiểm tra mạng rồi thử lại.',
            variant: 'danger',
          })
        }
      >
        Danger toast
      </Button>
    </div>
  )
}

const meta = {
  title: 'UI/Toast',
  component: Demo,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
  decorators: [
    (Story) => (
      <ToastProvider>
        <Story />
      </ToastProvider>
    ),
  ],
} satisfies Meta<typeof Demo>

export default meta
type Story = StoryObj<typeof meta>

export const Playground: Story = {}
