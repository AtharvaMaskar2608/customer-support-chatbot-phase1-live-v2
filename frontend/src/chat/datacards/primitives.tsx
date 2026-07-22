/**
 * Data-card primitives (data-card-system) — the shared card language all
 * three data cards build on: hero fact + qualifying context, animated reveal
 * (count-up / bar-grow), expandable rows with depth on tap, count-chips that
 * double as filters, show-more, and the quiet footer. Holdings composes these
 * now; Money and Brokerage (Wave B) reuse them unchanged.
 *
 * Visual source of truth: docs/prototype/report-flow-prototype.html
 * (.hcard/.mcard/.bcard). Color discipline: success is quiet, exceptions
 * carry the color; the dark theme uses the app's soft variants for legibility.
 */

import { useEffect, useState, type ReactNode } from 'react'
import { RefreshIcon } from '../../icons'
import { DOWN_TEXT, UP_TEXT } from './tokens'
import { useCountUp } from './useCountUp'

/* ── frame ────────────────────────────────────────────────────────────── */

/** The zero-padding card shell — sections own their padding (hero, rows,
 *  footer), so full-bleed row hovers and border-top separators line up. */
export function DataCardFrame({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900/60 dark:text-zinc-100">
      {children}
    </div>
  )
}

/* ── hero block ───────────────────────────────────────────────────────── */

/** The small uppercase card label, e.g. "PORTFOLIO VALUE · 10 HOLDINGS". */
export function HeroLabel({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="text-[10.5px] font-bold tracking-[0.07em] text-zinc-400 uppercase dark:text-zinc-500">
      {children}
    </div>
  )
}

/** The hero number — counts up to `value`, formatted by `format`
 *  (paise dropped during the count: the reveal rounds to whole rupees). */
export function CountUpValue({
  value,
  format,
}: Readonly<{ value: number; format: (n: number) => string }>) {
  const shown = useCountUp(Math.round(value))
  return (
    <div className="mt-[3px] mb-px text-[31px] leading-[1.05] font-extrabold tracking-[-0.02em] tabular-nums">
      {format(shown)}
    </div>
  )
}

/** Stat pill (1D / Overall …): tinted green when up, red when down,
 *  neutral gray otherwise. Children carry the ▴/▾ + amount + %. */
const PILL_TONE = {
  up: `bg-online/[.13] ${UP_TEXT}`,
  down: `bg-alert/[.13] ${DOWN_TEXT}`,
  neutral: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
} as const

