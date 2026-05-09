/**
 * /settings/groups/:id — view/edit a single group (US-#227).
 *
 * Members see a read-only view with an explicit banner. Owners get
 * the full editable form. Server enforces the same rule on PATCH so
 * the UI gating is convenience, not security.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import Icon from '../../components/Icon'
import { apiFetch } from '../../lib/api'
import { localizeError } from '../../lib/apiError'

interface GroupDetail {
  id: string
  name: string | null
  role: 'owner' | 'member'
  member_count: number
  owner_telegram_id: number | null

  default_band: number
  topics: string[]
  daily_time: string | null
  challenge_time: string | null
  word_count: number
  challenge_question_count: number
  challenge_deadline_minutes: number
}

export default function GroupDetailPage() {
  const { t } = useTranslation(['settings', 'common'])
  const { id } = useParams<{ id: string }>()
  const [group, setGroup] = useState<GroupDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Form state (mirrors the server fields). Hydrated from the GET
  // response and reset back to it after a successful PATCH.
  const [band, setBand] = useState(7.0)
  const [topicDraft, setTopicDraft] = useState('')
  const [topics, setTopics] = useState<string[]>([])
  const [dailyTime, setDailyTime] = useState('')
  const [challengeTime, setChallengeTime] = useState('')
  const [wordCount, setWordCount] = useState(10)
  const [questionCount, setQuestionCount] = useState(5)
  const [deadlineMin, setDeadlineMin] = useState(60)

  useEffect(() => {
    if (!id) return
    apiFetch<GroupDetail>(`/api/v1/groups/${id}`)
      .then((g) => {
        setGroup(g)
        setBand(g.default_band)
        setTopics(g.topics || [])
        setDailyTime(g.daily_time || '')
        setChallengeTime(g.challenge_time || '')
        setWordCount(g.word_count)
        setQuestionCount(g.challenge_question_count)
        setDeadlineMin(g.challenge_deadline_minutes)
      })
      .catch((e) => setError(localizeError(e)))
  }, [id])

  useEffect(() => {
    if (!saved) return
    const to = setTimeout(() => setSaved(false), 3000)
    return () => clearTimeout(to)
  }, [saved])

  if (!group && !error) {
    return (
      <div className="max-w-3xl mx-auto p-4">
        <p className="text-muted-fg">{t('common:status.loading')}</p>
      </div>
    )
  }
  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-4 space-y-3">
        <Link to="/settings/groups" className="text-sm text-muted-fg hover:text-fg inline-flex items-center gap-1">
          <Icon name="ArrowLeft" size="sm" /> {t('common:actions.back')}
        </Link>
        <div className="rounded-lg border border-danger/30 bg-danger/5 p-3 text-sm text-danger">
          {error}
        </div>
      </div>
    )
  }
  if (!group) return null

  const isOwner = group.role === 'owner'

  const addTopic = () => {
    const v = topicDraft.trim().toLowerCase()
    if (!v || topics.includes(v)) return
    setTopics([...topics, v])
    setTopicDraft('')
  }
  const removeTopic = (tp: string) => setTopics(topics.filter((x) => x !== tp))

  const save = async () => {
    if (!isOwner || !id) return
    setSaving(true)
    setError(null)
    try {
      // Only send changed fields. Compare against the loaded snapshot
      // so we don't write back unchanged values (admin audit churn).
      const patch: Record<string, unknown> = {}
      if (band !== group.default_band) patch.default_band = band
      if (JSON.stringify(topics) !== JSON.stringify(group.topics)) {
        patch.topics = topics
      }
      if ((dailyTime || null) !== group.daily_time) {
        patch.daily_time = dailyTime || ''
      }
      if ((challengeTime || null) !== group.challenge_time) {
        patch.challenge_time = challengeTime || ''
      }
      if (wordCount !== group.word_count) patch.word_count = wordCount
      if (questionCount !== group.challenge_question_count) {
        patch.challenge_question_count = questionCount
      }
      if (deadlineMin !== group.challenge_deadline_minutes) {
        patch.challenge_deadline_minutes = deadlineMin
      }

      const updated = await apiFetch<GroupDetail>(`/api/v1/groups/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      setGroup(updated)
      setSaved(true)
    } catch (e) {
      setError(localizeError(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <Link
        to="/settings/groups"
        className="text-sm text-muted-fg hover:text-fg inline-flex items-center gap-1"
      >
        <Icon name="ArrowLeft" size="sm" /> {t('common:actions.back')}
      </Link>
      <div>
        <h1 className="text-2xl font-bold text-fg">
          {group.name || t('groups.card.unnamed', { id: group.id })}
        </h1>
        <p className="text-sm text-muted-fg mt-1">
          {t('groups.card.memberCount', { count: group.member_count })}
        </p>
      </div>

      {/* Role banner — owner sees a green "you can edit" affordance,
          member sees an explicit yellow "view-only" notice. The previous
          tiny chip in the page header was easy to miss; this banner
          spans the full width and uses an icon so the role is obvious
          before the user touches any field. */}
      {isOwner ? (
        <div className="rounded-lg border border-success/30 bg-success/5 p-3 text-sm text-success">
          <div className="flex items-start gap-2">
            <Icon name="Crown" size="sm" className="mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold">{t('groups.roleBanner.owner.title')}</p>
              <p className="text-success/80 mt-0.5">
                {t('groups.roleBanner.owner.description')}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-warning/30 bg-warning/5 p-3 text-sm text-warning">
          <div className="flex items-start gap-2">
            <Icon name="Eye" size="sm" className="mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold">{t('groups.roleBanner.member.title')}</p>
              <p className="text-warning/80 mt-0.5">
                {t('groups.roleBanner.member.description')}
              </p>
            </div>
          </div>
        </div>
      )}

      {saved && (
        <div className="rounded-lg border border-success/30 bg-success/5 p-3 text-sm text-success">
          {t('groups.saved')}
        </div>
      )}

      <section className="rounded-xl border border-border bg-surface-raised p-4 space-y-4">
        <div>
          <label htmlFor="g-band" className="text-sm font-semibold text-fg block mb-1">
            {t('groups.fields.band')}: <span className="text-primary">{band.toFixed(1)}</span>
          </label>
          <input
            id="g-band"
            type="range"
            min={4.0}
            max={9.0}
            step={0.5}
            value={band}
            onChange={(e) => setBand(Number(e.target.value))}
            disabled={!isOwner}
            className="w-full disabled:opacity-50"
          />
        </div>

        <div>
          <label className="text-sm font-semibold text-fg block mb-1">
            {t('groups.fields.topics')}
          </label>
          <div className="flex flex-wrap gap-2 mb-2">
            {topics.map((tp) => (
              <span
                key={tp}
                className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-sm text-primary"
              >
                {tp}
                {isOwner && (
                  <button
                    type="button"
                    onClick={() => removeTopic(tp)}
                    aria-label={t('groups.fields.removeTopic', { topic: tp })}
                    className="text-primary/70 hover:text-primary"
                  >
                    ✕
                  </button>
                )}
              </span>
            ))}
          </div>
          {isOwner && (
            <div className="flex gap-2">
              <input
                type="text"
                value={topicDraft}
                onChange={(e) => setTopicDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addTopic()
                  }
                }}
                placeholder={t('groups.fields.topicsPlaceholder')}
                className="flex-1 px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none"
              />
              <button
                type="button"
                onClick={addTopic}
                disabled={!topicDraft.trim()}
                className="px-3 py-2 rounded-lg bg-primary text-primary-fg text-sm hover:bg-primary-hover disabled:opacity-50"
              >
                {t('common:actions.add')}
              </button>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="g-daily" className="text-sm font-semibold text-fg block mb-1">
              {t('groups.fields.dailyTime')}
            </label>
            <input
              id="g-daily"
              type="time"
              value={dailyTime}
              onChange={(e) => setDailyTime(e.target.value)}
              disabled={!isOwner}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none disabled:opacity-50"
            />
          </div>
          <div>
            <label htmlFor="g-challenge-time" className="text-sm font-semibold text-fg block mb-1">
              {t('groups.fields.challengeTime')}
            </label>
            <input
              id="g-challenge-time"
              type="time"
              value={challengeTime}
              onChange={(e) => setChallengeTime(e.target.value)}
              disabled={!isOwner}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none disabled:opacity-50"
            />
          </div>
          <div>
            <label htmlFor="g-wc" className="text-sm font-semibold text-fg block mb-1">
              {t('groups.fields.wordCount')}
            </label>
            <input
              id="g-wc"
              type="number"
              min={5}
              max={20}
              value={wordCount}
              onChange={(e) => setWordCount(Number(e.target.value))}
              disabled={!isOwner}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none disabled:opacity-50"
            />
          </div>
          <div>
            <label htmlFor="g-qc" className="text-sm font-semibold text-fg block mb-1">
              {t('groups.fields.questionCount')}
            </label>
            <input
              id="g-qc"
              type="number"
              min={3}
              max={10}
              value={questionCount}
              onChange={(e) => setQuestionCount(Number(e.target.value))}
              disabled={!isOwner}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none disabled:opacity-50"
            />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="g-dl" className="text-sm font-semibold text-fg block mb-1">
              {t('groups.fields.deadlineMinutes')}
            </label>
            <input
              id="g-dl"
              type="number"
              min={15}
              max={180}
              value={deadlineMin}
              onChange={(e) => setDeadlineMin(Number(e.target.value))}
              disabled={!isOwner}
              className="w-full px-3 py-2 rounded-lg border border-border bg-surface text-fg focus:border-primary focus:outline-none disabled:opacity-50"
            />
          </div>
        </div>

        {isOwner && (
          <button
            onClick={save}
            disabled={saving}
            className="w-full py-2 bg-primary text-primary-fg rounded-lg font-medium hover:bg-primary-hover disabled:opacity-50"
          >
            {saving ? t('common:status.saving') : t('common:actions.save')}
          </button>
        )}
      </section>
    </div>
  )
}
