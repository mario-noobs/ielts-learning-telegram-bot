import Gb from './icons/flags/Gb'
import Vn from './icons/flags/Vn'

/** Flag wrapper for the supported locales. Decorative — `aria-hidden`
 *  on the SVG itself; pair with adjacent text for screen-reader label. */

interface Props {
  code: 'en' | 'vi'
  className?: string
}

export default function Flag({ code, className = '' }: Props) {
  if (code === 'en') return <Gb className={className} />
  return <Vn className={className} />
}
