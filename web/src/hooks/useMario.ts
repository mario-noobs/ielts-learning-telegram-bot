import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import {
  actionsForRoute,
  FALLBACK_MARIO_STATE,
  highlightForRoute,
  MARIO_CHAT_ENDPOINT,
  MARIO_EVENTS_ENDPOINT,
  MARIO_STATE_ENDPOINT,
  MARIO_STORAGE_KEYS,
  MarioActionChip,
  MarioChatMessage,
  MarioChatResponse,
  MarioEventPayload,
  MarioEventType,
  MarioHighlight,
  MarioNudge,
  MarioState,
  normalizeMarioState,
  nudgeForRoute,
} from '../lib/marioTypes'

type MarioStatus = 'idle' | 'loading' | 'ready' | 'error'
type MarioChatStatus = 'idle' | 'sending' | 'error'

export interface UseMarioResult {
  state: MarioState
  status: MarioStatus
  panelOpen: boolean
  hidden: boolean
  sessionHidden: boolean
  optedOut: boolean
  actions: MarioActionChip[]
  chatMessages: MarioChatMessage[]
  chatStatus: MarioChatStatus
  nudge: MarioNudge | null
  highlight: MarioHighlight | null
  openPanel: () => void
  closePanel: () => void
  dismissSession: () => void
  optOut: () => void
  selectAction: (action: MarioActionChip) => void
  sendChatMessage: (content: string) => Promise<void>
}

function readStorage(storage: Storage | undefined, key: string): boolean {
  try {
    return storage?.getItem(key) === '1'
  } catch {
    return false
  }
}

function writeStorage(storage: Storage | undefined, key: string, value: string): void {
  try {
    storage?.setItem(key, value)
  } catch {
    // Storage may be unavailable in private or embedded contexts.
  }
}

function localStore(): Storage | undefined {
  return typeof window === 'undefined' ? undefined : window.localStorage
}

function sessionStore(): Storage | undefined {
  return typeof window === 'undefined' ? undefined : window.sessionStorage
}

export function useMario(): UseMarioResult {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [state, setState] = useState<MarioState>(FALLBACK_MARIO_STATE)
  const [status, setStatus] = useState<MarioStatus>('idle')
  const [chatStatus, setChatStatus] = useState<MarioChatStatus>('idle')
  const [chatMessages, setChatMessages] = useState<MarioChatMessage[]>([])
  const [loadedRoute, setLoadedRoute] = useState<string | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [sessionHidden, setSessionHidden] = useState(() => (
    readStorage(sessionStore(), MARIO_STORAGE_KEYS.sessionHidden)
  ))
  const [optedOut, setOptedOut] = useState(() => (
    readStorage(localStore(), MARIO_STORAGE_KEYS.optOut)
  ))
  const viewedKeys = useRef<Set<string>>(new Set())

  const hidden = optedOut || sessionHidden || !state.enabled || loadedRoute !== pathname
  const actions = useMemo(() => actionsForRoute(state, pathname), [pathname, state])
  const nudge = useMemo(() => nudgeForRoute(state, pathname), [pathname, state])
  const highlight = useMemo(() => highlightForRoute(state, pathname), [pathname, state])

  const emitEvent = useCallback((
    type: MarioEventType,
    detail: Partial<MarioEventPayload> = {},
  ) => {
    if (optedOut) return
    void apiFetch(MARIO_EVENTS_ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({
        event: type,
        route: pathname,
        ...detail,
      } satisfies MarioEventPayload),
    }).catch(() => undefined)
  }, [optedOut, pathname])

  useEffect(() => {
    if (optedOut || sessionHidden) return
    let cancelled = false
    setStatus('loading')
    apiFetch<unknown>(
      `${MARIO_STATE_ENDPOINT}?route=${encodeURIComponent(pathname)}`,
    )
      .then((payload) => {
        if (cancelled) return
        setState(normalizeMarioState(payload))
        setLoadedRoute(pathname)
        setStatus('ready')
      })
      .catch(() => {
        if (cancelled) return
        setState(FALLBACK_MARIO_STATE)
        setLoadedRoute(pathname)
        setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [optedOut, pathname, sessionHidden])

  useEffect(() => {
    if (hidden) return
    if (loadedRoute !== pathname) return
    const viewKey = `${pathname}:${nudge?.id ?? 'no-nudge'}:${highlight?.id ?? 'no-highlight'}`
    if (viewedKeys.current.has(viewKey)) return
    viewedKeys.current.add(viewKey)
    emitEvent('shown', {
      metadata: {
        nudge_id: nudge?.id,
        highlight_id: highlight?.id,
      },
    })
  }, [emitEvent, hidden, highlight?.id, loadedRoute, nudge?.id, pathname])

  const openPanel = useCallback(() => {
    setPanelOpen(true)
    emitEvent('expanded', {
      metadata: {
        nudge_id: nudge?.id,
        highlight_id: highlight?.id,
      },
    })
  }, [emitEvent, highlight?.id, nudge?.id])

  const closePanel = useCallback(() => {
    setPanelOpen(false)
    emitEvent('minimized')
  }, [emitEvent])

  const dismissSession = useCallback(() => {
    writeStorage(sessionStore(), MARIO_STORAGE_KEYS.sessionHidden, '1')
    setPanelOpen(false)
    setSessionHidden(true)
    emitEvent('dismissed', { metadata: { scope: 'session' } })
  }, [emitEvent])

  const optOut = useCallback(() => {
    writeStorage(localStore(), MARIO_STORAGE_KEYS.optOut, '1')
    setPanelOpen(false)
    setOptedOut(true)
    emitEvent('dismissed', { metadata: { scope: 'profile' } })
    void apiFetch('/api/v1/me', {
      method: 'PATCH',
      body: JSON.stringify({ dismissed_onboarding: true }),
    }).catch(() => undefined)
  }, [emitEvent])

  const selectAction = useCallback((action: MarioActionChip) => {
    if (action.disabled) return
    emitEvent('action_clicked', { suggestion_id: action.id })
    setPanelOpen(false)
    if (action.route) {
      navigate(action.route)
      return
    }
    if (action.href && typeof window !== 'undefined') {
      window.open(action.href, '_blank', 'noopener,noreferrer')
    }
  }, [emitEvent, navigate])

  const sendChatMessage = useCallback(async (content: string) => {
    const trimmed = content.trim()
    if (!trimmed || chatStatus === 'sending') return

    const userMessage: MarioChatMessage = { role: 'user', content: trimmed }
    const history = [...chatMessages, userMessage].slice(-8)
    setChatMessages((current) => [...current, userMessage])
    setChatStatus('sending')

    try {
      const response = await apiFetch<MarioChatResponse>(MARIO_CHAT_ENDPOINT, {
        method: 'POST',
        body: JSON.stringify({
          message: trimmed,
          route: pathname,
          history,
        }),
      })
      setChatMessages((current) => [...current, response.message])
      setChatStatus('idle')
      emitEvent('action_clicked', {
        suggestion_id: 'chat_message',
        metadata: { message_length: trimmed.length },
      })
    } catch {
      setChatMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: "I couldn't reply just now. Please try again in a moment.",
        },
      ])
      setChatStatus('error')
    }
  }, [chatMessages, chatStatus, emitEvent, pathname])

  return {
    state,
    status,
    panelOpen,
    hidden,
    sessionHidden,
    optedOut,
    actions,
    chatMessages,
    chatStatus,
    nudge,
    highlight,
    openPanel,
    closePanel,
    dismissSession,
    optOut,
    selectAction,
    sendChatMessage,
  }
}
