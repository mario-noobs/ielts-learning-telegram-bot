import { useMemo, useState } from 'react'
import {
  CRITERIA,
  IssueType,
  ParagraphAnnotation,
  WritingSubmission,
} from '../lib/writing'

function bandColorClass(band: number): string {
  if (band >= 7.0) return 'bg-success'
  if (band >= 6.0) return 'bg-primary'
  if (band >= 5.0) return 'bg-warning'
  return 'bg-danger'
}

function issueColorClass(type: IssueType): { bg: string; text: string } {
  switch (type) {
    case 'grammar':
      return { bg: 'bg-danger/20', text: 'text-danger' }
    case 'weak_vocab':
      return { bg: 'bg-accent/20', text: 'text-accent' }
    case 'good':
      return { bg: 'bg-success/20', text: 'text-success' }
  }
}

function BandBadge({ band, target }: { band: number; target: number }) {
  const delta = Math.round((band - target) * 10) / 10
  const sign = delta > 0 ? '+' : ''
  return (
    <div className="flex items-center gap-3">
      <div className={`${bandColorClass(band)} text-primary-fg text-3xl font-bold px-5 py-3 rounded-xl`}>
        {band.toFixed(1)}
      </div>
      <div className="text-sm text-muted-fg">
        <div>Mục tiêu: {target.toFixed(1)}</div>
        <div className={delta >= 0 ? 'text-success' : 'text-danger'}>
          {delta === 0 ? 'Đúng mục tiêu' : `${sign}${delta.toFixed(1)}`}
        </div>
      </div>
    </div>
  )
}

