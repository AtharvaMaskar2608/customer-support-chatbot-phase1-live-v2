/** Right pane of the Traces view: one trace's rollup, masked input/output, and
 * its full span tree. */

import { useEffect, useState } from 'react'
import type { TraceDetail as Trace } from './api'
import { getTrace } from './api'
import { fmtDateTime, fmtInt, fmtMs } from './format'
import { SpanTree } from './SpanTree'
import { Chip, ErrorBadge, ErrorNote, Spinner } from './ui'

export function TraceDetail({
  token,
  id,
  onError,
  onOpenThread,
}: Readonly<{
  token: string
  id: number
  onError: (e: unknown) => void
  onOpenThread: (threadId: string) => void
}>) {
  const [trace, setTrace] = useState<Trace | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    setLoading(true)
    setFailed(false)
    setTrace(null)
    getTrace(token, id)
      .then((res) => {
        if (live) setTrace(res)
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
  }, [token, id, onError])

  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">
          Trace <span className="font-mono text-zinc-400">#{id}</span>
        </h2>
        {loading && <Spinner />}
      </div>

      {failed && <ErrorNote>Could not load this trace.</ErrorNote>}

      {trace && (
        <div className="mt-3 space-y-4">
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-zinc-500 dark:text-zinc-400">
            <span>{fmtDateTime(trace.created_at)}</span>
            {trace.had_error && <ErrorBadge />}
            {trace.model && <Chip>{trace.model}</Chip>}
            <Chip>{fmtMs(trace.latency_ms)}</Chip>
            <Chip>
              {fmtInt(trace.input_tokens)}→{fmtInt(trace.output_tokens)} tok
            </Chip>
            {trace.thread_id && (
              <button
                type="button"
                onClick={() => onOpenThread(trace.thread_id as string)}
                className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-accent-strong hover:underline dark:bg-zinc-800 dark:text-accent-soft"
                title="Open this thread"
              >
                thread {trace.thread_id} ↗
              </button>
            )}
          </div>

          {trace.input && (
            <Field label="User input">
              <p className="whitespace-pre-wrap">{trace.input}</p>
            </Field>
          )}
          {trace.output && (
            <Field label="Assistant output">
              <p className="whitespace-pre-wrap">{trace.output}</p>
            </Field>
          )}

          <div>
            <h3 className="mb-1 text-xs font-semibold tracking-wide text-zinc-500 uppercase dark:text-zinc-400">
              Span tree
            </h3>
            <SpanTree spans={trace.spans} />
          </div>
        </div>
      )}
    </section>
  )
}

function Field({
  label,
  children,
}: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <div>
      <h3 className="mb-1 text-xs font-semibold tracking-wide text-zinc-500 uppercase dark:text-zinc-400">
        {label}
      </h3>
      <div className="rounded-lg bg-zinc-50 p-2.5 text-sm text-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-200">
        {children}
      </div>
    </div>
  )
}
