import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Icon, { IconName } from '../components/Icon'
import LoadingScreen from '../components/LoadingScreen'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'
import { localizeError } from '../lib/apiError'
import { track } from '../lib/analytics'

type TeamRole = 'owner' | 'admin' | 'member'

interface TeamSummary {
  id: string
  name: string
  owner_uid: string
  plan_id: string
  seat_limit: number
  member_count: number
  my_role: TeamRole | null
  created_at: string | null
}

interface TeamMemberSummary {
  user_id: string
  name: string
  email: string | null
  role: TeamRole
  joined_at: string | null
  is_current_user: boolean
}

interface TeamOverviewResponse {
  week_start: string
  weekly_active_members: number
  study_minutes: number
  words_reviewed: number
  words_mastered: number
  quiz_count: number
  member_count: number
  seat_limit: number
}

interface TeamMemberProgressRow {
  user_id: string
  name: string
  email: string | null
  role: TeamRole
  last_active_date: string | null
  weekly_minutes: number
  words_reviewed: number
  due_words: number
  current_streak: number
}

interface TeamMeResponse {
  team: TeamSummary | null
}

interface TeamCreateResponse {
  team: TeamSummary
}

interface TeamInviteCreateResponse {
  token: string
  invite_url: string
  expires_at: string
}

interface TeamMembersResponse {
  team: TeamSummary
  members: TeamMemberSummary[]
}

interface TeamMemberUpdateResponse {
  member: TeamMemberSummary
}

interface TeamMemberProgressResponse {
  week_start: string
  members: TeamMemberProgressRow[]
}

interface TeamWordSnapshot {
  word: string
  definition_en: string
  definition_vi: string
  ipa: string
  part_of_speech: string
  example_en: string
  example_vi: string
  topic: string
}

interface TeamKnowledgePost {
  id: string
  team_id: string
  type: 'question' | 'shared_word' | 'note'
  category: string | null
  title: string | null
  body: string | null
  author: {
    user_id: string
    name: string
  }
  word_snapshot: TeamWordSnapshot | null
  saved_to_my_words: boolean
  existing_word_id: string | null
  reply_count: number
  helpful_count: number
  helpful_by_me: boolean
  created_at: string
}

interface TeamKnowledgePostsResponse {
  items: TeamKnowledgePost[]
  next_cursor: string | null
}

interface TeamKnowledgeReply {
  id: string
  post_id: string
  team_id: string
  author: {
    user_id: string
    name: string
  }
  body: string
  helpful_count: number
  helpful_by_me: boolean
  created_at: string
}

interface TeamCreateKnowledgePostResponse {
  post: TeamKnowledgePost
}

interface TeamKnowledgeRepliesResponse {
  items: TeamKnowledgeReply[]
  next_cursor: string | null
}

interface TeamCreateKnowledgeReplyResponse {
  reply: TeamKnowledgeReply
}

interface TeamKnowledgeHelpfulResponse {
  target_type: 'post' | 'reply'
  target_id: string
  helpful_count: number
  helpful_by_me: boolean
}

interface TeamSaveSharedWordResponse {
  word: {
    id: string
  }
}

const KNOWLEDGE_CATEGORIES = ['general', 'vocabulary', 'writing', 'reading', 'listening']

const ROLE_META: Record<TeamRole, { icon: IconName; className: string }> = {
  owner: {
    icon: 'Crown',
    className: 'border-warning/30 bg-warning/15 text-warning',
  },
  admin: {
    icon: 'ShieldCheck',
    className: 'border-primary/30 bg-primary/10 text-primary',
  },
  member: {
    icon: 'Users',
    className: 'border-border bg-surface text-muted-fg',
  },
}

function absoluteInviteUrl(path: string) {
  if (typeof window === 'undefined') return path
  return new URL(path, window.location.origin).toString()
}

function formatDate(value: string | null) {
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
    .format(new Date(value))
}

