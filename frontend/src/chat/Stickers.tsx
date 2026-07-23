import { useState } from 'react'
import { DATA_FLOWS } from '../flow/dataRegistry'
import type { AnyFlowDescriptor } from '../flow/dataflow'
import { FLOWS } from '../flow/registry'
import type { TintKey } from '../flow/types'
import { ChevronLeftIcon, ChevronRightIcon } from '../icons'

/** Per-flow tint → icon-circle classes (static so Tailwind keeps them).
 *  emerald/rose are pre-registered for the Wave-B data-flow stickers. */
const TINT: Record<TintKey, string> = {
  violet: 'bg-accent-tint text-accent dark:bg-accent/20 dark:text-accent-soft',
  blue: 'bg-blue-100 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400',
  amber: 'bg-amber-100 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400',
  teal: 'bg-teal-100 text-teal-600 dark:bg-teal-500/20 dark:text-teal-400',
  cyan: 'bg-cyan-100 text-cyan-600 dark:bg-cyan-500/20 dark:text-cyan-400',
  emerald: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400',
  rose: 'bg-rose-100 text-rose-600 dark:bg-rose-500/20 dark:text-rose-400',
}

/** File + data flows on one ordering scale (Holdings is 0, ahead of P&L).
 *  `hideSticker` flows (CHO-233: brokerage) stay registered + keyword-routable
 *  but are dropped from the home chip grid. */
const ALL_FLOWS: AnyFlowDescriptor[] = [...FLOWS, ...DATA_FLOWS]
  .filter((flow) => !flow.hideSticker)
  .sort((a, b) => a.order - b.order)

const PAGE_SIZE = 4

/**
 * The quick-action sticker row. Rendered from the auto-discovered flow
 * registries — so a new flow's sticker (file or data) appears the moment its
 * descriptor file lands, with no edit here. Used both as the empty-state
 * stickers and as the reply when composer text matches no flow.
 *
 * Landing (`paginate`) shows four chips per page with prev/next + dots;
 * conversation fallback keeps the full wrap row.
 */
export function Stickers({
  onPick,
  paginate = false,
}: Readonly<{
  onPick: (flow: AnyFlowDescriptor) => void
  paginate?: boolean
}>) {
  const [page, setPage] = useState(0)
  const totalPages = Math.max(1, Math.ceil(ALL_FLOWS.length / PAGE_SIZE))
  const visible = paginate
    ? ALL_FLOWS.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)
    : ALL_FLOWS

  return (
    <div>
      <div className="flex flex-wrap gap-2.5">
        {visible.map((flow) => {
          const Icon = flow.sticker.icon
          return (
            <button
              key={flow.key}
              type="button"
              onClick={() => onPick(flow)}
              className="inline-flex items-center gap-2.5 rounded-full border border-zinc-200 bg-white py-1.5 pr-4 pl-1.5 text-[13.5px] font-semibold text-zinc-800 shadow-sm transition-all hover:-translate-y-0.5 hover:border-accent-soft hover:shadow-md hover:shadow-accent/15 active:translate-y-0 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            >
              <span className={`grid size-7 place-items-center rounded-full ${TINT[flow.sticker.tint]}`}>
                <Icon className="size-4" />
              </span>
              {flow.stickerLabel ?? flow.trigger}
            </button>
          )
        })}
      </div>

      {paginate && totalPages > 1 ? (
        <div className="mt-4 flex items-center justify-center gap-3">
          <button
            type="button"
            aria-label="Previous chip page"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="grid size-7 place-items-center rounded-full border border-zinc-200 text-zinc-600 transition-colors enabled:hover:border-accent-soft enabled:hover:text-accent disabled:cursor-not-allowed disabled:opacity-35 dark:border-zinc-700 dark:text-zinc-300 dark:enabled:hover:text-accent-soft"
          >
            <ChevronLeftIcon className="size-4" />
          </button>
          <div className="flex items-center gap-1.5" role="tablist" aria-label="Chip pages">
            {Array.from({ length: totalPages }, (_, i) => (
              <button
                key={i}
                type="button"
                role="tab"
                aria-label={`Chip page ${i + 1}`}
                aria-selected={i === page}
                onClick={() => setPage(i)}
                className={[
                  'size-1.5 rounded-full transition-colors',
                  i === page
                    ? 'bg-accent dark:bg-accent-soft'
                    : 'bg-zinc-300 hover:bg-zinc-400 dark:bg-zinc-600 dark:hover:bg-zinc-500',
                ].join(' ')}
              />
            ))}
          </div>
          <button
            type="button"
            aria-label="Next chip page"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            className="grid size-7 place-items-center rounded-full border border-zinc-200 text-zinc-600 transition-colors enabled:hover:border-accent-soft enabled:hover:text-accent disabled:cursor-not-allowed disabled:opacity-35 dark:border-zinc-700 dark:text-zinc-300 dark:enabled:hover:text-accent-soft"
          >
            <ChevronRightIcon className="size-4" />
          </button>
        </div>
      ) : null}
    </div>
  )
}
