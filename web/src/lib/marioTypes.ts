import type { IconName } from '../components/Icon'

export const MARIO_STATE_ENDPOINT = '/api/v1/mario/state'
export const MARIO_EVENTS_ENDPOINT = '/api/v1/mario/events'
export const MARIO_CHAT_ENDPOINT = '/api/v1/mario/chat'

export const MARIO_STORAGE_KEYS = {
  optOut: 'mario.v1.opt_out',
  sessionHidden: 'mario.v1.session_hidden',
} as const

export type MarioEventType =
  | 'shown'
  | 'expanded'
  | 'minimized'
  | 'dismissed'
  | 'action_clicked'

export type MarioTone = 'neutral' | 'primary' | 'warning' | 'success'

export interface MarioActionChip {
  id: string
  label?: string
  label_key?: string
  route?: string
  href?: string
  icon?: IconName
  priority?: number
  route_patterns?: string[]
  disabled?: boolean
}

export interface MarioNudge {
  id: string
  title?: string
  title_key?: string
  body?: string
  body_key?: string
  route_patterns?: string[]
  priority?: number
}

export interface MarioHighlight {
  id: string
  label?: string
  label_key?: string
  tone?: MarioTone
  route_patterns?: string[]
}

export interface MarioState {
  enabled: boolean
  persona_name?: string
  message?: string
  message_key?: string
  message_params?: Record<string, unknown>
  action_chips: MarioActionChip[]
  nudge: MarioNudge | null
  highlight: MarioHighlight | null
}

export interface MarioEventPayload {
  event: MarioEventType
  route: string
  suggestion_id?: string
  metadata?: Record<string, string | number | boolean | null | undefined>
}

export interface MarioChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface MarioChatResponse {
  message: MarioChatMessage
}

const DEFAULT_ACTIONS: MarioActionChip[] = [
  {
    id: 'review_due',
    label_key: 'actions.reviewDue',
    route: '/learn/review',
    icon: 'RotateCcw',
    priority: 10,
    route_patterns: ['/', '/learn/*', '/vocab', '/review', '/daily'],
  },
  {
    id: 'daily_words',
    label_key: 'actions.dailyWords',
    route: '/learn/daily',
    icon: 'Flame',
    priority: 20,
    route_patterns: ['/', '/learn/*', '/vocab', '/review', '/daily'],
  },
  {
    id: 'practice_writing',
    label_key: 'actions.practiceWriting',
    route: '/practice/writing',
    icon: 'PenLine',
    priority: 30,
    route_patterns: ['/', '/progress', '/practice/*', '/write'],
  },
  {
    id: 'practice_listening',
    label_key: 'actions.practiceListening',
    route: '/practice/listening',
    icon: 'Headphones',
    priority: 40,
    route_patterns: ['/', '/practice/listening', '/listening', '/progress'],
  },
  {
    id: 'reading_lab',
    label_key: 'actions.readingLab',
    route: '/practice/reading',
    icon: 'FileText',
    priority: 50,
    route_patterns: ['/', '/practice/reading', '/reading', '/progress'],
  },
  {
    id: 'view_progress',
    label_key: 'actions.viewProgress',
    route: '/progress',
    icon: 'TrendingUp',
    priority: 60,
    route_patterns: ['/practice/*', '/learn/*', '/write', '/listening', '/reading'],
  },
]

export const FALLBACK_MARIO_STATE: MarioState = {
  enabled: true,
  persona_name: 'Mario',
  message_key: 'panel.defaultMessage',
  action_chips: DEFAULT_ACTIONS,
  nudge: {
    id: 'keep_momentum',
    title_key: 'nudge.title',
    body_key: 'nudge.body',
    route_patterns: ['*'],
  },
  highlight: {
    id: 'ready',
    label_key: 'highlight.label',
    tone: 'primary',
    route_patterns: ['*'],
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined
}

function asStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined
  const items = value.filter((item): item is string => typeof item === 'string')
  return items.length ? items : undefined
}

function asNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined
}

function asParams(value: unknown): Record<string, unknown> | undefined {
  return isRecord(value) ? value : undefined
}