export default function TeamPage() {
  const { t } = useTranslation(['team', 'common'])
  const { profile, refreshProfile } = useAuth()
  const [team, setTeam] = useState<TeamSummary | null>(null)
  const [members, setMembers] = useState<TeamMemberSummary[]>([])
  const [overview, setOverview] = useState<TeamOverviewResponse | null>(null)
  const [memberProgress, setMemberProgress] = useState<TeamMemberProgressRow[]>([])
  const [knowledgePosts, setKnowledgePosts] = useState<TeamKnowledgePost[]>([])
  const [repliesByPost, setRepliesByPost] = useState<Record<string, TeamKnowledgeReply[]>>({})
  const [loading, setLoading] = useState(true)
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [name, setName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [inviteLoading, setInviteLoading] = useState(false)
  const [memberAction, setMemberAction] = useState('')
  const [knowledgeAction, setKnowledgeAction] = useState('')
  const [helpfulAction, setHelpfulAction] = useState('')
  const [deleteAction, setDeleteAction] = useState('')
  const [openPostId, setOpenPostId] = useState('')
  const [replyLoading, setReplyLoading] = useState('')
  const [replySubmitting, setReplySubmitting] = useState('')
  const [questionSubmitting, setQuestionSubmitting] = useState(false)
  const [questionCategory, setQuestionCategory] = useState('general')
  const [questionTitle, setQuestionTitle] = useState('')
  const [questionBody, setQuestionBody] = useState('')
  const [replyTextByPost, setReplyTextByPost] = useState<Record<string, string>>({})
  const [invite, setInvite] = useState<TeamInviteCreateResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  const loadWorkspace = useCallback(async (
    teamId: string,
    role: TeamRole | null,
    trackView = false,
  ) => {
    setWorkspaceLoading(true)
    try {
      const [membersRes, overviewRes, knowledgeRes] = await Promise.all([
        apiFetch<TeamMembersResponse>(`/api/v1/teams/${encodeURIComponent(teamId)}/members`),
        apiFetch<TeamOverviewResponse>(`/api/v1/teams/${encodeURIComponent(teamId)}/overview`),
        apiFetch<TeamKnowledgePostsResponse>(
          `/api/v1/teams/${encodeURIComponent(teamId)}/knowledge/posts?limit=10`,
        ),
      ])
      setTeam(membersRes.team)
      setMembers(membersRes.members)
      setOverview(overviewRes)
      setKnowledgePosts(knowledgeRes.items)
      setRepliesByPost({})
      setOpenPostId('')
      if (role === 'owner' || role === 'admin') {
        const progressRes = await apiFetch<TeamMemberProgressResponse>(
          `/api/v1/teams/${encodeURIComponent(teamId)}/member-progress`,
        )
        setMemberProgress(progressRes.members)
      } else {
        setMemberProgress([])
      }
      if (trackView) {
        void apiFetch(`/api/v1/teams/${encodeURIComponent(teamId)}/views`, {
          method: 'POST',
        }).catch(() => undefined)
        track('team_dashboard_viewed', {
          team_id: teamId,
          role: role ?? 'member',
          member_count: overviewRes.member_count,
        })
      }
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setWorkspaceLoading(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const res = await apiFetch<TeamMeResponse>('/api/v1/teams/me')
        if (cancelled) return
        setTeam(res.team)
        if (res.team) await loadWorkspace(res.team.id, res.team.my_role, true)
      } catch (e) {
        if (!cancelled) setError(localizeError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [loadWorkspace])

  const fullInviteUrl = useMemo(
    () => (invite ? absoluteInviteUrl(invite.invite_url) : ''),
    [invite],
  )

  const canManageMembers = team?.my_role === 'owner' || team?.my_role === 'admin'
  const canChangeRoles = team?.my_role === 'owner'
  const canDeletePost = (post: TeamKnowledgePost) =>
    canManageMembers || post.author.user_id === profile?.id
  const canDeleteReply = (reply: TeamKnowledgeReply) =>
    canManageMembers || reply.author.user_id === profile?.id

  const createTeam = async (event: FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setSubmitting(true)
    setError('')
    try {
      const res = await apiFetch<TeamCreateResponse>('/api/v1/teams', {
        method: 'POST',
        body: JSON.stringify({ name: trimmed }),
      })
      setTeam(res.team)
      await Promise.all([
        refreshProfile(),
        loadWorkspace(res.team.id, res.team.my_role, true),
      ])
      track('team_created', { team_id: res.team.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setSubmitting(false)
    }
  }

  const createInvite = async () => {
    if (!team) return
    setInviteLoading(true)
    setError('')
    setCopied(false)
    try {
      const res = await apiFetch<TeamInviteCreateResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/invites`,
        {
          method: 'POST',
          body: JSON.stringify({ role: 'member' }),
        },
      )
      setInvite(res)
      track('team_invite_created', { team_id: team.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setInviteLoading(false)
    }
  }

  const copyInvite = async () => {
    if (!fullInviteUrl) return
    await navigator.clipboard?.writeText(fullInviteUrl)
    setCopied(true)
  }

  const updateRole = async (member: TeamMemberSummary, role: 'admin' | 'member') => {
    if (!team || member.role === role) return
    setMemberAction(member.user_id)
    setError('')
    try {
      const res = await apiFetch<TeamMemberUpdateResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/members/${encodeURIComponent(member.user_id)}`,
        {
          method: 'PATCH',
          body: JSON.stringify({ role }),
        },
      )
      setMembers((items) => items.map((item) => (
        item.user_id === member.user_id ? res.member : item
      )))
      track('team_member_role_updated', { team_id: team.id, role })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setMemberAction('')
    }
  }

  const removeMember = async (member: TeamMemberSummary) => {
    if (!team) return
    const confirmed = window.confirm(t('members.removeConfirm', { name: member.name }))
    if (!confirmed) return
    setMemberAction(member.user_id)
    setError('')
    try {
      await apiFetch(
        `/api/v1/teams/${encodeURIComponent(team.id)}/members/${encodeURIComponent(member.user_id)}`,
        { method: 'DELETE' },
      )
      await refreshProfile()
      if (member.is_current_user) {
        setTeam(null)
        setMembers([])
        setOverview(null)
        setMemberProgress([])
        setKnowledgePosts([])
        setRepliesByPost({})
        setOpenPostId('')
      } else {
        await loadWorkspace(team.id, team.my_role)
      }
      track('team_member_removed', { team_id: team.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setMemberAction('')
    }
  }

  const saveSharedWord = async (post: TeamKnowledgePost) => {
    if (!team || post.saved_to_my_words) return
    setKnowledgeAction(post.id)
    setError('')
    try {
      const res = await apiFetch<TeamSaveSharedWordResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts/${encodeURIComponent(post.id)}/save-word`,
        { method: 'POST' },
      )
      setKnowledgePosts((items) => items.map((item) => (
        item.id === post.id
          ? { ...item, saved_to_my_words: true, existing_word_id: res.word.id }
          : item
      )))
      track('team_shared_word_saved', { team_id: team.id, post_id: post.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setKnowledgeAction('')
    }
  }

  const createQuestion = async (event: FormEvent) => {
    event.preventDefault()
    if (!team) return
    const title = questionTitle.trim()
    const body = questionBody.trim()
    if (!title || !body) return
    setQuestionSubmitting(true)
    setError('')
    try {
      const res = await apiFetch<TeamCreateKnowledgePostResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts`,
        {
          method: 'POST',
          body: JSON.stringify({
            type: 'question',
            category: questionCategory,
            title,
            body,
          }),
        },
      )
      setKnowledgePosts((items) => [res.post, ...items])
      setQuestionTitle('')
      setQuestionBody('')
      setQuestionCategory('general')
      track('team_knowledge_question_created', { team_id: team.id, post_id: res.post.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setQuestionSubmitting(false)
    }
  }

  const loadReplies = async (post: TeamKnowledgePost) => {
    if (!team) return
    if (openPostId === post.id) {
      setOpenPostId('')
      return
    }
    setOpenPostId(post.id)
    if (repliesByPost[post.id]) return
    setReplyLoading(post.id)
    setError('')
    try {
      const res = await apiFetch<TeamKnowledgeRepliesResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts/${encodeURIComponent(post.id)}/replies?limit=20`,
      )
      setRepliesByPost((items) => ({ ...items, [post.id]: res.items }))
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setReplyLoading('')
    }
  }

  const createReply = async (post: TeamKnowledgePost) => {
    if (!team) return
    const body = (replyTextByPost[post.id] || '').trim()
    if (!body) return
    setReplySubmitting(post.id)
    setError('')
    try {
      const res = await apiFetch<TeamCreateKnowledgeReplyResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts/${encodeURIComponent(post.id)}/replies`,
        {
          method: 'POST',
          body: JSON.stringify({ body }),
        },
      )
      setRepliesByPost((items) => ({
        ...items,
        [post.id]: [...(items[post.id] || []), res.reply],
      }))
      setReplyTextByPost((items) => ({ ...items, [post.id]: '' }))
      setKnowledgePosts((items) => items.map((item) => (
        item.id === post.id ? { ...item, reply_count: item.reply_count + 1 } : item
      )))
      track('team_knowledge_reply_created', { team_id: team.id, post_id: post.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setReplySubmitting('')
    }
  }

  const togglePostHelpful = async (post: TeamKnowledgePost) => {
    if (!team) return
    setHelpfulAction(`post:${post.id}`)
    setError('')
    try {
      const res = await apiFetch<TeamKnowledgeHelpfulResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts/${encodeURIComponent(post.id)}/helpful`,
        { method: 'POST' },
      )
      setKnowledgePosts((items) => items.map((item) => (
        item.id === post.id
          ? { ...item, helpful_count: res.helpful_count, helpful_by_me: res.helpful_by_me }
          : item
      )))
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setHelpfulAction('')
    }
  }

  const toggleReplyHelpful = async (postId: string, reply: TeamKnowledgeReply) => {
    if (!team) return
    setHelpfulAction(`reply:${reply.id}`)
    setError('')
    try {
      const res = await apiFetch<TeamKnowledgeHelpfulResponse>(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts/${encodeURIComponent(postId)}/replies/${encodeURIComponent(reply.id)}/helpful`,
        { method: 'POST' },
      )
      setRepliesByPost((items) => ({
        ...items,
        [postId]: (items[postId] || []).map((item) => (
          item.id === reply.id
            ? { ...item, helpful_count: res.helpful_count, helpful_by_me: res.helpful_by_me }
            : item
        )),
      }))
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setHelpfulAction('')
    }
  }

  const deletePost = async (post: TeamKnowledgePost) => {
    if (!team || !canDeletePost(post)) return
    const confirmed = window.confirm(t('knowledge.deletePostConfirm'))
    if (!confirmed) return
    setDeleteAction(`post:${post.id}`)
    setError('')
    try {
      await apiFetch(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts/${encodeURIComponent(post.id)}`,
        { method: 'DELETE' },
      )
      setKnowledgePosts((items) => items.filter((item) => item.id !== post.id))
      setRepliesByPost((items) => {
        const next = { ...items }
        delete next[post.id]
        return next
      })
      if (openPostId === post.id) setOpenPostId('')
      track('team_knowledge_post_deleted', { team_id: team.id, post_id: post.id })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setDeleteAction('')
    }
  }

  const deleteReply = async (post: TeamKnowledgePost, reply: TeamKnowledgeReply) => {
    if (!team || !canDeleteReply(reply)) return
    const confirmed = window.confirm(t('knowledge.deleteReplyConfirm'))
    if (!confirmed) return
    setDeleteAction(`reply:${reply.id}`)
    setError('')
    try {
      await apiFetch(
        `/api/v1/teams/${encodeURIComponent(team.id)}/knowledge/posts/${encodeURIComponent(post.id)}/replies/${encodeURIComponent(reply.id)}`,
        { method: 'DELETE' },
      )
      setRepliesByPost((items) => ({
        ...items,
        [post.id]: (items[post.id] || []).filter((item) => item.id !== reply.id),
      }))
      setKnowledgePosts((items) => items.map((item) => (
        item.id === post.id
          ? { ...item, reply_count: Math.max(0, item.reply_count - 1) }
          : item
      )))
      track('team_knowledge_reply_deleted', {
        team_id: team.id,
        post_id: post.id,
        reply_id: reply.id,
      })
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setDeleteAction('')
    }
  }

  const RoleBadge = ({ role }: { role: TeamRole }) => {
    const meta = ROLE_META[role]
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-semibold ${meta.className}`}
      >
        <Icon name={meta.icon} size="sm" className="text-current" />
        {t(`roles.${role}`)}
      </span>
    )
  }

  const overviewStats = overview ? [
    {
      key: 'active',
      icon: 'Users' as IconName,
      label: t('overview.activeMembers'),
      value: String(overview.weekly_active_members),
    },
    {
      key: 'minutes',
      icon: 'Clock' as IconName,
      label: t('overview.studyMinutes'),
      value: String(overview.study_minutes),
    },
    {
      key: 'reviewed',
      icon: 'RotateCcw' as IconName,
      label: t('overview.wordsReviewed'),
      value: String(overview.words_reviewed),
    },
    {
      key: 'mastered',
      icon: 'Trophy' as IconName,
      label: t('overview.wordsMastered'),
      value: String(overview.words_mastered),
    },
    {
      key: 'quiz',
      icon: 'ClipboardCheck' as IconName,
      label: t('overview.quizCount'),
      value: String(overview.quiz_count),
    },
  ] : []
  const hasActivity = overviewStats.some((item) => Number(item.value) > 0)
  const seatsRemaining = team ? Math.max(0, team.seat_limit - team.member_count) : 0

  if (loading) {
    return <LoadingScreen className="mx-auto max-w-5xl p-4" />
  }

  return (
    <div className="mx-auto max-w-5xl p-4">
      <header className="mb-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary">
          {t('page.eyebrow')}
        </p>
        <h1 className="mt-2 text-2xl font-bold text-fg">{t('page.heading')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-fg">{t('page.subtitle')}</p>
      </header>

      {error && (
        <p className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      {team ? (
        <div className="space-y-4">
          <section className="rounded-lg border border-border bg-surface-raised p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-medium text-muted-fg">{t('workspace.title')}</p>
                <h2 className="mt-1 text-xl font-semibold text-fg">{team.name}</h2>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="text-sm text-muted-fg">{t('workspace.roleLabel')}</span>
                  <RoleBadge role={team.my_role ?? 'member'} />
                </div>
              </div>
              <div className="inline-flex items-center gap-2 rounded-md bg-primary/10 px-3 py-2 text-sm font-medium text-primary">
                <Icon name="Users" size="sm" variant="primary" />
                {t('workspace.members', {
                  count: team.member_count,
                  limit: team.seat_limit,
                })}
              </div>
            </div>
            <p className="mt-4 text-sm text-muted-fg">{t('workspace.privacy')}</p>
            <p className="mt-2 text-xs text-muted-fg">
              {seatsRemaining > 0
                ? t('beta.seatsRemaining', { count: seatsRemaining })
                : t('beta.full')}
            </p>
          </section>

          <section className="rounded-lg border border-border bg-surface-raised p-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-fg">{t('overview.title')}</h2>
                <p className="text-sm text-muted-fg">
                  {overview ? t('overview.weekStart', { date: formatDate(overview.week_start) }) : t('overview.loading')}
                </p>
              </div>
              {workspaceLoading && (
                <span className="inline-flex items-center gap-2 text-sm text-muted-fg">
                  <Icon name="Loader2" size="sm" className="animate-spin" />
                  {t('overview.loading')}
                </span>
              )}
            </div>

            {overview && (
              <>
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  {overviewStats.map((item) => (
                    <div key={item.key} className="rounded-md border border-border bg-bg p-3">
                      <div className="flex items-center gap-2 text-xs font-medium text-muted-fg">
                        <Icon name={item.icon} size="sm" variant="muted" />
                        {item.label}
                      </div>
                      <p className="mt-2 text-2xl font-semibold text-fg">{item.value}</p>
                    </div>
                  ))}
                </div>
                {!hasActivity && (
                  <p className="mt-3 rounded-md border border-border bg-bg px-3 py-2 text-sm text-muted-fg">
                    {t('overview.empty')}
                  </p>
                )}
              </>
            )}
          </section>

          <section className="rounded-lg border border-border bg-surface-raised p-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-fg">{t('knowledge.title')}</h2>
                <p className="mt-1 max-w-xl text-sm text-muted-fg">{t('knowledge.description')}</p>
              </div>
              <span className="inline-flex w-fit items-center gap-1.5 rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                <Icon name="BookOpen" size="sm" variant="primary" />
                {t('knowledge.badge')}
              </span>
            </div>

            <form onSubmit={createQuestion} className="mt-4 rounded-lg border border-border bg-bg p-3">
              <div className="grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)]">
                <label className="block text-sm font-medium text-fg" htmlFor="knowledge-category">
                  {t('knowledge.askCategory')}
                  <select
                    id="knowledge-category"
                    value={questionCategory}
                    onChange={(event) => setQuestionCategory(event.target.value)}
                    className="mt-1 min-h-10 w-full rounded-md border border-border bg-surface px-2 text-sm text-fg"
                  >
                    {KNOWLEDGE_CATEGORIES.map((category) => (
                      <option key={category} value={category}>
                        {t(`knowledge.categories.${category}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm font-medium text-fg" htmlFor="knowledge-title">
                  {t('knowledge.askTitle')}
                  <input
                    id="knowledge-title"
                    value={questionTitle}
                    onChange={(event) => setQuestionTitle(event.target.value)}
                    maxLength={160}
                    placeholder={t('knowledge.askTitlePlaceholder')}
                    className="mt-1 min-h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg placeholder:text-muted-fg"
                  />
                </label>
              </div>
              <label className="mt-3 block text-sm font-medium text-fg" htmlFor="knowledge-body">
                {t('knowledge.askBody')}
                <textarea
                  id="knowledge-body"
                  value={questionBody}
                  onChange={(event) => setQuestionBody(event.target.value)}
                  maxLength={2000}
                  rows={3}
                  placeholder={t('knowledge.askBodyPlaceholder')}
                  className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg placeholder:text-muted-fg"
                />
              </label>
              <div className="mt-3 flex justify-end">
                <button
                  type="submit"
                  disabled={questionSubmitting || !questionTitle.trim() || !questionBody.trim()}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-60"
                >
                  {questionSubmitting && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
                  {questionSubmitting ? t('knowledge.asking') : t('knowledge.ask')}
                </button>
              </div>
            </form>

            <div className="mt-4 space-y-3">
              {knowledgePosts.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border bg-bg px-4 py-5">
                  <p className="font-medium text-fg">{t('knowledge.emptyTitle')}</p>
                  <p className="mt-1 text-sm text-muted-fg">{t('knowledge.emptyDescription')}</p>
                </div>
              ) : (
                knowledgePosts.map((post) => {
                  const word = post.word_snapshot
                  const saving = knowledgeAction === post.id
                  const replies = repliesByPost[post.id] || []
                  const isOpen = openPostId === post.id
                  const loadingReplies = replyLoading === post.id
                  const replying = replySubmitting === post.id
                  const postHelpful = helpfulAction === `post:${post.id}`
                  const deletingPost = deleteAction === `post:${post.id}`
                  return (
                    <article key={post.id} className="rounded-lg border border-border bg-bg p-3">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-md bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                              {t(`knowledge.types.${post.type}`)}
                            </span>
                            {post.category && (
                              <span className="rounded-md bg-surface px-2 py-0.5 text-xs font-medium text-muted-fg">
                                {t(`knowledge.categories.${post.category}`, { defaultValue: post.category })}
                              </span>
                            )}
                            <span className="text-xs text-muted-fg">
                              {t('knowledge.byline', {
                                name: post.author.name,
                                date: formatDate(post.created_at),
                              })}
                            </span>
                          </div>
                          {word && (
                            <>
                              {post.type === 'shared_word' ? (
                                <h3 className="mt-2 text-base font-semibold text-fg">
                                  {word.word}
                                  {word.ipa && (
                                    <span className="ml-1.5 text-xs font-normal text-muted-fg">
                                      /{word.ipa}/
                                    </span>
                                  )}
                                </h3>
                              ) : (
                                <p className="mt-2 inline-flex rounded-md bg-surface px-2 py-1 text-xs font-medium text-muted-fg">
                                  {t('knowledge.wordContext', { word: word.word })}
                                </p>
                              )}
                              {(word.definition_vi || word.definition_en) && (
                                <p className="mt-1 text-sm text-muted-fg">
                                  {word.definition_vi || word.definition_en}
                                </p>
                              )}
                            </>
                          )}
                          {post.title && (!word || post.type !== 'shared_word') && (
                            <h3 className="mt-2 text-base font-semibold text-fg">{post.title}</h3>
                          )}
                          {post.body && (
                            <p className="mt-2 text-sm text-fg">{post.body}</p>
                          )}
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2 sm:justify-end">
                          {post.type === 'shared_word' && (
                            <button
                              type="button"
                              onClick={() => void saveSharedWord(post)}
                              disabled={post.saved_to_my_words || saving}
                              className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40 disabled:opacity-60"
                            >
                              <Icon
                                name={post.saved_to_my_words ? 'Check' : 'Plus'}
                                size="sm"
                                variant={post.saved_to_my_words ? 'success' : 'muted'}
                              />
                              {post.saved_to_my_words
                                ? t('knowledge.saved')
                                : saving
                                  ? t('knowledge.saving')
                                  : t('knowledge.save')}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => void togglePostHelpful(post)}
                            disabled={postHelpful}
                            className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40 disabled:opacity-60"
                          >
                            <Icon name="Heart" size="sm" variant={post.helpful_by_me ? 'danger' : 'muted'} />
                            {t('knowledge.helpful', { count: post.helpful_count })}
                          </button>
                          <button
                            type="button"
                            onClick={() => void loadReplies(post)}
                            className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:border-primary/40"
                          >
                            <Icon name={isOpen ? 'ChevronDown' : 'ChevronRight'} size="sm" variant="muted" />
                            {t('knowledge.replies', { count: post.reply_count })}
                          </button>
                          {canDeletePost(post) && (
                            <button
                              type="button"
                              onClick={() => void deletePost(post)}
                              disabled={deletingPost}
                              className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-md border border-danger/30 px-3 py-2 text-sm font-medium text-danger hover:bg-danger/10 disabled:opacity-60"
                            >
                              {deletingPost ? (
                                <Icon name="Loader2" size="sm" className="animate-spin text-danger" />
                              ) : (
                                <Icon name="X" size="sm" variant="danger" />
                              )}
                              {deletingPost ? t('knowledge.deleting') : t('knowledge.delete')}
                            </button>
                          )}
                        </div>
                      </div>
                      {isOpen && (
                        <div className="mt-3 border-t border-border pt-3">
                          {loadingReplies ? (
                            <p className="inline-flex items-center gap-2 text-sm text-muted-fg">
                              <Icon name="Loader2" size="sm" className="animate-spin" />
                              {t('knowledge.loadingReplies')}
                            </p>
                          ) : replies.length === 0 ? (
                            <p className="text-sm text-muted-fg">{t('knowledge.noReplies')}</p>
                          ) : (
                            <div className="space-y-3">
                              {replies.map((reply) => {
                                const replyHelpful = helpfulAction === `reply:${reply.id}`
                                const deletingReply = deleteAction === `reply:${reply.id}`
                                return (
                                  <div key={reply.id} className="rounded-md border border-border bg-surface p-3">
                                    <p className="text-xs text-muted-fg">
                                      {t('knowledge.replyByline', {
                                        name: reply.author.name,
                                        date: formatDate(reply.created_at),
                                      })}
                                    </p>
                                    <p className="mt-1 text-sm text-fg">{reply.body}</p>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      <button
                                        type="button"
                                        onClick={() => void toggleReplyHelpful(post.id, reply)}
                                        disabled={replyHelpful}
                                        className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-fg hover:border-primary/40 disabled:opacity-60"
                                      >
                                        <Icon name="Heart" size="sm" variant={reply.helpful_by_me ? 'danger' : 'muted'} />
                                        {t('knowledge.helpful', { count: reply.helpful_count })}
                                      </button>
                                      {canDeleteReply(reply) && (
                                        <button
                                          type="button"
                                          onClick={() => void deleteReply(post, reply)}
                                          disabled={deletingReply}
                                          className="inline-flex min-h-9 items-center justify-center gap-1.5 rounded-md border border-danger/30 px-2.5 py-1.5 text-xs font-medium text-danger hover:bg-danger/10 disabled:opacity-60"
                                        >
                                          {deletingReply ? (
                                            <Icon name="Loader2" size="sm" className="animate-spin text-danger" />
                                          ) : (
                                            <Icon name="X" size="sm" variant="danger" />
                                          )}
                                          {deletingReply ? t('knowledge.deleting') : t('knowledge.delete')}
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          )}
                          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                            <input
                              value={replyTextByPost[post.id] || ''}
                              onChange={(event) => setReplyTextByPost((items) => ({
                                ...items,
                                [post.id]: event.target.value,
                              }))}
                              maxLength={2000}
                              placeholder={t('knowledge.replyPlaceholder')}
                              className="min-h-10 flex-1 rounded-md border border-border bg-surface px-3 text-sm text-fg placeholder:text-muted-fg"
                            />
                            <button
                              type="button"
                              onClick={() => void createReply(post)}
                              disabled={replying || !(replyTextByPost[post.id] || '').trim()}
                              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-60"
                            >
                              {replying && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
                              {replying ? t('knowledge.replying') : t('knowledge.reply')}
                            </button>
                          </div>
                        </div>
                      )}
                    </article>
                  )
                })
              )}
            </div>
          </section>

          {canManageMembers && (
            <section className="rounded-lg border border-border bg-surface-raised p-4">
              <div>
                <h2 className="text-lg font-semibold text-fg">{t('progress.title')}</h2>
                <p className="mt-1 text-sm text-muted-fg">{t('progress.description')}</p>
              </div>
              <div className="mt-4 overflow-x-auto rounded-lg border border-border bg-bg">
                <table className="min-w-full divide-y divide-border text-sm">
                  <thead className="bg-surface">
                    <tr className="text-left text-xs font-semibold uppercase tracking-wide text-muted-fg">
                      <th className="px-3 py-2">{t('progress.member')}</th>
                      <th className="px-3 py-2">{t('progress.lastActive')}</th>
                      <th className="px-3 py-2">{t('progress.weeklyMinutes')}</th>
                      <th className="px-3 py-2">{t('progress.wordsReviewed')}</th>
                      <th className="px-3 py-2">{t('progress.dueWords')}</th>
                      <th className="px-3 py-2">{t('progress.streak')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {memberProgress.map((member) => (
                      <tr key={member.user_id}>
                        <td className="px-3 py-3">
                          <div className="flex flex-col gap-1">
                            <span className="font-medium text-fg">{member.name}</span>
                            <RoleBadge role={member.role} />
                          </div>
                        </td>
                        <td className="px-3 py-3 text-muted-fg">
                          {member.last_active_date
                            ? formatDate(member.last_active_date)
                            : t('progress.noActivity')}
                        </td>
                        <td className="px-3 py-3 font-medium text-fg">{member.weekly_minutes}</td>
                        <td className="px-3 py-3 text-fg">{member.words_reviewed}</td>
                        <td className="px-3 py-3 text-fg">{member.due_words}</td>
                        <td className="px-3 py-3 text-fg">
                          {t('progress.streakDays', { count: member.current_streak })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-muted-fg">{t('progress.privacy')}</p>
            </section>
          )}

          <section className="rounded-lg border border-border bg-surface-raised p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-fg">{t('members.title')}</h2>
                <p className="mt-1 max-w-xl text-sm text-muted-fg">{t('members.description')}</p>
              </div>
              {(team.my_role === 'owner' || team.my_role === 'admin') && (
                <button
                  type="button"
                  onClick={createInvite}
                  disabled={inviteLoading}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-70"
                >
                  {inviteLoading && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
                  {inviteLoading ? t('invite.creating') : t('invite.create')}
                </button>
              )}
            </div>

            {invite && (
              <div className="mt-4 rounded-lg border border-border bg-bg p-3">
                <label className="text-xs font-medium text-muted-fg" htmlFor="team-invite-link">
                  {t('invite.linkLabel')}
                </label>
                <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                  <input
                    id="team-invite-link"
                    readOnly
                    value={fullInviteUrl}
                    className="min-h-10 flex-1 rounded-md border border-border bg-surface px-3 text-sm text-fg"
                  />
                  <button
                    type="button"
                    onClick={copyInvite}
                    className="inline-flex min-h-10 items-center justify-center rounded-md border border-border px-3 py-2 text-sm font-medium text-fg hover:bg-surface"
                  >
                    {copied ? t('invite.copied') : t('invite.copy')}
                  </button>
                </div>
              </div>
            )}

            <div className="mt-4 divide-y divide-border rounded-lg border border-border bg-bg">
              {members.map((member) => {
                const canRemove = canManageMembers
                  && member.role !== 'owner'
                  && (team.my_role === 'owner' || member.role === 'member')
                const busy = memberAction === member.user_id
                return (
                  <div key={member.user_id} className="flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-semibold text-fg">{member.name}</p>
                        {member.is_current_user && (
                          <span className="rounded-md bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
                            {t('members.you')}
                          </span>
                        )}
                        <RoleBadge role={member.role} />
                      </div>
                      <p className="mt-1 truncate text-xs text-muted-fg">
                        {member.email || member.user_id}
                        {member.joined_at ? ` · ${t('members.joined', { date: formatDate(member.joined_at) })}` : ''}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {canChangeRoles && member.role !== 'owner' && (
                        <select
                          aria-label={t('members.roleActionLabel', { name: member.name })}
                          value={member.role}
                          disabled={busy}
                          onChange={(event) => updateRole(member, event.target.value as 'admin' | 'member')}
                          className="min-h-10 rounded-md border border-border bg-surface px-2 text-sm text-fg"
                        >
                          <option value="member">{t('roles.member')}</option>
                          <option value="admin">{t('roles.admin')}</option>
                        </select>
                      )}
                      {canRemove && (
                        <button
                          type="button"
                          onClick={() => removeMember(member)}
                          disabled={busy}
                          className="inline-flex min-h-10 items-center justify-center rounded-md border border-danger/30 px-3 py-2 text-sm font-medium text-danger hover:bg-danger/10 disabled:opacity-60"
                        >
                          {busy ? t('members.removing') : t('members.remove')}
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
        </div>
      ) : (
        <section className="rounded-lg border border-border bg-surface-raised p-4">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-fg">{t('create.title')}</h2>
            <p className="mt-1 text-sm text-muted-fg">{t('create.description')}</p>
          </div>
          <div className="mb-4 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-muted-fg">
            {t('empty.joinHint')}
          </div>
          <form onSubmit={createTeam} className="space-y-3">
            <label className="block text-sm font-medium text-fg" htmlFor="team-name">
              {t('create.nameLabel')}
            </label>
            <input
              id="team-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t('create.namePlaceholder')}
              maxLength={120}
              className="min-h-11 w-full rounded-md border border-border bg-bg px-3 text-sm text-fg placeholder:text-muted-fg"
            />
            <p className="text-xs text-muted-fg">{t('create.limit')}</p>
            <p className="text-xs text-muted-fg">{t('beta.createLimit')}</p>
            <button
              type="submit"
              disabled={submitting || !name.trim()}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 disabled:opacity-60"
            >
              {submitting && <Icon name="Loader2" size="sm" className="animate-spin text-on-primary" />}
              {submitting ? t('create.creating') : t('create.submit')}
            </button>
          </form>
        </section>
      )}
    </div>
  )
}
