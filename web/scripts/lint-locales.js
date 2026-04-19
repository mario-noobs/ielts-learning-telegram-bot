#!/usr/bin/env node
/**
 * Locale bundle lint (US-M7.1 AC4).
 *
 * For each namespace, compares the EN and VN bundles and fails with a
 * non-zero exit code on any of:
 *   - missing keys in either bundle (EN is the source-of-truth)
 *   - duplicate keys within a single bundle (JSON duplicate-key check)
 *   - values that are identical placeholders (e.g. empty strings)
 *
 * Run: node scripts/lint-locales.js
 */
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = dirname(HERE)
const LOCALES_DIR = join(ROOT, 'public', 'locales')
const LOCALES = ['en', 'vi']

function flatten(obj, prefix = '') {
  const out = {}
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      Object.assign(out, flatten(v, key))
    } else {
      out[key] = v
    }
  }
  return out
}

function parseDetectingDuplicates(raw, file) {
  // JSON.parse silently overwrites duplicate keys. Detect them by
  // walking the text, tracking brace depth, and collecting keys seen
  // within each currently-open object. When an object closes, check
  // its key list for duplicates.
  const stack = [[]] // one key-array per currently-open object
  const dups = []
  let i = 0
  let inString = false
  let escape = false
  let currentString = ''
  let justExitedString = false
  const n = raw.length

  while (i < n) {
    const c = raw[i]
    if (inString) {
      if (escape) {
        currentString += c
        escape = false
      } else if (c === '\\') {
        currentString += c
        escape = true
      } else if (c === '"') {
        inString = false
        justExitedString = true
      } else {
        currentString += c
      }
      i++
      continue
    }
    if (c === '"') {
      inString = true
      currentString = ''
      i++
      continue
    }
    if (c === '{') {
      stack.push([])
    } else if (c === '}') {
      const keys = stack.pop() || []
      const seen = new Set()
      for (const k of keys) {
        if (seen.has(k)) dups.push(k)
        seen.add(k)
      }
    } else if (c === ':' && justExitedString) {
      stack[stack.length - 1].push(currentString)
    }
    if (!/\s/.test(c)) justExitedString = justExitedString && c !== ':' ? false : justExitedString
    if (c !== ':' && c !== '"' && !/\s/.test(c)) justExitedString = false
    i++
  }

  if (dups.length) {
    throw new Error(`${file}: duplicate JSON keys: ${[...new Set(dups)].join(', ')}`)
  }
  return JSON.parse(raw)
}

const errors = []

if (!existsSync(LOCALES_DIR)) {
  console.error(`locales dir missing: ${LOCALES_DIR}`)
  process.exit(1)
}

const perLocale = {}
for (const lng of LOCALES) {
  const dir = join(LOCALES_DIR, lng)
  if (!existsSync(dir)) {
    errors.push(`locale dir missing: ${lng}`)
    continue
  }
  perLocale[lng] = {}
  for (const entry of readdirSync(dir)) {
    if (!entry.endsWith('.json')) continue
    const ns = entry.slice(0, -5)
    const raw = readFileSync(join(dir, entry), 'utf8')
    try {
      const parsed = parseDetectingDuplicates(raw, `${lng}/${entry}`)
      perLocale[lng][ns] = flatten(parsed)
    } catch (e) {
      errors.push(String(e.message || e))
    }
  }
}

const namespaces = new Set()
for (const lng of LOCALES) {
  for (const ns of Object.keys(perLocale[lng] || {})) namespaces.add(ns)
}

for (const ns of namespaces) {
  const en = perLocale.en?.[ns]
  const vi = perLocale.vi?.[ns]
  if (!en) {
    errors.push(`en/${ns}.json missing`)
    continue
  }
  if (!vi) {
    errors.push(`vi/${ns}.json missing`)
    continue
  }
  const enKeys = new Set(Object.keys(en))
  const viKeys = new Set(Object.keys(vi))
  for (const k of enKeys) {
    if (!viKeys.has(k)) errors.push(`${ns}: vi missing key '${k}'`)
  }
  for (const k of viKeys) {
    if (!enKeys.has(k)) errors.push(`${ns}: en missing key '${k}' (vi has an orphan)`)
  }
  for (const k of enKeys) {
    if (en[k] === '') errors.push(`${ns}: en key '${k}' is empty`)
  }
  for (const k of viKeys) {
    if (vi[k] === '') errors.push(`${ns}: vi key '${k}' is empty`)
  }
}

if (errors.length) {
  console.error(`FAIL: ${errors.length} locale issue(s)`)
  for (const e of errors) console.error(`  - ${e}`)
  process.exit(1)
}

const totals = Object.fromEntries(
  LOCALES.map((l) => [
    l,
    Object.values(perLocale[l] || {}).reduce((n, ns) => n + Object.keys(ns).length, 0),
  ]),
)
console.log(`OK: namespaces=${[...namespaces].sort().join(',')} keys=${JSON.stringify(totals)}`)