function normalizeAction(value: unknown): MarioActionChip | null {
  if (!isRecord(value)) return null
  const id = asString(value.id)
  if (!id) return null
  return {
    id,
    label: asString(value.label),
    label_key: asString(value.label_key),
    route: asString(value.route),
    href: asString(value.href),
    icon: asString(value.icon) as IconName | undefined,
    priority: asNumber(value.priority),
    route_patterns: asStringArray(value.route_patterns),
    disabled: asBoolean(value.disabled),
  }
}

function normalizeSuggestion(value: unknown, index: number): MarioActionChip | null {
  if (!isRecord(value)) return null
  const id = asString(value.id)
  if (!id) return null
  return {
    id,
    label_key: asString(value.label_key),
    route: asString(value.route),
    priority: index + 1,
  }
}

function normalizeNudge(value: unknown): MarioNudge | null {
  if (!isRecord(value)) return null
  const id = asString(value.id)
  if (!id) return null
  return {
    id,
    title: asString(value.title),
    title_key: asString(value.title_key),
    body: asString(value.body),
    body_key: asString(value.body_key),
    route_patterns: asStringArray(value.route_patterns),
    priority: asNumber(value.priority),
  }
}

function normalizeHighlight(value: unknown): MarioHighlight | null {
  if (!isRecord(value)) return null
  const id = asString(value.id)
  if (!id) return null
  return {
    id,
    label: asString(value.label),
    label_key: asString(value.label_key),
    tone: asString(value.tone) as MarioTone | undefined,
    route_patterns: asStringArray(value.route_patterns),
  }
}

export function normalizeMarioState(value: unknown): MarioState {
  const source = isRecord(value) && isRecord(value.mario) ? value.mario : value
  if (!isRecord(source)) return FALLBACK_MARIO_STATE

  const actions = Array.isArray(source.action_chips)
    ? source.action_chips
      .map(normalizeAction)
      .filter((action): action is MarioActionChip => action !== null)
    : Array.isArray(source.suggestions)
      ? source.suggestions
        .map(normalizeSuggestion)
        .filter((action): action is MarioActionChip => action !== null)
      : FALLBACK_MARIO_STATE.action_chips

  const greeting = isRecord(source.greeting) ? source.greeting : null

  return {
    enabled: source.enabled !== false,
    persona_name: asString(source.persona_name) ?? FALLBACK_MARIO_STATE.persona_name,
    message: asString(source.message),
    message_key:
      asString(source.message_key)
      ?? asString(greeting?.key)
      ?? FALLBACK_MARIO_STATE.message_key,
    message_params: asParams(greeting?.params),
    action_chips: actions.length ? actions : FALLBACK_MARIO_STATE.action_chips,
    nudge: source.nudge === null
      ? null
      : normalizeNudge(source.nudge) ?? FALLBACK_MARIO_STATE.nudge,
    highlight: source.highlight === null
      ? null
      : normalizeHighlight(source.highlight) ?? FALLBACK_MARIO_STATE.highlight,
  }
}

export function matchesRoutePattern(pathname: string, pattern: string): boolean {
  if (pattern === '*') return true
  if (pattern.endsWith('/*')) {
    const prefix = pattern.slice(0, -1)
    return pathname.startsWith(prefix)
  }
  return pathname === pattern || pathname.startsWith(`${pattern}/`)
}

export function itemMatchesRoute(
  item: { route_patterns?: string[] },
  pathname: string,
): boolean {
  const patterns = item.route_patterns
  if (!patterns || patterns.length === 0) return true
  return patterns.some((pattern) => matchesRoutePattern(pathname, pattern))
}

export function actionsForRoute(
  state: MarioState,
  pathname: string,
  limit = 3,
): MarioActionChip[] {
  return state.action_chips
    .filter((action) => itemMatchesRoute(action, pathname))
    .sort((a, b) => {
      const byPriority = (a.priority ?? 100) - (b.priority ?? 100)
      return byPriority || a.id.localeCompare(b.id)
    })
    .slice(0, limit)
}

export function nudgeForRoute(
  state: MarioState,
  pathname: string,
): MarioNudge | null {
  if (!state.nudge || !itemMatchesRoute(state.nudge, pathname)) return null
  return state.nudge
}

export function highlightForRoute(
  state: MarioState,
  pathname: string,
): MarioHighlight | null {
  if (!state.highlight || !itemMatchesRoute(state.highlight, pathname)) return null
  return state.highlight
}
