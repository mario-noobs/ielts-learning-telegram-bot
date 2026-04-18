export type DiffPart = { kind: 'same' | 'add' | 'del'; text: string }

export function diffWords(a: string, b: string): DiffPart[] {
  const aw = a.split(/(\s+)/)
  const bw = b.split(/(\s+)/)
  const m = aw.length
  const n = bw.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = aw[i] === bw[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const out: DiffPart[] = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (aw[i] === bw[j]) {
      out.push({ kind: 'same', text: aw[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ kind: 'del', text: aw[i] })
      i++
    } else {
      out.push({ kind: 'add', text: bw[j] })
      j++
    }
  }
  while (i < m) {
    out.push({ kind: 'del', text: aw[i++] })
  }
  while (j < n) {
    out.push({ kind: 'add', text: bw[j++] })
  }
  return out
}
