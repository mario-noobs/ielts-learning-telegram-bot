// Barrel export for the core design-system primitives (#121 US-M6.2).
// Import via: `import { Button, Card, Modal, ... } from '@/components/ui'`

export { Button, buttonVariants, type ButtonProps } from './Button'
export { Input, type InputProps } from './Input'
export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from './Card'
export { Badge, badgeVariants, type BadgeProps } from './Badge'
export { default as ProgressRing } from './ProgressRing'
export {
  Modal,
  ModalTrigger,
  ModalClose,
  ModalPortal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalTitle,
  ModalDescription,
  ModalFooter,
  SimpleModal,
} from './Modal'
export {
  ToastProvider,
  useToast,
  Toast,
  type ToastPayload,
  type ToastVariant,
} from './Toast'
export { Tabs, TabsList, TabsTrigger, TabsContent } from './Tabs'
