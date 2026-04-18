/**
 * IELTS Coach design-system Tailwind preset.
 *
 * This is the canonical Tailwind theme surface for the M6 design-system package.
 * Consumed via `presets: [dsPreset]` in `web/tailwind.config.js`. Colours, font
 * families, motion durations, and easing curves all resolve to the CSS custom
 * properties declared in `./tokens.css`, so swapping the light/dark token layer
 * cascades automatically without touching any Tailwind class in the app.
 *
 * Do not add new tokens here without mirroring them into `tokens.css` and
 * `tokens.ts`. See `./README.md` for the full contributor contract.
 *
 * Written as `.js` with JSDoc types to match the plain Vite + npm toolchain
 * (no `style-dictionary`, no monorepo). Types are declared in the sibling
 * `tailwind.preset.d.ts`. See ADR-M6-1 for the rationale.
 *
 * @type {Partial<import('tailwindcss').Config>}
 */
const withAlpha = (v) => `rgb(${v} / <alpha-value>)`

const preset = {
  theme: {
    extend: {
      colors: {
        bg: withAlpha('var(--color-bg)'),
        surface: withAlpha('var(--color-surface)'),
        'surface-raised': withAlpha('var(--color-surface-raised)'),
        border: withAlpha('var(--color-border)'),
        fg: withAlpha('var(--color-fg)'),
        'muted-fg': withAlpha('var(--color-muted-fg)'),
        ring: withAlpha('var(--color-ring)'),
        primary: {
          DEFAULT: withAlpha('var(--color-primary)'),
          fg: withAlpha('var(--color-primary-fg)'),
          hover: withAlpha('var(--color-primary-hover)'),
        },
        accent: {
          DEFAULT: withAlpha('var(--color-accent)'),
          fg: withAlpha('var(--color-accent-fg)'),
        },
        success: withAlpha('var(--color-success)'),
        warning: withAlpha('var(--color-warning)'),
        danger: withAlpha('var(--color-danger)'),
      },
      fontFamily: {
        sans: ['"Be Vietnam Pro"', '"Noto Sans"', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontVariantNumeric: {
        tabular: 'tabular-nums',
      },
      transitionDuration: {
        fast: '120ms',
        base: '200ms',
        slow: '320ms',
      },
      transitionTimingFunction: {
        'out-soft': 'cubic-bezier(0.2, 0.8, 0.2, 1)',
      },
    },
  },
}

export default preset
