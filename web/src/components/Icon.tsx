/*
 * Icon registry — explicit named imports keep the bundle tree-shaken.
 * Add a new icon here before using it via <Icon name="...">.
 */
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Calendar,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileText,
  Flag,
  Flame,
  Globe,
  Headphones,
  Hourglass,
  Info,
  LayoutDashboard,
  Lightbulb,
  LogOut,
  Mail,
  Mic,
  Minus,
  PartyPopper,
  Plus,
  Pause,
  PenLine,
  Play,
  RotateCcw,
  Settings,
  ShieldCheck,
  Sparkles,
  SquarePen,
  Target,
  TrendingDown,
  TrendingUp,
  Trophy,
  User,
  Volume2,
  X,
  Zap,
  type LucideIcon,
} from 'lucide-react'

const REGISTRY = {
  AlertCircle, ArrowLeft, ArrowRight, BookOpen, Calendar, Check, CheckCircle2,
  ChevronRight, Clock, FileText, Flag, Flame, Globe, Headphones, Hourglass, Info,
  LayoutDashboard, Lightbulb, LogOut, Mail, Mic, Minus, PartyPopper, Pause,
  PenLine, Play, Plus, RotateCcw, Settings, ShieldCheck, Sparkles, SquarePen,
  Target, TrendingDown, TrendingUp, Trophy, User, Volume2, X, Zap,
} satisfies Record<string, LucideIcon>

export type IconName = keyof typeof REGISTRY

type Size = 'sm' | 'md' | 'lg' | 'xl'
type Variant = 'fg' | 'muted' | 'primary' | 'accent' | 'success' | 'warning' | 'danger'

const SIZE_PX: Record<Size, number> = { sm: 16, md: 20, lg: 24, xl: 32 }

const VARIANT_CLASS: Record<Variant, string> = {
  fg: 'text-fg',
  muted: 'text-muted-fg',
  primary: 'text-primary',
  accent: 'text-accent',
  success: 'text-success',
  warning: 'text-warning',
  danger: 'text-danger',
}

interface Props {
  name: IconName
  size?: Size
  variant?: Variant
  /** Sets aria-label and role="img". Omit to mark the icon decorative. */
  label?: string
  className?: string
}

export default function Icon({
  name,
  size = 'md',
  variant = 'fg',
  label,
  className = '',
}: Props) {
  const Cmp = REGISTRY[name]
  if (!Cmp) {
    if (import.meta.env.DEV) console.warn(`<Icon name="${name}"> not in registry`)
    return null
  }
  const a11y = label
    ? { 'aria-label': label, role: 'img' as const }
    : { 'aria-hidden': true, focusable: false as const }
  return (
    <Cmp
      size={SIZE_PX[size]}
      strokeWidth={1.75}
      className={`${VARIANT_CLASS[variant]} shrink-0 ${className}`}
      {...a11y}
    />
  )
}
