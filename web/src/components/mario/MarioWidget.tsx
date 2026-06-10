import { FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Icon, { IconName } from '../Icon'
import { useMario } from '../../hooks/useMario'
import { cn } from '../../lib/utils'
import type { MarioActionChip, MarioHighlight, MarioNudge } from '../../lib/marioTypes'

const ACTION_ICON: Record<string, IconName> = {
  review_due: 'RotateCcw',
  daily_words: 'Flame',
  practice_writing: 'PenLine',
  practice_listening: 'Headphones',
  reading_lab: 'FileText',
  view_progress: 'TrendingUp',
}

const HIGHLIGHT_TONE: Record<NonNullable<MarioHighlight['tone']>, string> = {
  neutral: 'bg-surface text-fg border-border',
  primary: 'bg-primary/10 text-primary border-primary/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  success: 'bg-success/10 text-success border-success/20',
}

function resolveText(
  t: (key: string, options?: Record<string, unknown>) => string,
  key: string | undefined,
  fallback: string | undefined,
  defaultKey: string,
  params?: Record<string, unknown>,
): string {
  if (key) return t(key, { defaultValue: fallback ?? key, ...params })
  if (fallback) return fallback
  return t(defaultKey)
}

function actionLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  action: MarioActionChip,
): string {
  return resolveText(t, action.label_key, action.label, `actions.${action.id}`)
}

function nudgeTitle(
  t: (key: string, options?: Record<string, unknown>) => string,
  nudge: MarioNudge | null,
): string {
  if (!nudge) return t('nudge.title')
  return resolveText(t, nudge.title_key, nudge.title, 'nudge.title')
}

function nudgeBody(
  t: (key: string, options?: Record<string, unknown>) => string,
  nudge: MarioNudge | null,
): string {
  if (!nudge) return t('nudge.body')
  return resolveText(t, nudge.body_key, nudge.body, 'nudge.body')
}

