import type { AnyFlowDescriptor } from '../flow/dataflow'
import { Stickers } from './Stickers'

/**
 * The conversation's empty state: greeting + quick-action stickers. On first
 * engagement it collapses away (max-height/opacity transition) and the
 * conversation owns the canvas — `onCollapsed` unmounts it once the animation
 * settles. Keeps the "no email verification" line from the existing home.
 */
export function EmptyState({
  firstName,
  collapsing,
  onCollapsed,
  onPick,
}: Readonly<{
  firstName: string | null
  collapsing: boolean
  onCollapsed: () => void
  onPick: (flow: AnyFlowDescriptor) => void
}>) {
  return (
    <div
      onTransitionEnd={collapsing ? onCollapsed : undefined}
      className={[
        'overflow-hidden transition-all duration-300 ease-out',
        collapsing ? 'max-h-0 -translate-y-1.5 opacity-0' : 'max-h-[640px] opacity-100',
      ].join(' ')}
    >
      <section className="pt-1">
        <h2 className="text-[26px] leading-8 font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
          Hey <span className="text-accent dark:text-accent-soft">{firstName ?? 'there'}</span> —
          what do you need?
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Reports, charges, processes, ticket status.
        </p>
        <p className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Files land right here —{' '}
          <span className="font-medium text-online dark:text-online-soft">
            no email verification.
          </span>
        </p>
      </section>

      <section className="pt-6">
        <h3 className="mb-3 text-[11px] font-semibold tracking-[0.14em] text-zinc-400 uppercase dark:text-zinc-500">
          Popular right now
        </h3>
        <Stickers onPick={onPick} />
      </section>
    </div>
  )
}
