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

export function RefreshIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M3 21v-5h5" />
    </StrokeIcon>
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

/** Capital-gains statement glyph (torn-edge receipt). */
export function ReceiptIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M5 2v20l2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1z" />
      <path d="M9 7h6" />
      <path d="M9 11h6" />
      <path d="M9 15h4" />
    </StrokeIcon>
  )
}

export function CalendarIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4" />
      <path d="M8 2v4" />
      <path d="M3 10h18" />
    </StrokeIcon>
  )
}

export function MailIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-10 6L2 7" />
    </StrokeIcon>
  )
}

export function DownloadIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="M7 10l5 5 5-5" />
      <path d="M12 15V3" />
    </StrokeIcon>
  )
}

export function CheckIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M20 6 9 17l-5-5" />
    </StrokeIcon>
  )
}

/** Pie-chart glyph — the holdings data-card sticker. */
export function PieIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
      <path d="M22 12A10 10 0 0 0 12 2v10z" />
    </StrokeIcon>
  )
}

/** Opposing arrows — the pay in / out sticker (Wave B). */
export function SwapIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M7 5v14" />
      <path d="M4 16l3 3 3-3" />
      <path d="M17 19V5" />
      <path d="M14 8l3-3 3 3" />
    </StrokeIcon>
  )
}

/** Price-tag glyph — the brokerage sticker (Wave B). */
export function TagIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
      <path d="M7 7h.01" />
    </StrokeIcon>
  )
}

/** Left/right chevrons for the calendar month nav. */
export function ChevronLeftIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="m15 18-6-6 6-6" />
    </StrokeIcon>
  )
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="m9 18 6-6-6-6" />
    </StrokeIcon>
  )
}

/** Feedback thumbs (CHO-217) — pass fill="currentColor" for the selected state. */
export function ThumbUpIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M7 10v12" />
      <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
    </StrokeIcon>
  )
}

export function ThumbDownIcon(props: IconProps) {
  return (
    <StrokeIcon {...props}>
      <path d="M17 14V2" />
      <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
    </StrokeIcon>
  )
}
