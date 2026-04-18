import type { Meta, StoryObj } from '@storybook/react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from './Tabs'

/**
 * Tabs stories — segmented control pattern used for Task 1/Task 2 toggles,
 * Listening type filters, etc. Radix handles Left/Right/Home/End key nav.
 */
const meta = {
  title: 'UI/Tabs',
  component: Tabs,
  tags: ['autodocs'],
  parameters: { layout: 'centered' },
} satisfies Meta<typeof Tabs>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Tabs defaultValue="t1" className="w-80">
      <TabsList>
        <TabsTrigger value="t1">Task 1</TabsTrigger>
        <TabsTrigger value="t2">Task 2</TabsTrigger>
      </TabsList>
      <TabsContent value="t1">
        <p className="text-sm text-fg">
          Mô tả biểu đồ / biểu bảng (150 từ).
        </p>
      </TabsContent>
      <TabsContent value="t2">
        <p className="text-sm text-fg">Luận văn ý kiến (250 từ).</p>
      </TabsContent>
    </Tabs>
  ),
}

export const ThreeTabs: Story = {
  render: () => (
    <Tabs defaultValue="all" className="w-96">
      <TabsList>
        <TabsTrigger value="all">Tất cả</TabsTrigger>
        <TabsTrigger value="dict">Dictation</TabsTrigger>
        <TabsTrigger value="gap">Gap fill</TabsTrigger>
      </TabsList>
      <TabsContent value="all">Tất cả bài nghe.</TabsContent>
      <TabsContent value="dict">Chỉ bài dictation.</TabsContent>
      <TabsContent value="gap">Chỉ bài gap fill.</TabsContent>
    </Tabs>
  ),
}

export const Disabled: Story = {
  render: () => (
    <Tabs defaultValue="a" className="w-80">
      <TabsList>
        <TabsTrigger value="a">Bật</TabsTrigger>
        <TabsTrigger value="b" disabled>
          Khóa
        </TabsTrigger>
      </TabsList>
      <TabsContent value="a">Tab được bật.</TabsContent>
      <TabsContent value="b">Không truy cập được.</TabsContent>
    </Tabs>
  ),
}
