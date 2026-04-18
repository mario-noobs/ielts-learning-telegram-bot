import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ElementRef,
  type HTMLAttributes,
  type ReactNode,
} from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { cn } from '../../lib/utils'

/**
 * Modal — Radix Dialog styled via tokens.
 *
 * Exports:
 *   <Modal>         = Dialog.Root (controls open state)
 *   <ModalTrigger>  = Dialog.Trigger
 *   <ModalContent>  = Dialog.Content + Overlay + Portal (all bundled)
 *   <ModalHeader>   layout for title/description
 *   <ModalTitle>    Dialog.Title (required for a11y)
 *   <ModalDescription>  Dialog.Description
 *   <ModalFooter>   layout for actions row
 *   <ModalClose>    Dialog.Close
 *
 * Focus trap, escape-key, click-outside-to-close, and initial-focus are all
 * handled by Radix. Durations route through --dur-base so reduced-motion
 * sessions snap in without animation.
 */

export const Modal = DialogPrimitive.Root
export const ModalTrigger = DialogPrimitive.Trigger
export const ModalClose = DialogPrimitive.Close
export const ModalPortal = DialogPrimitive.Portal

export const ModalOverlay = forwardRef<
  ElementRef<typeof DialogPrimitive.Overlay>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      // Scrim: semi-opaque black via fg token with low alpha so it themes.
      'fixed inset-0 z-50 bg-fg/40 backdrop-blur-[2px]',
      'data-[state=open]:animate-in data-[state=closed]:animate-out',
      'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      className,
    )}
    style={{ transitionDuration: 'var(--dur-base)' }}
    {...props}
  />
))
ModalOverlay.displayName = 'ModalOverlay'

export const ModalContent = forwardRef<
  ElementRef<typeof DialogPrimitive.Content>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <ModalPortal>
    <ModalOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        'fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2',
        'bg-surface-raised border border-border rounded-2xl shadow-lg',
        'text-fg',
        'p-4 sm:p-6',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
        className,
      )}
      style={{ transitionDuration: 'var(--dur-base)' }}
      {...props}
    >
      {children}
    </DialogPrimitive.Content>
  </ModalPortal>
))
ModalContent.displayName = 'ModalContent'

export function ModalHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex flex-col gap-1.5 text-left mb-4', className)}
      {...props}
    />
  )
}
ModalHeader.displayName = 'ModalHeader'

export const ModalTitle = forwardRef<
  ElementRef<typeof DialogPrimitive.Title>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn('text-lg font-semibold text-fg leading-tight', className)}
    {...props}
  />
))
ModalTitle.displayName = 'ModalTitle'

export const ModalDescription = forwardRef<
  ElementRef<typeof DialogPrimitive.Description>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-sm text-muted-fg', className)}
    {...props}
  />
))
ModalDescription.displayName = 'ModalDescription'

export function ModalFooter({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'flex flex-col-reverse gap-2 sm:flex-row sm:justify-end mt-6',
        className,
      )}
      {...props}
    />
  )
}
ModalFooter.displayName = 'ModalFooter'

/** Convenience helper for stories / tests that just need a full modal shell. */
export interface SimpleModalProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  trigger?: ReactNode
}
export function SimpleModal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  trigger,
}: SimpleModalProps) {
  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      {trigger ? <ModalTrigger asChild>{trigger}</ModalTrigger> : null}
      <ModalContent>
        <ModalHeader>
          <ModalTitle>{title}</ModalTitle>
          {description ? (
            <ModalDescription>{description}</ModalDescription>
          ) : null}
        </ModalHeader>
        {children}
        {footer ? <ModalFooter>{footer}</ModalFooter> : null}
      </ModalContent>
    </Modal>
  )
}
