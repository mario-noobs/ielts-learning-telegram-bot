import { diffWords } from '../lib/diff'

export default function WritingDiff({
  original,
  revised,
}: {
  original: string
  revised: string
}) {
  const parts = diffWords(original, revised)
  return (
    <div className="bg-surface-raised rounded-xl shadow-sm p-5">
      <h3 className="font-semibold text-fg mb-3">So sánh bài viết</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-xs uppercase tracking-wide text-muted-fg mb-1">Bản gốc</div>
          <div className="leading-relaxed whitespace-pre-wrap text-fg">
            {parts
              .filter((p) => p.kind !== 'add')
              .map((p, i) => (
                <span
                  key={i}
                  className={
                    p.kind === 'del' ? 'bg-danger/20 text-danger rounded px-0.5' : ''
                  }
                >
                  {p.text}
                </span>
              ))}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-muted-fg mb-1">Bản sửa</div>
          <div className="leading-relaxed whitespace-pre-wrap text-fg">
            {parts
              .filter((p) => p.kind !== 'del')
              .map((p, i) => (
                <span
                  key={i}
                  className={
                    p.kind === 'add' ? 'bg-success/20 text-success rounded px-0.5' : ''
                  }
                >
                  {p.text}
                </span>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}
