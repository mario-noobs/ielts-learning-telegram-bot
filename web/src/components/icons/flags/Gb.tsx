/** UK flag (Union Jack), simplified for trigger / dropdown rendering. */
interface Props {
  className?: string
}

export default function Gb({ className = '' }: Props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 60 30"
      className={`h-3 w-5 rounded-sm ${className}`}
      aria-hidden="true"
    >
      <clipPath id="gb-clip">
        <rect width="60" height="30" />
      </clipPath>
      <g clipPath="url(#gb-clip)">
        <rect width="60" height="30" fill="#012169" />
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#ffffff" strokeWidth="6" />
        <path
          d="M0,0 L60,30 M60,0 L0,30"
          stroke="#C8102E"
          strokeWidth="4"
          clipPath="polygon(0 0, 30 15, 60 0, 60 30, 30 15, 0 30)"
        />
        <path d="M30,0 v30 M0,15 h60" stroke="#ffffff" strokeWidth="10" />
        <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
      </g>
    </svg>
  )
}
