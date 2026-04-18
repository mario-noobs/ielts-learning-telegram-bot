// Backwards-compatible re-export so existing imports
// (`import ProgressRing from '../components/ProgressRing'`) keep working after
// the primitive moved to `components/ui/ProgressRing.tsx` in #121.
// New code should import from `components/ui` directly.
export { default } from './ui/ProgressRing'
