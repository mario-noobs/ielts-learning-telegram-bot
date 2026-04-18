import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ElementRef,
} from 'react'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import { cn } from '../../lib/utils'

/**
 * Tabs — Radix Tabs wrapped with tokens.
 *
 *   <Tabs defaultValue="one">
 *     <TabsList>
 *       <TabsTrigger value="one">Một</TabsTrigger>
 *       <TabsTrigger value="two">Hai</TabsTrigger>
 *     </TabsList>
 *     <TabsContent value="one">…</TabsContent>
 *     <TabsContent value="two">…</TabsContent>
 *   </Tabs>
 *
 * Keyboard navigation (Left/Right/Home/End) and aria wiring come from Radix.
 */

export const Tabs = TabsPrimitive.Root

export const TabsList = forwardRef<
  ElementRef<typeof TabsPrimitive.List>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      'inline-flex items-center justify-start gap-1 rounded-xl',
      'bg-surface p-1 border border-border',
      className,
    )}
    {...props}
  />
))
TabsList.displayName = 'TabsList'

export const TabsTrigger = forwardRef<
  ElementRef<typeof TabsPrimitive.Trigger>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      'inline-flex h-9 items-center justify-center whitespace-nowrap',
      'rounded-lg px-3 text-sm font-medium',
      'text-muted-fg',
      'transition-colors duration-base ease-out-soft',
      'hover:text-fg',
      'disabled:pointer-events-none disabled:opacity-50',
      'data-[state=active]:bg-surface-raised data-[state=active]:text-fg',
      'data-[state=active]:shadow-sm',
      className,
    )}
    {...props}
  />
))
TabsTrigger.displayName = 'TabsTrigger'

export const TabsContent = forwardRef<
  ElementRef<typeof TabsPrimitive.Content>,
  ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn('mt-4 text-fg', className)}
    {...props}
  />
))
TabsContent.displayName = 'TabsContent'
