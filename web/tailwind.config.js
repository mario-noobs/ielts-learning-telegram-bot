/** @type {import('tailwindcss').Config} */
const withAlpha = (v) => `rgb(${v} / <alpha-value>)`

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: 'class',
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
  plugins: [],
}
