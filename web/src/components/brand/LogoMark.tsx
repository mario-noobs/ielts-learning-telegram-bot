/**
 * IELTS Coach logo mark — inlined SVG (themeable, no HTTP).
 *
 * Use `<LogoMark />` in headers/footers; pair with the wordmark text
 * "IELTS Coach" beside it on lg screens. Sizes follow Tailwind's
 * size scale (sm = 24px, md = 32px, lg = 48px).
 *
 * The outer rounded square uses `currentColor` so the mark inherits
 * the parent's text color (e.g., `text-primary` in the header,
 * `text-muted-fg` in a disabled-ish footer). Inner glyph stays white
 * for contrast against any colored background.
 */

interface Props {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  ariaLabel?: string
}

const SIZE_PX: Record<NonNullable<Props['size']>, number> = {
  sm: 24,
  md: 32,
  lg: 48,
}

export default function LogoMark({
  size = 'md',
  className = '',
  ariaLabel = 'IELTS Coach',
}: Props) {
  const px = SIZE_PX[size]
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={px}
      height={px}
      role="img"
      aria-label={ariaLabel}
      className={`text-primary ${className}`}
    >
      <rect x="0" y="0" width="64" height="64" rx="14" fill="currentColor" />
      <rect
        x="14"
        y="20"
        width="36"
        height="4"
        rx="2"
        fill="#ffffff"
        fillOpacity="0.95"
      />
      <rect
        x="14"
        y="30"
        width="28"
        height="4"
        rx="2"
        fill="#ffffff"
        fillOpacity="0.85"
      />
      <rect
        x="14"
        y="40"
        width="20"
        height="4"
        rx="2"
        fill="#ffffff"
        fillOpacity="0.75"
      />
      <circle cx="46" cy="44" r="4" fill="#ffffff" />
    </svg>
  )
}
