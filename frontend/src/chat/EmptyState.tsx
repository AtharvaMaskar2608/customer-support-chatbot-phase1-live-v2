import type { AnyFlowDescriptor } from '../flow/dataflow'
import { useEntryGreeting } from '../useGreeting'
import { Stickers } from './Stickers'

const PLACEHOLDER = '{clientRef}'

/**
 * The headline, rendered from the backend's template (CHO-226).
 *
 * The template is split on `{clientRef}` and the name goes inside the same
 * accent span the static greeting has always used — that is the whole reason
 * the backend ships a template instead of a rendered string (design D1). With
 * no template (fetch failed, partial payload, key we don't recognise) this
 * falls through to the static greeting, byte-identical to the pre-CHO-226
 * headline — which is also what the DEFAULT template renders to.
 */
function Headline({
  firstName,
  template,
}: Readonly<{ firstName: string | null; template: string | null }>) {
  if (template === null) {
    return (
      <>
        Hey <span className="text-accent dark:text-accent-soft">{firstName ?? 'there'}</span> —
        what do you need?
      </>
    )
  }

  const marker = template.indexOf(PLACEHOLDER)
  // No placeholder: a fallbackTemplates entry, already free of dangling
  // punctuation and double spaces. Render it verbatim.
  if (marker === -1) return <>{template}</>

  return (
    <>
      {template.slice(0, marker)}
      <span className="text-accent dark:text-accent-soft">{firstName ?? 'there'}</span>
      {template.slice(marker + PLACEHOLDER.length)}
    </>
  )
}

/**
 * The conversation's empty state: greeting + quick-action stickers. On first
 * engagement it collapses away (max-height/opacity transition) and the
 * conversation owns the canvas — `onCollapsed` unmounts it once the animation
 * settles. Keeps the "no email verification" line from the existing home.
 *
 * The greeting is presentation only: it is never a chat message, never in
 * history, never routed as intent.
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
  // Recomputed on mount, so Restart (which remounts the shell) re-selects the
  // window; static thereafter, so a boundary passing mid-view changes nothing.
  const greeting = useEntryGreeting()

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
          <Headline firstName={firstName} template={greeting?.template ?? null} />
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Fetch your reports instantly, explain charges and processes.
        </p>
        <p className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">
          Files land right here in chat —{' '}
          <span className="font-medium text-accent dark:text-accent-soft">
            no email verification needed.
          </span>
        </p>
      </section>

      {/* CHO-234: the "POPULAR RIGHT NOW" eyebrow was removed — the chips are
          the standard entry points, not an editorialised trend list. */}
      <section className="pt-6">
        <Stickers onPick={onPick} paginate />
      </section>

      {/* CHO-260: hairline divider signals open-ended chat below the chip pages. */}
      <div className="mt-6 mb-2 flex items-center gap-3">
        <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-700" />
        <span className="shrink-0 text-sm text-zinc-500 dark:text-zinc-400">
          or ask anything about FinX
        </span>
        <span className="h-px flex-1 bg-zinc-200 dark:bg-zinc-700" />
      </div>
    </div>
  )
}
