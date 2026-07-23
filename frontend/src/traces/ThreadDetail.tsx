/** Right pane of the Threads view: a thread's turns in order, its token trend
 * (context-rot gauge), and each turn expandable to its span tree. */

import { useEffect, useState } from 'react'
import type { TraceDetail } from './api'
import { getThread } from './api'
import { fmtDateTime, fmtInt, fmtMs } from './format'
import { SpanTree } from './SpanTree'
import { TokenTrend } from './TokenTrend'
import { Chip, Empty, ErrorBadge, ErrorNote, Spinner } from './ui'

export function ThreadDetail({
  token,
  threadId,
  onError,
  onOpenTrace,
}: Readonly<{
  token: string
  threadId: string
  onError: (e: unknown) => void
  onOpenTrace: (id: number) => void
}>) {
  const [turns, setTurns] = useState<TraceDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    setLoading(true)
    setFailed(false)
    getThread(token, threadId)
      .then((res) => {
        if (live) setTurns(res.traces)
      })
      .catch((e) => {
        if (!live) return
        setFailed(true)
        onError(e)
      })
      .finally(() => {
        if (live) setLoading(false)
      })
    return () => {
      live = false
    }
  }, [token, threadId, onError])

  const totalIn = turns.reduce((sum, t) => sum + (t.input_tokens ?? 0), 0)
  const anyError = turns.some((t) => t.had_error)

  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">
          Thread
        </h2>
        <span className="truncate font-mono text-xs text-zinc-500 dark:text-zinc-400">
          {threadId}
        </span>
        {anyError && <ErrorBadge />}
        {loading && <Spinner />}
      </div>

      {failed && <ErrorNote>Could not load this thread.</ErrorNote>}

      {!failed && !loading && turns.length === 0 && (
        <div className="mt-3">
          <Empty>This thread has no turns.</Empty>
        </div>
      )}

      {turns.length > 0 && (
        <div className="mt-3 space-y-4">
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-500 dark:text-zinc-400">
            <Chip>{fmtInt(turns.length)} turns</Chip>
            <Chip>{fmtInt(totalIn)} input tokens</Chip>
          </div>

          <TokenTrend traces={turns} onSelect={onOpenTrace} />

          <ul className="space-y-2">
            {turns.map((turn, i) => (
              <Turn
                key={turn.id}
                index={i + 1}
                turn={turn}
                onOpen={() => onOpenTrace(turn.id)}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function Turn({
  index,
  turn,
  onOpen,
}: Readonly<{ index: number; turn: TraceDetail; onOpen: () => void }>) {
  const [open, setOpen] = useState(false)
  return (
    <li className="rounded-lg border border-zinc-200 dark:border-zinc-800">
      <div className="flex items-center gap-2 p-2.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          <span className="w-3 shrink-0 text-[10px] text-zinc-400">
            {open ? '▾' : '▸'}
          </span>
          <span className="shrink-0 text-xs font-semibold text-zinc-500 tabular-nums dark:text-zinc-400">
            #{index}
          </span>
          <span className="truncate text-sm text-zinc-800 dark:text-zinc-100">
            {turn.input || <span className="text-zinc-400">(no input)</span>}
          </span>
          {turn.had_error && <ErrorBadge />}
        </button>
        <div className="flex shrink-0 items-center gap-1.5 text-[11px] text-zinc-400">
          <span className="tabular-nums">{fmtInt(turn.input_tokens)} tok</span>
          <span className="tabular-nums">{fmtMs(turn.latency_ms)}</span>
          <button
            type="button"
            onClick={onOpen}
            title="Open full trace"
            className="rounded px-1 text-accent-strong hover:underline dark:text-accent-soft"
          >
            #{turn.id} ↗
          </button>
        </div>
      </div>

      {open && (
        <div className="border-t border-zinc-100 p-2.5 dark:border-zinc-800">
          <div className="mb-2 text-[11px] text-zinc-400">
            {fmtDateTime(turn.created_at)}
            {turn.model ? ` · ${turn.model}` : ''}
          </div>
          {turn.output && (
            <p className="mb-2 rounded-md bg-zinc-50 p-2 text-sm whitespace-pre-wrap text-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-200">
              {turn.output}
            </p>
          )}
          <SpanTree spans={turn.spans} />
        </div>
      )}
    </li>
  )
}