export function ScorePanel({
  submission,
  targetBand,
}: {
  submission: WritingSubmission
  targetBand: number
}) {
  return (
    <div className="bg-surface-raised rounded-xl shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-fg">Điểm tổng</h2>
        <BandBadge band={submission.overall_band} target={targetBand} />
      </div>
      <div className="space-y-3">
        {CRITERIA.map((c) => {
          const score = submission.scores[c.key] || 0
          const pct = Math.min(100, (score / 9.0) * 100)
          const feedback = submission.criterion_feedback[c.key] || ''
          return (
            <div key={c.key}>
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-fg">{c.label}</span>
                <span className="font-mono text-fg">{score.toFixed(1)}</span>
              </div>
              <div className="h-2 bg-surface rounded-full overflow-hidden mt-1">
                <div
                  className={`h-full ${bandColorClass(score)}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              {feedback && <p className="text-xs text-muted-fg mt-1">{feedback}</p>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function HighlightedParagraph({
  paragraph,
  annotations,
  onSelect,
}: {
  paragraph: string
  annotations: ParagraphAnnotation[]
  onSelect: (a: ParagraphAnnotation) => void
}) {
  const segments = useMemo(() => {
    if (annotations.length === 0) {
      return [{ kind: 'plain' as const, text: paragraph }]
    }
    type Seg = { kind: 'plain' | 'hit'; text: string; ann?: ParagraphAnnotation }
    const out: Seg[] = []
    let cursor = 0
    const hits = annotations
      .map((a) => ({ ann: a, idx: paragraph.indexOf(a.excerpt) }))
      .filter((h) => h.idx >= 0 && h.ann.excerpt.length > 0)
      .sort((a, b) => a.idx - b.idx)
    for (const h of hits) {
      if (h.idx < cursor) continue
      if (h.idx > cursor) {
        out.push({ kind: 'plain', text: paragraph.slice(cursor, h.idx) })
      }
      out.push({
        kind: 'hit',
        text: paragraph.slice(h.idx, h.idx + h.ann.excerpt.length),
        ann: h.ann,
      })
      cursor = h.idx + h.ann.excerpt.length
    }
    if (cursor < paragraph.length) {
      out.push({ kind: 'plain', text: paragraph.slice(cursor) })
    }
    return out
  }, [paragraph, annotations])

  return (
    <p className="text-fg leading-relaxed whitespace-pre-wrap">
      {segments.map((s, i) => {
        if (s.kind === 'plain') return <span key={i}>{s.text}</span>
        const colors = issueColorClass(s.ann!.issue_type)
        const issueLabel =
          s.ann!.issue_type === 'good'
            ? 'Điểm tốt'
            : s.ann!.issue_type === 'grammar'
              ? 'Ngữ pháp'
              : 'Từ vựng'
        return (
          <button
            key={i}
            onClick={() => onSelect(s.ann!)}
            aria-label={`${issueLabel}: ${s.text}`}
            className={`${colors.bg} ${colors.text} px-1 rounded cursor-pointer hover:brightness-95`}
          >
            {s.text}
          </button>
        )
      })}
    </p>
  )
}

function AnnotationDetail({
  annotation,
  onClose,
}: {
  annotation: ParagraphAnnotation
  onClose: () => void
}) {
  const colors = issueColorClass(annotation.issue_type)
  return (
    <div className="fixed inset-0 bg-scrim flex items-end sm:items-center justify-center p-4 z-50" onClick={onClose}>
      <div
        className="bg-surface-raised rounded-2xl p-5 max-w-md w-full shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-3">
          <span className={`${colors.bg} ${colors.text} text-xs font-semibold px-2 py-1 rounded`}>
            {annotation.issue_type === 'good'
              ? 'Điểm tốt'
              : annotation.issue_type === 'grammar'
                ? 'Ngữ pháp'
                : 'Từ vựng'}
          </span>
          <button
            onClick={onClose}
            className="w-11 h-11 inline-flex items-center justify-center rounded-full text-muted-fg hover:bg-surface hover:text-fg"
            aria-label="Đóng"
          >
            <svg viewBox="0 0 20 20" className="w-5 h-5" fill="currentColor" aria-hidden>
              <path d="M4.3 4.3l11.4 11.4m0-11.4L4.3 15.7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <p className="text-sm font-mono bg-surface border border-border rounded p-2 mb-3 text-fg">
          "{annotation.excerpt}"
        </p>
        {annotation.issue && (
          <p className="text-sm text-fg mb-2">
            <span className="font-semibold">Vấn đề:</span> {annotation.issue}
          </p>
        )}
        {annotation.suggestion && (
          <p className="text-sm text-fg mb-2">
            <span className="font-semibold">Gợi ý:</span> {annotation.suggestion}
          </p>
        )}
        {annotation.explanation_vi && (
          <p className="text-sm text-fg bg-primary/10 border border-primary/20 rounded p-2">
            {annotation.explanation_vi}
          </p>
        )}
      </div>
    </div>
  )
}

export function AnnotatedEssay({ submission }: { submission: WritingSubmission }) {
  const [selected, setSelected] = useState<ParagraphAnnotation | null>(null)
  const paragraphs = submission.text.split(/\n\s*\n/)

  return (
    <div className="bg-surface-raised rounded-xl shadow-sm p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-fg">Bài viết</h2>
        <span className="text-xs text-muted-fg">{submission.word_count} từ</span>
      </div>
      <div className="space-y-4">
        {paragraphs.map((p, i) => {
          const forPara = submission.paragraph_annotations.filter(
            (a) => a.paragraph_index === i
          )
          return (
            <HighlightedParagraph
              key={i}
              paragraph={p}
              annotations={forPara}
              onSelect={setSelected}
            />
          )
        })}
      </div>
      {selected && (
        <AnnotationDetail annotation={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

export function VietnameseSummary({ summary }: { summary: string }) {
  if (!summary) return null
  return (
    <div className="bg-warning/10 border-l-4 border-warning rounded-xl p-4">
      <h3 className="text-sm font-semibold text-warning mb-1">Tóm tắt cần cải thiện</h3>
      <p className="text-fg text-sm whitespace-pre-line">{summary}</p>
    </div>
  )
}
