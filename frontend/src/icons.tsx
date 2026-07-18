import type { SVGProps } from 'react'

type IconProps = Readonly<SVGProps<SVGSVGElement>>

function StrokeIcon({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  )
}

export function BackIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="m15 18-6-6 6-6" />
    </StrokeIcon>
  )
}

/** Four-point sparkle used in the Choice Jini logo mark. */
export function SparkleIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" {...props}>
      <path d="M12 2.6c.96 4.9 3.6 7.55 8.5 8.5-4.9.96-7.54 3.6-8.5 8.5-.96-4.9-3.6-7.54-8.5-8.5 4.9-.95 7.54-3.6 8.5-8.5Z" />
      <path d="M19 15.4c.42 2.16 1.58 3.32 3.74 3.75-2.16.42-3.32 1.58-3.74 3.74-.43-2.16-1.59-3.32-3.75-3.74 2.16-.43 3.32-1.59 3.75-3.75Z" opacity={0.85} />
    </svg>
  )
}

export function TrendingUpIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M22 7 13.5 15.5 8.5 10.5 2 17" />
      <path d="M16 7h6v6" />
    </StrokeIcon>
  )
}

export function LedgerIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
    </StrokeIcon>
  )
}

export function DocumentIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
    </StrokeIcon>
  )
}

export function TicketIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" />
      <path d="M13 5v2" />
      <path d="M13 11v2" />
      <path d="M13 17v2" />
    </StrokeIcon>
  )
}

export function PercentIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M19 5 5 19" />
      <circle cx="6.5" cy="6.5" r="2.5" />
      <circle cx="17.5" cy="17.5" r="2.5" />
    </StrokeIcon>
  )
}

export function XIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </StrokeIcon>
  )
}

export function ArrowUpIcon(props: IconProps) {
  return (
    <StrokeIcon strokeWidth={2.4} {...props}>
      <path d="M12 19V5" />
      <path d="m5 12 7-7 7 7" />
    </StrokeIcon>
  )
}
