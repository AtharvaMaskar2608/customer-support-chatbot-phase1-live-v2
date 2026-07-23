/**
 * Per-turn token trend for a thread — the context-rot gauge. Hand-rolled CSS
 * bars (no chart dependency): each turn is a stacked bar of billed `input_tokens`
 * (bottom) plus `cache_read` tokens (top), so a conversation whose context keeps
 * growing shows a rising staircase, and how much of it is served from cache.
 */

import type { TraceDetail } from './api'
import { fmtInt, num } from './format'

type Point = { turn: number; id: number; input: number; cacheRead: number }

function pointsOf(traces: TraceDetail[]): Point[] {
  return traces.map((t, i) => {
    let cacheRead = 0
    let llmInput = 0
    for (const span of t.spans ?? []) {
      if (span.type !== 'llm') continue
      cacheRead += num(span.metadata?.cache_read_input_tokens) ?? 0
      llmInput += num(span.metadata?.input_tokens) ?? 0
    }
    return {
      turn: i + 1,
      id: t.id,
      input: t.input_tokens ?? llmInput,
      cacheRead,
    }
  })
}

export function TokenTrend({
  traces,
  onSelect,
}: Readonly<{ traces: TraceDetail[]; onSelect: (id: number) => void }>) {
  const points = pointsOf(traces)
  const max = Math.max(1, ...points.map((p) => p.input + p.cacheRead))
  const anyCache = points.some((p) => p.cacheRead > 0)

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase dark:text-zinc-400">
          Input tokens per turn
        </h3>
        <div className="flex items-center gap-3 text-[11px] text-zinc-500 dark:text-zinc-400">
          <span className="flex items-center gap-1">
            <span className="inline-block size-2.5 rounded-sm bg-accent" />
            input
          </span>
          {anyCache && (
            <span className="flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-sm bg-accent-soft/60" />
              cache-read
            </span>
          )}
        </div>
      </div>

      <div className="flex h-32 items-end gap-1 overflow-x-auto rounded-lg border border-zinc-200 bg-zinc-50 p-2 dark:border-zinc-800 dark:bg-zinc-900/50">
        {points.map((p) => {
          const total = p.input + p.cacheRead
          const inputPct = (p.input / max) * 100
          const cachePct = (p.cacheRead / max) * 100
          return (
            <button
              type="button"
              key={p.id}
              onClick={() => onSelect(p.id)}
              title={`Turn ${p.turn} · input ${fmtInt(p.input)} · cache-read ${fmtInt(p.cacheRead)} tokens`}
              className="group flex h-full min-w-[10px] flex-1 flex-col justify-end"
            >
              <div className="flex flex-col justify-end overflow-hidden rounded-t-sm">
                <div
                  className="w-full bg-accent-soft/60"
                  style={{ height: `${cachePct}%` }}
                />
                <div
                  className="w-full bg-accent transition-opacity group-hover:opacity-80"
                  style={{ height: `${inputPct}%` }}
                />
              </div>
              <span className="mt-0.5 block text-center text-[9px] text-zinc-400 tabular-nums">
                {total >= 1000 ? `${Math.round(total / 1000)}k` : total}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
