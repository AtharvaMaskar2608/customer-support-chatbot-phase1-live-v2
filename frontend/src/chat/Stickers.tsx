import { FLOWS } from '../flow/registry'
import type { FlowDescriptor, TintKey } from '../flow/types'

/** Per-flow tint → icon-circle classes (static so Tailwind keeps them). */
const TINT: Record<TintKey, string> = {
  violet: 'bg-accent-tint text-accent dark:bg-accent/20 dark:text-accent-soft',
  blue: 'bg-blue-100 text-blue-600 dark:bg-blue-500/20 dark:text-blue-400',
  amber: 'bg-amber-100 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400',
  teal: 'bg-teal-100 text-teal-600 dark:bg-teal-500/20 dark:text-teal-400',
}

/**
 * The quick-action sticker row. Rendered from the auto-discovered flow
 * registry — so a Wave-1 flow's sticker appears the moment its descriptor
 * file lands, with no edit here. Used both as the empty-state stickers and
 * as the reply when composer text matches no flow.
 */
export function Stickers({ onPick }: Readonly<{ onPick: (flow: FlowDescriptor) => void }>) {
  return (
    <div className="flex flex-wrap gap-2.5">
      {FLOWS.map((flow) => {
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
            {flow.trigger}
          </button>
        )
      })}
    </div>
  )
}
