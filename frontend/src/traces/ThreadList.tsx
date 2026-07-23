/** The paginated threads (conversations) list — left pane of the Threads view. */

import { useEffect, useState } from 'react'
import type { Thread } from './api'
import { listThreads } from './api'
import { fmtInt, fmtRelative } from './format'
import { Empty, ErrorBadge, ErrorNote, Pager, Spinner } from './ui'

const PAGE = 50

export function ThreadList({
  token,
  selectedId,
  onSelect,
  onError,
}: Readonly<{
  token: string
  selectedId: string | null
  onSelect: (id: string) => void
  onError: (e: unknown) => void
}>) {
  const [items, setItems] = useState<Thread[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    setLoading(true)
    setFailed(false)
    listThreads(token, PAGE, offset)
      .then((res) => {
        if (!live) return
        setItems(res.threads)
        setTotal(res.total)
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
  }, [token, offset, onError])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">
          Threads {loading && <Spinner />}
        </h2>
        <span className="text-xs text-zinc-400">{fmtInt(total)} total</span>
      </div>

      {failed && <ErrorNote>Could not load threads.</ErrorNote>}
      {!failed && items.length === 0 && !loading && (
        <Empty>No threads recorded yet.</Empty>
      )}

      <ul className="flex flex-col gap-2">
        {items.map((t) => {
          const active = t.thread_id === selectedId
          return (
            <li key={t.thread_id}>
              <button
                type="button"
                onClick={() => onSelect(t.thread_id)}
                className={`w-full rounded-xl border p-3 text-left transition-colors ${
                  active
                    ? 'border-accent bg-accent-tint/60 dark:border-accent dark:bg-accent/10'
                    : 'border-zinc-200 bg-white hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="truncate font-mono text-sm text-zinc-800 dark:text-zinc-100">
                    {t.thread_id}
                  </span>
                  {t.had_error && <ErrorBadge />}
                </div>
                <div className="mt-1.5 flex items-center gap-3 text-xs text-zinc-500 dark:text-zinc-400">
                  <span>{fmtInt(t.turns)} turns</span>
                  <span>{fmtInt(t.total_input_tokens)} in-tok</span>
                  <span className="ml-auto">{fmtRelative(t.last_at)}</span>
                </div>
              </button>
            </li>
          )
        })}
      </ul>

      {total > PAGE && (
        <Pager
          offset={offset}
          limit={PAGE}
          total={total}
          onPrev={() => setOffset((o) => Math.max(0, o - PAGE))}
          onNext={() => setOffset((o) => o + PAGE)}
        />
      )}
    </div>
  )
}
