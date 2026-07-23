import { useState, type ReactNode } from 'react'
import { CalendarIcon, DownloadIcon } from '../icons'
import type { ClientNote } from './notes'

const INITIAL_VISIBLE = 10

/**
 * Month-grouped tap-to-get contract-note list (the selection step). Notes
 * arrive already sorted; we insert a month header when the month changes, cap
 * the initial view at 10 with a "Show more", and each row taps to download.
 * A per-row busy state prevents a double-tap (and is self-clearing).
 */
export function NotesList({
  notes,
  onPick,
}: Readonly<{
  notes: ClientNote[]
  onPick: (note: ClientNote) => void
}>) {
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState<Set<string>>(new Set())

  const visible = expanded ? notes : notes.slice(0, INITIAL_VISIBLE)
  const remaining = notes.length - visible.length

  function tap(note: ClientNote) {
    if (busy.has(note.id)) return
    setBusy((prev) => new Set(prev).add(note.id))
    onPick(note)
    // Self-clearing feedback — the result card appears below regardless.
    setTimeout(() => {
      setBusy((prev) => {
        const next = new Set(prev)
        next.delete(note.id)
        return next
      })
    }, 1500)
  }

  const rows: ReactNode[] = []
  let lastMonth = ''
  for (const note of visible) {
    if (note.month !== lastMonth) {
      lastMonth = note.month
      rows.push(
        <div
          key={`m-${note.month}`}
          className="bg-zinc-50 px-3.5 py-1.5 text-[10.5px] font-bold tracking-[0.07em] text-zinc-400 uppercase dark:bg-zinc-800/60 dark:text-zinc-500"
        >
          {note.month}
        </div>,
      )
    }
    const isBusy = busy.has(note.id)
    rows.push(
      <button
        key={note.id}
        type="button"
        onClick={() => tap(note)}
        className="flex w-full items-center gap-2.5 border-t border-zinc-100 px-3.5 py-2.5 text-left transition-colors hover:bg-accent-tint/60 dark:border-zinc-800 dark:hover:bg-accent/10"
      >
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-semibold text-zinc-900 dark:text-zinc-100">{note.date}</p>
          <p className="mt-0.5 text-[11.5px] text-zinc-400 dark:text-zinc-500">{note.segment}</p>
        </div>
        {note.badge && (
          <span className="shrink-0 rounded-md bg-zinc-100 px-1.5 py-1 text-[10px] font-bold tracking-[0.03em] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
            {note.badge}
          </span>
        )}
        <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-zinc-200 bg-white text-accent dark:border-zinc-700 dark:bg-zinc-900 dark:text-accent-soft">
          {isBusy ? (
            <span className="size-2 animate-pulse rounded-full bg-accent" />
          ) : (
            <DownloadIcon className="size-4" />
          )}
        </span>
      </button>,
    )
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900/60">
      {rows}
      {remaining > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="w-full border-t border-zinc-100 py-2.5 text-center text-[13px] font-semibold text-accent hover:bg-accent-tint/60 dark:border-zinc-800 dark:text-accent-soft dark:hover:bg-accent/10"
        >
          Show more ({remaining} remaining)
        </button>
      )}
    </div>
  )
}

/** Standalone "Change dates" / "Other dates" pill (reused after single-note and
 *  empty/error results). */
export function ChangeDatesButton({
  label = 'Change dates',
  onClick,
}: Readonly<{ label?: string; onClick: () => void }>) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-2 rounded-full border-[1.5px] border-zinc-200 bg-white px-3.5 py-2 text-[13.5px] font-semibold text-zinc-700 hover:border-accent-soft hover:text-accent dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:text-accent-soft"
      >
        <CalendarIcon className="size-4 text-accent dark:text-accent-soft" />
        {label}
      </button>
    </div>
  )
}
