import { useEffect, type ComponentType, type SVGProps } from 'react'
import { DocumentIcon, SparkleIcon, TicketIcon, XIcon } from './icons'
import type { WhatsNewItem } from './useWhatsNew'

/**
 * Tint-matched icon tiles (task 5.4): the mock shows the glyph COLORED to
 * match its tile (blue document on indigo, green ticket on green) — native
 * emoji rendering (orange 🎫) breaks that. Known emoji map to inline SVG
 * glyphs colored via currentColor with the tint's text color; unknown
 * emoji/tint combinations fall back to the raw emoji on a neutral tile,
 * since remote content may ship arbitrary emoji later.
 */
const GLYPHS: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  '📄': DocumentIcon,
  '🎫': TicketIcon,
  '🎟️': TicketIcon,
  '✨': SparkleIcon,
}

/** tint key from the payload -> tile background + glyph color. */
const TINTS: Record<string, { tile: string; glyph: string }> = {
  indigo: {
    tile: 'bg-indigo-100 dark:bg-indigo-500/20',
    glyph: 'text-indigo-600 dark:text-indigo-400',
  },
  green: {
    tile: 'bg-green-100 dark:bg-green-500/20',
    glyph: 'text-green-600 dark:text-green-400',
  },
  blue: {
    tile: 'bg-accent-tint dark:bg-accent/20',
    glyph: 'text-accent dark:text-accent-soft',
  },
}
const NEUTRAL: { tile: string; glyph: string } = {
  tile: 'bg-zinc-100 dark:bg-zinc-800',
  glyph: 'text-zinc-600 dark:text-zinc-300',
}

function ItemTile({ emoji, tint }: Readonly<{ emoji: string; tint: string }>) {
  const Glyph = GLYPHS[emoji]

  if (Glyph === undefined) {
    // Unknown emoji -> raw emoji on a neutral tile.
    return (
      <span
        aria-hidden="true"
        className={`grid size-10 shrink-0 place-items-center rounded-xl text-lg ${NEUTRAL.tile}`}
      >
        {emoji}
      </span>
    )
  }

  const colors = TINTS[tint] ?? NEUTRAL
  return (
    <span
      aria-hidden="true"
      className={`grid size-10 shrink-0 place-items-center rounded-xl ${colors.tile}`}
    >
      <Glyph className={`size-5 ${colors.glyph}`} />
    </span>
  )
}

export function WhatsNewModal({
  items,
  onClose,
}: Readonly<{ items: WhatsNewItem[]; onClose: () => void }>) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-zinc-950/40 p-4 backdrop-blur-[2px]">
      <div
        role="dialog"
        aria-modal="true"
        aria-label="What's new in Jini"
        className="w-full max-w-[340px] rounded-3xl border border-zinc-200/80 bg-white p-5 shadow-2xl shadow-zinc-950/20 dark:border-zinc-700/60 dark:bg-zinc-900 dark:shadow-black/50"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-[17px] font-bold text-zinc-900 dark:text-zinc-50">
            ✨ What's new in Jini
          </h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="-mr-1.5 grid size-8 shrink-0 place-items-center rounded-full text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
          >
            <XIcon className="size-4.5" />
          </button>
        </div>

        <ul className="mt-4 space-y-4">
          {items.map((item) => (
            <li key={item.title} className="flex items-start gap-3">
              <ItemTile emoji={item.emoji} tint={item.tint} />
              <div className="min-w-0 pt-0.5">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
                  {item.title}
                </h3>
                <p className="mt-0.5 text-[13px] leading-snug text-zinc-500 dark:text-zinc-400">
                  {item.description}
                </p>
              </div>
            </li>
          ))}
        </ul>

        <button
          type="button"
          onClick={onClose}
          className="mt-5 w-full rounded-full bg-accent py-3 text-sm font-semibold text-white shadow-lg shadow-accent/25 transition hover:bg-accent-strong active:scale-[0.99]"
        >
          Got it
        </button>
      </div>
    </div>
  )
}
