import type { Preview } from '@storybook/react'
import { withThemeByClassName } from '@storybook/addon-themes'

// Loads Tailwind + design tokens (CSS custom properties) from src/index.css.
// The .dark class on <html> is what flips tokens between light and dark mode,
// so the themes addon toggles it on document.documentElement.
import '../src/index.css'

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    backgrounds: {
      // Use the token-driven page background instead of Storybook defaults so
      // components render on the same canvas as the real app.
      default: 'app',
      values: [
        { name: 'app', value: 'rgb(var(--color-bg))' },
        { name: 'surface', value: 'rgb(var(--color-surface))' },
      ],
    },
    a11y: {
      // Surface violations in the addon panel; CI can fail on them later via
      // test-runner if we opt in.
      test: 'todo',
    },
  },
  decorators: [
    withThemeByClassName({
      themes: {
        light: '',
        dark: 'dark',
      },
      defaultTheme: 'light',
      parentSelector: 'html',
    }),
  ],
}

export default preview
