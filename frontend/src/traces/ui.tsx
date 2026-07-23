/** Shared presentational primitives for the trace viewer. */

import type { ReactNode } from 'react'

export function Spinner() {
  return (
    <span
      aria-label="loading"
      className="inline-block size-4 animate-spin rounded-full border-2 border-zinc-300 border-t-accent dark:border-zinc-600 dark:border-t-accent-soft"
    />
  )
}

export function Empty({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="grid place-items-center rounded-xl border border-dashed border-zinc-200 p-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
      {children}
    </div>
  )
}

export function ErrorNote({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="rounded-lg border border-alert/30 bg-alert/5 px-3 py-2 text-sm text-alert dark:border-alert/40">
      {children}
    </div>
  )
}

const TYPE_STYLES: Record<string, string> = {
  agent: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  llm: 'bg-accent-tint text-accent-strong dark:bg-accent/20 dark:text-accent-soft',
  tool: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  retriever:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
}

export function TypePill({ type }: Readonly<{ type: string }>) {
  const cls =
    TYPE_STYLES[type] ??
    'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300'
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase ${cls}`}
    >
      {type}
    </span>
  )
}

export function ErrorBadge() {
  return (
    <span className="rounded bg-alert/10 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-alert uppercase">
      error
    </span>
  )
}

export function Chip({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
      {children}
    </span>
  )
}

export function Pager({
  offset,
  limit,
  total,
  onPrev,
  onNext,
}: Readonly<{
  offset: number
  limit: number
  total: number
  onPrev: () => void
  onNext: () => void
}>) {
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + limit, total)
  const btn =
    'rounded-md border border-zinc-200 px-2.5 py-1 font-medium text-zinc-600 enabled:hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-300 dark:enabled:hover:bg-zinc-800'
  return (
    <div className="flex items-center justify-between gap-3 text-xs text-zinc-500 dark:text-zinc-400">
      <span>
        {from}–{to} of {total}
      </span>
      <div className="flex gap-1">
        <button type="button" disabled={offset === 0} onClick={onPrev} className={btn}>
          Prev
        </button>
        <button type="button" disabled={to >= total} onClick={onNext} className={btn}>
          Next
        </button>
      </div>
    </div>
  )
}
