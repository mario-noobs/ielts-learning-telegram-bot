import type { Meta, StoryObj } from '@storybook/react'
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from './Card'
import { Button } from './Button'

/**
 * Card stories — shows the composable sub-parts and a realistic dashboard
 * task layout. Darkens via the themes addon.
 */
const meta = {
  title: 'UI/Card',
  component: Card,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
} satisfies Meta<typeof Card>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Card className="w-80">
      <CardHeader>
        <CardTitle>Học 10 từ mới</CardTitle>
        <CardDescription>Topic: Education · 8 phút</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-fg">
          Ôn tập 10 từ vựng trong chủ đề Education, kèm phát âm và ví dụ.
        </p>
      </CardContent>
      <CardFooter>
        <Button size="sm">Bắt đầu</Button>
        <Button size="sm" variant="ghost">
          Để sau
        </Button>
      </CardFooter>
    </Card>
  ),
}

export const HeaderOnly: Story = {
  render: () => (
    <Card className="w-80">
      <CardHeader>
        <CardTitle>Chỉ phần tiêu đề</CardTitle>
        <CardDescription>Không có nội dung phía dưới.</CardDescription>
      </CardHeader>
    </Card>
  ),
}

export const ContentOnly: Story = {
  render: () => (
    <Card className="w-80">
      <CardContent className="pt-6">
        <p className="text-fg">Chỉ một đoạn nội dung, không header/footer.</p>
      </CardContent>
    </Card>
  ),
}
