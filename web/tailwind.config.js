import dsPreset from './src/design-system/tailwind.preset.js'

/** @type {import('tailwindcss').Config} */
export default {
  presets: [dsPreset],
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
    // The design-system package's `tokens.ts` lists token names like
    // `"accent-fg"` and `"ring"` as string literals for tooling. Tailwind's
    // JIT would otherwise treat those strings as class names and emit stray
    // utilities into the bundle. Excluding the file keeps M6.1 a true
    // byte-for-byte refactor vs. the UX-1 baseline.
    '!./src/design-system/tokens.ts',
  ],
  darkMode: 'class',
  plugins: [],
}
