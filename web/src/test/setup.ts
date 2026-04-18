import '@testing-library/jest-dom/vitest'

// Radix animates some primitives (Dialog, Toast) which jsdom doesn't actually
// render; silence the "not implemented: HTMLMediaElement.prototype.play"-ish
// noise by stubbing what we need per-suite. Nothing global here yet.
