/** The paginated, filtered traces list (left pane of the Traces view). */

import { useEffect, useState } from 'react'
import type { TraceFilters, TraceListItem } from './api'
import { listTraces } from './api'
import { fmtInt, fmtMs, fmtRelative } from './format'
import { Chip, Empty, ErrorBadge, ErrorNote, Pager, Spinner } from './ui'

const PAGE = 50

export function TraceList({
  token,
  filters,
  selectedId,
  onSelect,
  onError,
}: Readonly<{
  token: string
  filters: TraceFilters
  selectedId: number | null
  onSelect: (id: number) => void
  onError: (e: unknown) => void
}>) {
  const [items, setItems] = useState<TraceListItem[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  const filtersKey = JSON.stringify(filters)

  // A filter change resets to the first page.
  useEffect(() => setOffset(0), [filtersKey])

  useEffect(() => {
    let live = true
    setLoading(true)
    setFailed(false)
    listTraces(token, filters, PAGE, offset)
      .then((res) => {
        if (!live) return
        setItems(res.traces)
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
  }, [token, filters, filtersKey, offset, onError])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between px-1">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">
          Traces {loading && <Spinner />}
        </h2>
        <span className="text-xs text-zinc-400">{fmtInt(total)} total</span>
      </div>

      {failed && <ErrorNote>Could not load traces.</ErrorNote>}

      {!failed && items.length === 0 && !loading && (
        <Empty>No traces match these filters.</Empty>
      )}

      <ul className="flex flex-col gap-2">
        {items.map((t) => {
          const active = t.id === selectedId
          return (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => onSelect(t.id)}
                className={`w-full rounded-xl border p-3 text-left transition-colors ${
                  active
                    ? 'border-accent bg-accent-tint/60 dark:border-accent dark:bg-accent/10'
                    : 'border-zinc-200 bg-white hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                  <span className="font-mono text-zinc-400">#{t.id}</span>
                  <span>{fmtRelative(t.created_at)}</span>
                  {t.had_error && <ErrorBadge />}
                  <span className="ml-auto tabular-nums">{fmtMs(t.latency_ms)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-zinc-800 dark:text-zinc-100">
                  {t.input || <span className="text-zinc-400">(no input)</span>}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
                  {t.model && <Chip>{t.model}</Chip>}
                  <Chip>
                    {fmtInt(t.input_tokens)}→{fmtInt(t.output_tokens)} tok
                  </Chip>
                  {t.tools.map((tool) => (
                    <Chip key={tool}>{tool}</Chip>
                  ))}
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
