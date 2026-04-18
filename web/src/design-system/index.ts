/**
 * IELTS Coach design-system — public surface.
 *
 * Single entry point for the in-repo design-token package shipped in M6
 * (US-M6.1 / issue #120). Future milestones (M7 i18n, M9 Reading Lab, etc.)
 * should import from `@/design-system` and never reach into `./tokens.css`
 * or `./tailwind.preset.js` directly.
 */

export { default as tailwindPreset } from './tailwind.preset.js'
export { tokens } from './tokens'
export type {
  ColorToken,
  MotionToken,
  Token,
  TokenName,
  ColorTokenName,
  MotionTokenName,
} from './tokens'
