# Design System — `src/design-system`

This is the **M6 design-token package** (US-M6.1 / [#120](https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/120)). It formalises the token surface first shipped in UX-1 ([milestone #7](https://github.com/mario-noobs/ielts-learning-telegram-bot/milestone/7)) so that M7 i18n, M9 Reading Lab, and any future milestone can consume a single stable contract.

**No visual changes were introduced by this package** — it is a refactor, not a redesign. The visual reskin is tracked separately as [#124](https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/124).

## What's here

| File | Purpose |
|------|---------|
| [`tokens.css`](./tokens.css) | **Source of truth.** CSS custom properties for colour, motion, dark mode, and reduced-motion. Imported once from `src/index.css`. |
| [`tailwind.preset.js`](./tailwind.preset.js) | Tailwind preset that maps `bg-primary`, `text-fg`, `duration-base`, etc. onto the CSS vars via `rgb(var(--token) / <alpha-value>)`. |
| [`tailwind.preset.d.ts`](./tailwind.preset.d.ts) | TS type declaration for the preset. |
| [`tokens.ts`](./tokens.ts) | Declarative JS/TS mirror of the CSS vars — for tooling (illustration brief [#125](https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/125), Storybook [#121](https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/121)) that needs a structured object. |
| [`index.ts`](./index.ts) | Public barrel: `tailwindPreset`, `tokens`, and TS types. |

## How to consume tokens in a component

**Always** go through Tailwind utilities. Never use raw hex or raw `var(--color-...)` inline.

```tsx
// Good
<button className="bg-primary text-primary-fg hover:bg-primary-hover">…</button>
<p className="text-muted-fg">Caption</p>

// Bad — do not do this
<button style={{ backgroundColor: '#0D9488' }}>…</button>
<button className="bg-[#0D9488]">…</button>
```

The ESLint `no-restricted-syntax` rule under `web/eslint.config.js` flags raw hex literals in `src/pages/**` and `src/components/**` so reskin ([#124](https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/124)) cannot regress this.

For JS-side access (e.g. SVG chart series colours, illustration briefs), import the `tokens` object:

```ts
import { tokens } from '@/design-system'
const brief = tokens.color.primary.lightHex // "#0D9488"
```

## Contrast & accessibility

All tokens shipped here were verified **WCAG AA** in the UX-1 audit:

- `fg` on `bg` = 16.5:1
- `muted-fg` on `bg` = 7.3:1
- `primary` on `bg` = 4.8:1
- `primary-fg` on `primary` = 6.1:1
- `success` / `danger` on `bg` ≥ 4.5:1

Full table and contrast notes: [`web/DESIGN_SPECS.md`](../../DESIGN_SPECS.md). Master page-level spec: [`web/design-system/ielts-coach/MASTER.md`](../../design-system/ielts-coach/MASTER.md).

## Dark mode status

The **token layer supports dark mode** (every colour token has a `.dark` override in `tokens.css`). The dark visual design pass — component-level polish, illustration palette, dark-mode screenshots in review checklist — is **M6 v2**, tracked under Epic [#92](https://github.com/mario-noobs/ielts-learning-telegram-bot/issues/92). Until then, dark mode renders but is not visually signed off.

## Adding or changing a token

1. Edit `tokens.css` (both `:root` and `.dark`).
2. Mirror the change in `tokens.ts` (add to the `color` or `motion` object with matching `name`, `var`, values, and hex equivalents).
3. If the new token needs a Tailwind utility, add it to `tailwind.preset.js`.
4. Update `web/DESIGN_SPECS.md` locked-tokens table.
5. Verify contrast and screenshot both themes in the PR.

Do **not** rename existing token variables — that's a breaking change for every consumer.
