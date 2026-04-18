/**
 * TypeScript mirror of the design-system CSS custom properties declared in
 * `./tokens.css`. Kept hand-synced (this is a tiny set) so JS consumers can
 * reference a structured object instead of `getComputedStyle()` gymnastics.
 *
 * Consumers today:
 *  - Illustration commission brief (#125) — palette snapshot for designers.
 *  - Storybook tokens panel (#121) — token inspector controls.
 *
 * Rules:
 *  - Every entry MUST correspond 1:1 with a var in `tokens.css`. When you add
 *    a token there, mirror it here and vice-versa. A visual test or a future
 *    script can enforce parity; for now it's a code-review contract.
 *  - Colour values are stored as the same `R G B` triplets used by the CSS
 *    (so Tailwind's `rgb(... / <alpha-value>)` resolution matches exactly).
 *    Hex equivalents are provided for humans and design tools only.
 */

export type ColorToken = {
  /** Stable token identifier, e.g. `'primary'`. */
  name: string
  /** CSS custom property, including the leading `--`. */
  var: `--${string}`
  /** Light-theme value as `"R G B"` space-separated triplet. */
  light: string
  /** Dark-theme value as `"R G B"` space-separated triplet. */
  dark: string
  /** Light-theme hex, for designers / illustrator briefs. */
  lightHex: string
  /** Dark-theme hex, for designers / illustrator briefs. */
  darkHex: string
  /** Short human description of usage. */
  description: string
}

export type MotionToken = {
  name: string
  var: `--${string}`
  value: string
  description: string
}

const color = {
  primary: {
    name: 'primary',
    var: '--color-primary',
    light: '13 148 136',
    dark: '20 184 166',
    lightHex: '#0D9488',
    darkHex: '#14B8A6',
    description: 'Brand primary — CTAs, focus ring, active states.',
  },
  primaryFg: {
    name: 'primary-fg',
    var: '--color-primary-fg',
    light: '255 255 255',
    dark: '4 47 46',
    lightHex: '#FFFFFF',
    darkHex: '#042F2E',
    description: 'Text on primary surfaces.',
  },
  primaryHover: {
    name: 'primary-hover',
    var: '--color-primary-hover',
    light: '15 118 110',
    dark: '45 212 191',
    lightHex: '#0F766E',
    darkHex: '#2DD4BF',
    description: 'Primary hover / pressed.',
  },
  accent: {
    name: 'accent',
    var: '--color-accent',
    light: '234 88 12',
    dark: '251 146 60',
    lightHex: '#EA580C',
    darkHex: '#FB923C',
    description: 'Streak, exam countdown urgency, highlights.',
  },
  accentFg: {
    name: 'accent-fg',
    var: '--color-accent-fg',
    light: '255 255 255',
    dark: '67 20 7',
    lightHex: '#FFFFFF',
    darkHex: '#431407',
    description: 'Text on accent surfaces.',
  },
  success: {
    name: 'success',
    var: '--color-success',
    light: '21 128 61',
    dark: '34 197 94',
    lightHex: '#15803D',
    darkHex: '#22C55E',
    description: 'Correct, mastered, band ≥ 7.',
  },
  warning: {
    name: 'warning',
    var: '--color-warning',
    light: '180 83 9',
    dark: '245 158 11',
    lightHex: '#B45309',
    darkHex: '#F59E0B',
    description: 'Weak / learning, < 30 days countdown.',
  },
  danger: {
    name: 'danger',
    var: '--color-danger',
    light: '185 28 28',
    dark: '248 113 113',
    lightHex: '#B91C1C',
    darkHex: '#F87171',
    description: 'Incorrect, band < 5, destructive.',
  },
  bg: {
    name: 'bg',
    var: '--color-bg',
    light: '255 255 255',
    dark: '11 18 32',
    lightHex: '#FFFFFF',
    darkHex: '#0B1220',
    description: 'Page background.',
  },
  surface: {
    name: 'surface',
    var: '--color-surface',
    light: '248 250 252',
    dark: '17 24 39',
    lightHex: '#F8FAFC',
    darkHex: '#111827',
    description: 'Cards, sheets.',
  },
  surfaceRaised: {
    name: 'surface-raised',
    var: '--color-surface-raised',
    light: '255 255 255',
    dark: '31 41 55',
    lightHex: '#FFFFFF',
    darkHex: '#1F2937',
    description: 'Elevated cards, modals.',
  },
  border: {
    name: 'border',
    var: '--color-border',
    light: '226 232 240',
    dark: '31 41 55',
    lightHex: '#E2E8F0',
    darkHex: '#1F2937',
    description: 'Dividers, card borders.',
  },
  fg: {
    name: 'fg',
    var: '--color-fg',
    light: '15 23 42',
    dark: '241 245 249',
    lightHex: '#0F172A',
    darkHex: '#F1F5F9',
    description: 'Body text, headings.',
  },
  mutedFg: {
    name: 'muted-fg',
    var: '--color-muted-fg',
    light: '71 85 105',
    dark: '148 163 184',
    lightHex: '#475569',
    darkHex: '#94A3B8',
    description: 'Secondary text, captions.',
  },
  ring: {
    name: 'ring',
    var: '--color-ring',
    light: '13 148 136',
    dark: '20 184 166',
    lightHex: '#0D9488',
    darkHex: '#14B8A6',
    description: 'Keyboard focus indicator.',
  },
} as const satisfies Record<string, ColorToken>

const motion = {
  durFast: {
    name: 'dur-fast',
    var: '--dur-fast',
    value: '120ms',
    description: 'Press feedback, tap scale.',
  },
  durBase: {
    name: 'dur-base',
    var: '--dur-base',
    value: '200ms',
    description: 'Colour / opacity transitions, hover.',
  },
  durSlow: {
    name: 'dur-slow',
    var: '--dur-slow',
    value: '320ms',
    description: 'Ring stroke fill, skeleton fade-out.',
  },
  easeOut: {
    name: 'ease-out',
    var: '--ease-out',
    value: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
    description: 'Default enter curve.',
  },
  easeInOut: {
    name: 'ease-in-out',
    var: '--ease-in-out',
    value: 'cubic-bezier(0.4, 0, 0.2, 1)',
    description: 'Ring fills, sheet motion.',
  },
} as const satisfies Record<string, MotionToken>

export const tokens = { color, motion } as const

export type Token = ColorToken | MotionToken
export type ColorTokenName = (typeof color)[keyof typeof color]['name']
export type MotionTokenName = (typeof motion)[keyof typeof motion]['name']
export type TokenName = ColorTokenName | MotionTokenName
