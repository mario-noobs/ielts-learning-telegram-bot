import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Standard shadcn-style class combiner.
 *   - `clsx` handles conditional class maps
 *   - `tailwind-merge` resolves conflicting Tailwind utilities
 *     (e.g. `cn('px-2', condition && 'px-4')` → `px-4`)
 *
 * Use this in every primitive under `components/ui/*` so callers can override
 * default classes via `className` without fighting specificity.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
