import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

/**
 * Matches 3, 4, 6, or 8-digit hex colour literals (e.g. "#0D9488", "#fff",
 * "#0000ffcc"). Anchored to string start/end so "abc#def" isn't flagged while
 * "#0D9488" (a colour) is. Used by the no-restricted-syntax rule below to block
 * raw hex colours in UI source — consumers must go through design-system tokens
 * (see src/design-system/README.md). Gate is per M6.1; reskin relies on this.
 */
const HEX_COLOR_LITERAL = /^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/

const HEX_COLOR_RULES = {
  'no-restricted-syntax': [
    'error',
    {
      selector: `Literal[value=/${HEX_COLOR_LITERAL.source}/]`,
      message:
        'Raw hex colour literals are not allowed. Use a design-system token via Tailwind (e.g. `text-primary`, `bg-surface`) or `tokens` from `@/design-system`. See src/design-system/README.md.',
    },
    {
      selector: `TemplateElement[value.raw=/${HEX_COLOR_LITERAL.source}/]`,
      message:
        'Raw hex colour literals are not allowed in template strings. Use a design-system token. See src/design-system/README.md.',
    },
  ],
}

export default tseslint.config(
  { ignores: ['dist', 'storybook-static', 'coverage'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
  {
    // M6.1 design-system guard, now strict after US-M6.5 (#124) finished the
    // reskin. Every SVG chart component that was previously grandfathered
    // (BandRing, BandTrendChart, ProgressRing, TaskVisualization,
    // WritingHistoryPage trend SVG) has been migrated to token-consuming
    // utilities via `currentColor` / Tailwind `stroke-*` / `fill-*` classes.
    // `tokens.ts` legitimately lists hex values and is outside this `files`
    // scope, so no per-file allowlist is required.
    files: ['src/pages/**/*.{ts,tsx}', 'src/components/**/*.{ts,tsx}'],
    rules: HEX_COLOR_RULES,
  },
)