export function StatPill({
  label,
  tone,
  children,
}: Readonly<{ label: string; tone: 'up' | 'down' | 'neutral'; children: ReactNode }>) {
  const toneClass = PILL_TONE[tone]
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-[10px] px-[11px] py-[7px] text-[12.5px] font-bold tabular-nums ${toneClass}`}
    >
      <span className="text-[10px] font-extrabold tracking-[0.05em] uppercase opacity-70">
        {label}
      </span>
      {children}
    </div>
  )
}

/** Freshness line: a deliberately-gray dot (NOT the green "online" dot) +
 *  time-honest copy like "Prices as of 17 Jul, 3:59 pm — last fetch, not live". */
export function FreshnessLine({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-zinc-400 dark:text-zinc-500">
      <span className="size-[7px] shrink-0 rounded-full bg-zinc-400/60 dark:bg-zinc-500/60" />
      <span>{children}</span>
    </div>
  )
}

/* ── allocation bar ───────────────────────────────────────────────────── */

export interface AllocationSegment {
  /** Tooltip label, e.g. "BANKBARODA" or "Other (5)". */
  label: string
  /** Segment share, 0–100. */
  pct: number
  /** CSS color for a ranked segment… */
  color?: string
  /** …or theme-aware classes (the gray "Other" lump). */
  className?: string
}

/** Horizontal allocation bar; segments grow from 0 to their widths on mount
 *  (one-shot, ~620ms ease-out — the reveal is earned, not dumped). */
export function AllocationBar({ segments }: Readonly<{ segments: AllocationSegment[] }>) {
  const [grown, setGrown] = useState(false)
  useEffect(() => {
    // Double rAF: let the 0-width state paint before transitioning.
    let raf2 = 0
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => setGrown(true))
    })
    return () => {
      cancelAnimationFrame(raf1)
      cancelAnimationFrame(raf2)
    }
  }, [])
  return (
    <div className="mx-4 flex h-[9px] gap-0.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
      {segments.map((s) => (
        <div
          key={s.label}
          title={`${s.label} · ${s.pct.toFixed(1)}%`}
          className={`h-full flex-none rounded-[2px] transition-[width] duration-[620ms] ease-[cubic-bezier(.22,1,.36,1)] ${s.className ?? ''}`}
          style={{ width: grown ? `${s.pct}%` : 0, ...(s.color ? { background: s.color } : {}) }}
        />
      ))}
    </div>
  )
}

/* ── list rows ────────────────────────────────────────────────────────── */

/**
 * Expandable row: tap toggles an inline detail area (depth on demand).
 * `dim` mutes rows for things that did not happen (failed/cancelled — the
 * color-discipline rule Money relies on).
 */
export function ExpandableRow({
  row,
  detail,
  dim = false,
}: Readonly<{ row: ReactNode; detail: ReactNode; dim?: boolean }>) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-t border-zinc-100 dark:border-zinc-800">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={`flex w-full items-center justify-between gap-2.5 px-4 py-[11px] text-left transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800 ${dim ? 'opacity-[.68]' : ''}`}
      >
        {row}
      </button>
      {open && detail}
    </div>
  )
}

/** The expanded detail area: a 2-column key/value grid on the track tint. */
export function DetailGrid({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="grid grid-cols-2 gap-x-3.5 gap-y-[9px] bg-zinc-100 px-4 pt-1 pb-[13px] dark:bg-zinc-800">
      {children}
    </div>
  )
}

/** One detail cell. `wide` spans both columns (e.g. a verbatim "Why" reason);
 *  `className` colors the value (UP_TEXT / DOWN_TEXT). */
export function DetailCell({
  k,
  wide = false,
  className,
  children,
}: Readonly<{ k: string; wide?: boolean; className?: string; children: ReactNode }>) {
  return (
    <div className={wide ? 'col-span-2' : undefined}>
      <div className="text-[10.5px] font-semibold tracking-[0.04em] text-zinc-400 uppercase dark:text-zinc-500">
        {k}
      </div>
      <div
        className={`mt-px text-[12.5px] ${wide ? 'leading-[1.45] font-medium' : 'font-bold tabular-nums'} ${className ?? ''}`}
      >
        {children}
      </div>
    </div>
  )
}

/* ── chips, show-more, footer ─────────────────────────────────────────── */

/**
 * Count-chip that doubles as a filter: dot + count + label; `active` shows
 * the pressed state (tap again clears). Callers must not render zero-count
 * chips — a zero is noise, not a filter.
 */
export function CountChip({
  count,
  label,
  dotClass,
  active,
  onClick,
}: Readonly<{
  count: number
  label: string
  dotClass: string
  active: boolean
  onClick: () => void
}>) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={[
        'inline-flex items-center gap-1.5 rounded-full border-[1.5px] px-[11px] py-[5px] text-[11.5px] font-bold transition-colors',
        active
          ? 'border-zinc-400 bg-zinc-100 text-zinc-900 dark:border-zinc-500 dark:bg-zinc-800 dark:text-zinc-100'
          : 'border-zinc-200 bg-white text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400',
      ].join(' ')}
    >
      <span className={`size-[7px] shrink-0 rounded-full ${dotClass}`} />
      {count} {label}
    </button>
  )
}

/** Centered "Show all n …" row. */
export function ShowMoreRow({ label, onClick }: Readonly<{ label: string; onClick: () => void }>) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full border-t border-zinc-100 py-[11px] text-center text-[13px] font-semibold text-accent transition-colors hover:bg-accent-tint dark:border-zinc-800 dark:text-accent-soft dark:hover:bg-accent/15"
    >
      {label}
    </button>
  )
}

/** Quiet card footer — at most one secondary action lives here, never the hero. */
export function CardFooter({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="flex items-center justify-between gap-3 border-t border-zinc-100 px-4 py-2.5 dark:border-zinc-800">
      {children}
    </div>
  )
}

/** Calm empty-state line inside the card frame ("No holdings in your demat yet"). */
export function EmptyCardLine({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="px-4 py-[18px] text-center text-[13px] text-zinc-400 dark:text-zinc-500">
      {children}
    </div>
  )
}

/** Follow-up under a data card: plain text · accent help link, plus an
 *  optional "Refresh prices" action (CHO-248) that re-runs the flow and
 *  appends a fresh card below as a continuation. */
export function DataFollowup({
  text,
  linkLabel,
  onClick,
  onRefresh,
}: Readonly<{ text: string; linkLabel: string; onClick: () => void; onRefresh?: () => void }>) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-[13px] text-zinc-500 dark:text-zinc-400">
        {text} ·{' '}
        <button
          type="button"
          onClick={onClick}
          className="font-semibold text-accent dark:text-accent-soft"
        >
          {linkLabel}
        </button>
      </p>
      {onRefresh && (
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex w-fit items-center gap-1.5 rounded-full border-[1.5px] border-zinc-200 bg-white px-3.5 py-1.5 text-[13px] font-semibold text-accent transition-colors hover:border-accent-soft hover:bg-accent-tint dark:border-zinc-700 dark:bg-zinc-900 dark:text-accent-soft dark:hover:bg-accent/15"
        >
          <RefreshIcon className="size-4" /> Refresh prices
        </button>
      )}
    </div>
  )
}