export default function MarioWidget() {
  const { t } = useTranslation('mario')
  const mario = useMario()
  const [chatDraft, setChatDraft] = useState('')

  if (mario.hidden) return null

  const personaName = mario.state.persona_name ?? t('personaName')
  const message = resolveText(
    t,
    mario.state.message_key,
    mario.state.message,
    'panel.defaultMessage',
    mario.state.message_params,
  )
  const highlightLabel = mario.highlight
    ? resolveText(
      t,
      mario.highlight.label_key,
      mario.highlight.label,
      'highlight.label',
    )
    : null
  const highlightTone = mario.highlight?.tone ?? 'primary'
  const hasSignal = Boolean(mario.nudge || mario.highlight)
  const canSend = chatDraft.trim().length > 0 && mario.chatStatus !== 'sending'

  const submitChat = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSend) return
    const next = chatDraft
    setChatDraft('')
    await mario.sendChatMessage(next)
  }

  return (
    <aside
      aria-label={t('aria.region')}
      className="fixed right-4 bottom-[calc(4.75rem+env(safe-area-inset-bottom))] z-50 flex max-w-[calc(100vw-2rem)] flex-col items-end gap-3 md:right-6 md:bottom-6"
      data-testid="mario-widget"
    >
      {mario.panelOpen && (
        <section
          role="dialog"
          aria-label={t('aria.panel')}
          className="w-[min(26rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-border bg-surface-raised shadow-xl"
        >
          <div className="flex items-start gap-3 border-b border-border bg-bg/70 p-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary ring-1 ring-primary/20">
              <Icon name="Sparkles" size="md" variant="primary" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-semibold text-fg">{personaName}</h2>
              <p className="mt-1 text-sm leading-5 text-muted-fg">{message}</p>
            </div>
            <button
              type="button"
              onClick={mario.closePanel}
              aria-label={t('actions.closePanel')}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-muted-fg hover:bg-surface hover:text-fg"
            >
              <Icon name="X" size="sm" variant="muted" />
            </button>
          </div>

          <div className="max-h-[min(34rem,calc(100vh-11rem))] space-y-4 overflow-y-auto p-4">
            {mario.nudge && (
              <div className="rounded-xl border border-primary/20 bg-primary/10 p-3">
                <p className="text-sm font-medium text-fg">
                  {nudgeTitle(t, mario.nudge)}
                </p>
                <p className="mt-1 text-sm leading-5 text-muted-fg">
                  {nudgeBody(t, mario.nudge)}
                </p>
              </div>
            )}

            <div className="space-y-3">
              <p className="text-xs font-medium uppercase text-muted-fg">
                {t('chat.heading')}
              </p>
              <div
                aria-live="polite"
                className="space-y-2"
                data-testid="mario-chat-messages"
              >
                {mario.chatMessages.length === 0 && (
                  <div className="rounded-xl bg-bg px-3 py-2 text-sm leading-5 text-muted-fg">
                    {t('chat.empty')}
                  </div>
                )}
                {mario.chatMessages.map((item, index) => (
                  <div
                    key={`${item.role}-${index}`}
                    className={cn(
                      'rounded-xl px-3 py-2 text-sm leading-5',
                      item.role === 'user'
                        ? 'ml-8 bg-primary text-primary-fg'
                        : 'mr-8 bg-bg text-fg',
                    )}
                  >
                    {item.content}
                  </div>
                ))}
                {mario.chatStatus === 'sending' && (
                  <div className="mr-8 flex items-center gap-2 rounded-xl bg-bg px-3 py-2 text-sm text-muted-fg">
                    <Icon name="Loader2" size="sm" variant="muted" className="animate-spin" />
                    {t('chat.thinking')}
                  </div>
                )}
              </div>
              <form onSubmit={submitChat} className="flex items-end gap-2">
                <label htmlFor="mario-chat-input" className="sr-only">
                  {t('chat.inputLabel')}
                </label>
                <textarea
                  id="mario-chat-input"
                  value={chatDraft}
                  onChange={(event) => setChatDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      event.currentTarget.form?.requestSubmit()
                    }
                  }}
                  rows={2}
                  maxLength={800}
                  placeholder={t('chat.placeholder')}
                  className="min-h-[3rem] flex-1 resize-none rounded-xl border border-border bg-bg px-3 py-2 text-sm text-fg placeholder:text-muted-fg focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
                <button
                  type="submit"
                  disabled={!canSend}
                  aria-label={t('chat.send')}
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-fg hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Icon name="ArrowRight" size="md" variant="fg" className="text-primary-fg" />
                </button>
              </form>
            </div>

            <div>
              <p className="mb-2 text-xs font-medium uppercase text-muted-fg">
                {t('panel.actionsHeading')}
              </p>
              <div className="flex flex-wrap gap-2">
                {mario.actions.map((action) => {
                  const icon = action.icon ?? ACTION_ICON[action.id] ?? 'ChevronRight'
                  return (
                    <button
                      key={action.id}
                      type="button"
                      disabled={action.disabled}
                      onClick={() => mario.selectAction(action)}
                      className="inline-flex min-h-9 max-w-full items-center gap-2 rounded-full border border-border bg-bg px-3 py-1.5 text-sm font-medium text-fg hover:border-primary/40 hover:text-primary disabled:opacity-50"
                    >
                      <Icon name={icon} size="sm" variant="muted" />
                      <span className="truncate">{actionLabel(t, action)}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-border bg-bg/70 px-4 py-3">
            <button
              type="button"
              onClick={mario.dismissSession}
              className="text-sm font-medium text-muted-fg hover:text-fg"
            >
              {t('actions.dismissSession')}
            </button>
            <button
              type="button"
              onClick={mario.optOut}
              className="text-sm font-medium text-muted-fg hover:text-danger"
            >
              {t('actions.optOut')}
            </button>
          </div>
        </section>
      )}

      {!mario.panelOpen && mario.nudge && (
        <button
          type="button"
          onClick={mario.openPanel}
          className="max-w-[18rem] rounded-2xl border border-border bg-surface-raised px-3 py-2 text-left text-sm shadow-lg hover:border-primary/40"
        >
          <span className="block font-medium text-fg">
            {nudgeTitle(t, mario.nudge)}
          </span>
          <span className="mt-0.5 block truncate text-muted-fg">
            {nudgeBody(t, mario.nudge)}
          </span>
        </button>
      )}

      <div className="flex items-center gap-2">
        {!mario.panelOpen && highlightLabel && (
          <span
            className={cn(
              'hidden rounded-full border px-2.5 py-1 text-xs font-medium shadow-sm sm:inline-flex',
              HIGHLIGHT_TONE[highlightTone],
            )}
          >
            {highlightLabel}
          </span>
        )}
        <button
          type="button"
          onClick={mario.panelOpen ? mario.closePanel : mario.openPanel}
          aria-expanded={mario.panelOpen}
          aria-label={mario.panelOpen ? t('actions.closePanel') : t('actions.openPanel')}
          className={cn(
            'relative flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-fg shadow-xl transition-transform hover:scale-[1.02] focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-bg',
            hasSignal && !mario.panelOpen && 'ring-4 ring-primary/20',
          )}
          data-testid="mario-launcher"
        >
          {hasSignal && !mario.panelOpen && (
            <span
              aria-hidden="true"
              className="absolute -right-0.5 -top-0.5 h-3.5 w-3.5 rounded-full bg-warning ring-2 ring-surface-raised"
            />
          )}
          <Icon
            name={mario.panelOpen ? 'X' : 'Sparkles'}
            size="lg"
            variant="fg"
            className="text-primary-fg"
          />
        </button>
      </div>
    </aside>
  )
}
