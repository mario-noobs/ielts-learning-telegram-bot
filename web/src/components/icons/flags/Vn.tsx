/** Vietnam flag — red field with central yellow 5-pointed star. */
interface Props {
  className?: string
}

export default function Vn({ className = '' }: Props) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 60 40"
      className={`h-3 w-5 rounded-sm ${className}`}
      aria-hidden="true"
    >
      <rect width="60" height="40" fill="#DA251D" />
      <polygon
        points="30,8 33.5,18.5 44.5,18.5 35.5,25 39,35.5 30,29 21,35.5 24.5,25 15.5,18.5 26.5,18.5"
        fill="#FFFF00"
      />
    </svg>
  )
}
